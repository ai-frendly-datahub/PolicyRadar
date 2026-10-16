"""Git snapshots stored as zstd Parquet instead of Git LFS.

Historical ``*.duckdb`` paths can still contain Git LFS pointer text. Callers
that only need to read articles should use :func:`connect_readonly`, which
understands those pointers. Writers should use :func:`resolve_writable_database`,
which leaves the pointer file in place and uses ``data/work/`` for the real
DuckDB file.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb

# Strictly under GitHub's 50 MB warning. A committed file must stay below this.
PARQUET_MAX_BYTES = 50_000_000

_LFS_PREFIX = b"version https://git-lfs.github.com/spec/v1"
_ARTICLE_COLUMNS: tuple[str, ...] = (
    "category",
    "source",
    "title",
    "link",
    "summary",
    "published",
    "collected_at",
    "entities_json",
    "ontology_json",
    "run_id",
    "collector_version",
    "fetch_status",
    "fetched_at",
)
_PROJECTION = """
CAST(category AS VARCHAR) AS category,
CAST(source AS VARCHAR) AS source,
CAST(title AS VARCHAR) AS title,
CAST(link AS VARCHAR) AS link,
CAST(summary AS VARCHAR) AS summary,
CAST(published AS TIMESTAMP) AS published,
CAST(collected_at AS TIMESTAMP) AS collected_at,
CAST(entities_json AS VARCHAR) AS entities_json,
CAST(ontology_json AS VARCHAR) AS ontology_json,
CAST(run_id AS VARCHAR) AS run_id,
CAST(collector_version AS VARCHAR) AS collector_version,
CAST(fetch_status AS VARCHAR) AS fetch_status,
CAST(fetched_at AS TIMESTAMP) AS fetched_at
"""
_EMPTY_ARTICLES_DDL = """
CREATE TABLE articles (
    id BIGINT,
    category VARCHAR,
    source VARCHAR,
    title VARCHAR,
    link VARCHAR,
    summary VARCHAR,
    published TIMESTAMP,
    collected_at TIMESTAMP,
    entities_json VARCHAR,
    ontology_json VARCHAR,
    run_id VARCHAR,
    collector_version VARCHAR,
    fetch_status VARCHAR,
    fetched_at TIMESTAMP
)
"""


class ParquetBudgetError(RuntimeError):
    """Raised when a Parquet snapshot cannot be kept under the byte budget."""


def is_lfs_pointer(path: Path) -> bool:
    """Return True when ``path`` is a Git LFS pointer, not a database."""
    if not path.is_file():
        return False
    try:
        if path.stat().st_size > 1024:
            return False
        with path.open("rb") as handle:
            prefix = handle.read(len(_LFS_PREFIX))
    except OSError:
        return False
    return prefix == _LFS_PREFIX


def is_duckdb_file(path: Path) -> bool:
    """Return True when ``path`` looks like a DuckDB file rather than a pointer.

    Current DuckDB files store the ``DUCK`` marker a few bytes into the header,
    not at offset 0.
    """
    if not path.is_file() or is_lfs_pointer(path):
        return False
    try:
        with path.open("rb") as handle:
            header = handle.read(64)
    except OSError:
        return False
    return b"DUCK" in header


def is_parquet_file(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"PAR1"
    except OSError:
        return False


def connect_readonly(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Open articles for reading.

    A real DuckDB file is opened directly. An LFS pointer falls back to a
    sibling working database, then to Parquet, then to an empty ``articles``
    table so callers can query without raising.
    """
    if is_duckdb_file(db_path):
        return duckdb.connect(str(db_path), read_only=True)
    work = _work_path(db_path)
    if is_duckdb_file(work):
        return duckdb.connect(str(work), read_only=True)

    connection = duckdb.connect()
    parquet_files = _parquet_sources(db_path)
    if not parquet_files:
        connection.execute(_EMPTY_ARTICLES_DDL)
        return connection

    selects = " UNION ALL BY NAME ".join(
        f"SELECT * FROM read_parquet({_quote(path)})" for path in parquet_files
    )
    connection.execute(f"""
        CREATE TABLE articles AS
        SELECT * EXCLUDE (_rn) FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY link
                       ORDER BY collected_at DESC NULLS LAST
                   ) AS _rn
            FROM ({selects})
        )
        WHERE _rn = 1
        """)
    return connection


def resolve_writable_database(db_path: Path, *, raw_data_dir: Path | None = None) -> Path:
    """Return a real DuckDB path without modifying an LFS pointer.

    Missing paths are returned unchanged so the caller can create them. Pointer
    files stay on disk; the writable database is ``data/work/<name>``.
    """
    if is_duckdb_file(db_path) or not db_path.exists():
        return db_path
    work = _work_path(db_path)
    if is_duckdb_file(work):
        return work
    work.parent.mkdir(parents=True, exist_ok=True)
    _hydrate(work, db_path, raw_data_dir=raw_data_dir)
    return work


def export_articles_parquet(
    db_path: Path,
    *,
    parquet_root: Path | None = None,
    overflow_dir: Path | None = None,
    max_bytes: int = PARQUET_MAX_BYTES,
    snapshot_date: date | None = None,
    keep_daily_days: int = 30,
) -> dict[str, object]:
    """Write the articles table to zstd Parquet strictly under ``max_bytes``.

    Newest rows stay in git. Rows that do not fit are written to
    ``articles-overflow.parquet`` for a GitHub Release upload. Historical
    DuckDB files are not deleted.
    """
    root = parquet_root or (db_path.parent / "parquet")
    release_dir = overflow_dir or (db_path.parent / "release")
    empty: dict[str, object] = {
        "parquet_path": None,
        "parquet_bytes": 0,
        "overflow_path": None,
        "overflow_bytes": 0,
        "rows_kept": 0,
        "rows_overflow": 0,
        "truncated": False,
        "daily_removed": 0,
    }
    if not is_duckdb_file(db_path):
        return empty

    stamp = snapshot_date or datetime.now(UTC).date()
    root.mkdir(parents=True, exist_ok=True)
    final_path = root / "articles.parquet"
    partial_path = root / "articles.parquet.partial"
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {str(name) for (name,) in connection.execute("SHOW TABLES").fetchall()}
        if "articles" not in tables:
            return empty
        total = int(connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0])
        if total == 0:
            size = _copy_newest(connection, partial_path, 0)
            kept = 0
            truncated = False
        else:
            full_size = _copy_newest(connection, partial_path, None)
            if full_size < max_bytes:
                size = full_size
                kept = total
                truncated = False
            else:
                lo = 0
                hi = total
                kept = 0
                while lo <= hi:
                    mid = (lo + hi) // 2
                    mid_size = _copy_newest(connection, partial_path, mid)
                    if mid_size < max_bytes:
                        kept = mid
                        lo = mid + 1
                    else:
                        hi = mid - 1
                size = _copy_newest(connection, partial_path, kept)
                truncated = kept < total
        if size >= max_bytes:
            raise ParquetBudgetError(
                f"Parquet snapshot is {size} bytes, at or above the {max_bytes} byte budget"
            )
        os.replace(partial_path, final_path)
        daily_dir = root / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        daily_path = daily_dir / f"{stamp.isoformat()}.parquet"
        shutil.copy2(final_path, daily_path)
        daily_removed = cleanup_parquet_snapshots(daily_dir, keep_days=keep_daily_days, today=stamp)

        overflow_path: Path | None = None
        overflow_bytes = 0
        overflow_rows = 0
        manifest = release_dir / "UPLOAD"
        if truncated:
            release_dir.mkdir(parents=True, exist_ok=True)
            overflow_path = release_dir / "articles-overflow.parquet"
            overflow_bytes = _copy_overflow(connection, final_path, overflow_path)
            overflow_rows = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM read_parquet({_quote(overflow_path)})"
                ).fetchone()[0]
            )
            manifest.write_text(f"{overflow_path.name}\n", encoding="utf-8")
        elif manifest.exists():
            manifest.unlink()
    finally:
        connection.close()
        if partial_path.exists():
            partial_path.unlink()

    return {
        "parquet_path": str(final_path),
        "daily_parquet_path": str(daily_path),
        "parquet_bytes": final_path.stat().st_size,
        "overflow_path": str(overflow_path) if overflow_path is not None else None,
        "overflow_bytes": overflow_bytes,
        "rows_kept": kept,
        "rows_overflow": overflow_rows,
        "truncated": truncated,
        "daily_removed": daily_removed,
    }


def cleanup_parquet_snapshots(daily_dir: Path, *, keep_days: int, today: date | None = None) -> int:
    """Remove dated Parquet snapshots older than ``keep_days``.

    DuckDB files in the same directory are left untouched.
    """
    if keep_days < 0 or not daily_dir.exists():
        return 0
    cutoff = (today or datetime.now(UTC).date()) - timedelta(days=keep_days)
    removed = 0
    for item in daily_dir.iterdir():
        if not item.is_file() or item.suffix != ".parquet":
            continue
        try:
            stamp = date.fromisoformat(item.stem)
        except ValueError:
            continue
        if stamp < cutoff:
            item.unlink()
            removed += 1
    return removed


def _work_path(db_path: Path) -> Path:
    return db_path.parent / "work" / db_path.name


def _quote(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _parquet_sources(db_path: Path) -> list[Path]:
    base = db_path.parent
    found: list[Path] = []
    release = base / "release"
    if release.is_dir():
        found.extend(sorted(path for path in release.glob("*.parquet") if is_parquet_file(path)))
    rolling = base / "parquet" / "articles.parquet"
    if is_parquet_file(rolling):
        found.append(rolling)
    return found


def _hydrate(work: Path, configured: Path, *, raw_data_dir: Path | None) -> None:
    from policyradar.storage import RadarStorage

    storage = RadarStorage(work)
    try:
        sources = _parquet_sources(configured)
        if sources:
            _insert_parquets(storage.conn, sources)
        elif raw_data_dir is not None and raw_data_dir.exists():
            _load_raw_jsonl(storage, raw_data_dir)
    finally:
        storage.close()


def _insert_parquets(connection: duckdb.DuckDBPyConnection, paths: list[Path]) -> None:
    rolling = [path for path in paths if path.name == "articles.parquet"]
    older = [path for path in paths if path.name != "articles.parquet"]
    for path in older:
        _insert_parquet(connection, path, overwrite=False)
    for path in rolling:
        _insert_parquet(connection, path, overwrite=True)


def _insert_parquet(connection: duckdb.DuckDBPyConnection, path: Path, *, overwrite: bool) -> None:
    conflict = (
        """
        ON CONFLICT (link) DO UPDATE SET
            category = EXCLUDED.category,
            source = EXCLUDED.source,
            title = EXCLUDED.title,
            summary = EXCLUDED.summary,
            published = EXCLUDED.published,
            collected_at = EXCLUDED.collected_at,
            entities_json = EXCLUDED.entities_json,
            ontology_json = EXCLUDED.ontology_json,
            run_id = EXCLUDED.run_id,
            collector_version = EXCLUDED.collector_version,
            fetch_status = EXCLUDED.fetch_status,
            fetched_at = EXCLUDED.fetched_at
        """
        if overwrite
        else "ON CONFLICT (link) DO NOTHING"
    )
    connection.execute(f"""
        INSERT INTO articles (
            category, source, title, link, summary, published, collected_at,
            entities_json, ontology_json, run_id, collector_version, fetch_status, fetched_at
        )
        SELECT
            category, source, title, link, summary, published,
            COALESCE(collected_at, published, CURRENT_TIMESTAMP),
            COALESCE(entities_json, '{{}}'),
            COALESCE(ontology_json, '{{}}'),
            run_id, collector_version, fetch_status, fetched_at
        FROM read_parquet({_quote(path)})
        {conflict}
        """)


def _load_raw_jsonl(storage: object, raw_dir: Path) -> int:
    from radar_core.url_utils import canonical_url

    from policyradar.models import Article
    from policyradar.storage import RadarStorage

    if not isinstance(storage, RadarStorage):
        raise TypeError("storage must be a RadarStorage")

    latest: dict[str, Article] = {}
    for path in sorted(raw_dir.rglob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            link = canonical_url(str(record.get("link") or "")) or str(record.get("link") or "")
            title = str(record.get("title") or "").strip()
            if not link or not title:
                continue
            published = _parse_datetime(record.get("published"))
            collected_at = _parse_datetime(record.get("logged_at")) or published
            article = Article(
                title=title,
                link=link,
                summary=str(record.get("summary") or ""),
                published=published,
                source=str(record.get("source") or ""),
                category=str(record.get("category") or ""),
                matched_entities=_entities(record.get("matched_entities")),
                collected_at=collected_at,
            )
            latest[link] = article
    articles = list(latest.values())
    upsert = storage.upsert_articles
    for start in range(0, len(articles), 500):
        upsert(articles[start : start + 500])
    return len(articles)


def _entities(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    parsed: dict[str, list[str]] = {}
    for key, item in value.items():
        if isinstance(item, list):
            parsed[str(key)] = [str(entry) for entry in item]
        elif item is None:
            parsed[str(key)] = []
        else:
            parsed[str(key)] = [str(item)]
    return parsed


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _copy_newest(connection: duckdb.DuckDBPyConnection, dest: Path, limit: int | None) -> int:
    if dest.exists():
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if limit is None:
        query = f"SELECT {_PROJECTION} FROM articles"
    else:
        query = f"""
            SELECT {", ".join(_ARTICLE_COLUMNS)} FROM (
                SELECT {_PROJECTION},
                       ROW_NUMBER() OVER (
                           ORDER BY COALESCE(published, collected_at) DESC NULLS LAST, link DESC
                       ) AS _rn
                FROM articles
            ) ranked
            WHERE _rn <= {int(limit)}
        """
    connection.execute(f"COPY ({query}) TO {_quote(dest)} (FORMAT PARQUET, COMPRESSION ZSTD)")
    return dest.stat().st_size


def _copy_overflow(connection: duckdb.DuckDBPyConnection, kept: Path, dest: Path) -> int:
    if dest.exists():
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(f"""
        COPY (
            SELECT {_PROJECTION}
            FROM articles
            WHERE link NOT IN (SELECT link FROM read_parquet({_quote(kept)}))
        ) TO {_quote(dest)} (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
    return dest.stat().st_size
