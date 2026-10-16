from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from policyradar.date_storage import apply_date_storage_policy
from policyradar.models import Article
from policyradar.parquet_store import (
    PARQUET_MAX_BYTES,
    cleanup_parquet_snapshots,
    connect_readonly,
    export_articles_parquet,
    is_lfs_pointer,
    resolve_writable_database,
)
from policyradar.storage import RadarStorage

_POINTER = (
    "version https://git-lfs.github.com/spec/v1\n"
    "oid sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
    "size 12\n"
)


def _article(link: str, *, published: datetime, summary: str = "summary") -> Article:
    return Article(
        title=f"title {link}",
        link=link,
        summary=summary,
        published=published,
        source="Example",
        category="policy",
        matched_entities={},
    )


def _fill(db_path: Path, articles: list[Article]) -> None:
    storage = RadarStorage(db_path)
    try:
        storage.upsert_articles(articles)
    finally:
        storage.close()


def test_connect_readonly_reads_parquet_and_leaves_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / "radar_data.duckdb"
    pointer.write_text(_POINTER, encoding="utf-8")
    real = tmp_path / "source.duckdb"
    published = datetime(2026, 10, 1, tzinfo=UTC)
    _fill(real, [_article("https://example.com/a", published=published)])
    export_articles_parquet(
        real, parquet_root=tmp_path / "parquet", overflow_dir=tmp_path / "release"
    )

    before = pointer.read_bytes()
    connection = connect_readonly(pointer)
    try:
        rows = connection.execute("SELECT link FROM articles").fetchall()
    finally:
        connection.close()

    assert rows == [("https://example.com/a",)]
    assert pointer.read_bytes() == before
    assert is_lfs_pointer(pointer)


def test_connect_readonly_on_pointer_without_parquet_returns_empty_table(tmp_path: Path) -> None:
    pointer = tmp_path / "radar_data.duckdb"
    pointer.write_text(_POINTER, encoding="utf-8")

    connection = connect_readonly(pointer)
    try:
        rows = connection.execute("SELECT COUNT(*) FROM articles").fetchall()
    finally:
        connection.close()

    assert rows == [(0,)]
    assert is_lfs_pointer(pointer)


def test_resolve_writable_database_does_not_replace_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / "radar_data.duckdb"
    pointer.write_text(_POINTER, encoding="utf-8")
    raw = tmp_path / "raw" / "2026-10-01"
    raw.mkdir(parents=True)
    (raw / "Example.jsonl").write_text(
        '{"title": "Policy update", "link": "https://example.com/raw", '
        '"summary": "text", "published": "2026-10-01T00:00:00+00:00", '
        '"source": "Example", "category": "policy", "matched_entities": {}, '
        '"logged_at": "2026-10-01T01:00:00+00:00"}\n',
        encoding="utf-8",
    )
    before = pointer.read_bytes()

    working = resolve_writable_database(pointer, raw_data_dir=tmp_path / "raw")

    assert working != pointer
    assert working.name == "radar_data.duckdb"
    assert pointer.read_bytes() == before
    connection = connect_readonly(working)
    try:
        count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()
    finally:
        connection.close()
    assert count is not None
    assert int(count[0]) == 1


def test_export_keeps_small_snapshot_under_budget(tmp_path: Path) -> None:
    db_path = tmp_path / "radar_data.duckdb"
    now = datetime.now(UTC)
    _fill(
        db_path,
        [
            _article("https://example.com/old", published=now - timedelta(days=2)),
            _article("https://example.com/new", published=now),
        ],
    )

    result = export_articles_parquet(db_path, max_bytes=PARQUET_MAX_BYTES)

    parquet_path = result["parquet_path"]
    assert isinstance(parquet_path, str)
    size = Path(parquet_path).stat().st_size
    assert size < PARQUET_MAX_BYTES
    assert result["truncated"] is False
    assert result["overflow_path"] is None
    assert result["rows_kept"] == 2


def test_export_sends_older_rows_to_overflow(tmp_path: Path) -> None:
    db_path = tmp_path / "radar_data.duckdb"
    now = datetime.now(UTC)
    blob = base64.b64encode(os.urandom(60_000)).decode("ascii")
    _fill(
        db_path,
        [
            _article("https://example.com/old", published=now - timedelta(days=3), summary=blob),
            _article("https://example.com/new", published=now, summary=blob + "tail"),
        ],
    )
    one = tmp_path / "one.duckdb"
    _fill(one, [_article("https://example.com/new", published=now, summary=blob + "tail")])
    one_export = export_articles_parquet(
        one, parquet_root=tmp_path / "one-parquet", max_bytes=PARQUET_MAX_BYTES
    )
    one_size = int(one_export["parquet_bytes"])
    budget = one_size + 64

    result = export_articles_parquet(
        db_path,
        parquet_root=tmp_path / "parquet",
        overflow_dir=tmp_path / "release",
        max_bytes=budget,
    )

    assert result["truncated"] is True
    assert int(result["parquet_bytes"]) < budget
    assert int(result["rows_kept"]) >= 1
    assert int(result["rows_overflow"]) >= 1
    assert int(result["rows_kept"]) + int(result["rows_overflow"]) == 2
    overflow = result["overflow_path"]
    assert isinstance(overflow, str)
    assert Path(overflow).is_file()
    assert (tmp_path / "release" / "UPLOAD").read_text(encoding="utf-8").strip() == (
        "articles-overflow.parquet"
    )
    rolling = tmp_path / "parquet" / "articles.parquet"
    check = duckdb.connect()
    try:
        links = {
            row[0]
            for row in check.execute("SELECT link FROM read_parquet(?)", [str(rolling)]).fetchall()
        }
    finally:
        check.close()
    assert "https://example.com/new" in links


def test_cleanup_parquet_snapshots_keeps_duckdb_files(tmp_path: Path) -> None:
    today = datetime(2026, 10, 16, tzinfo=UTC).date()
    old_parquet = tmp_path / "2020-01-01.parquet"
    old_parquet.write_bytes(b"PAR1")
    duck = tmp_path / "2020-01-01.duckdb"
    duck.write_text("pointer", encoding="utf-8")
    recent = tmp_path / f"{today.isoformat()}.parquet"
    recent.write_bytes(b"PAR1")

    removed = cleanup_parquet_snapshots(tmp_path, keep_days=30, today=today)

    assert removed == 1
    assert not old_parquet.exists()
    assert duck.exists()
    assert recent.exists()


def test_storage_policy_does_not_delete_duckdb_snapshots(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    db_path = data / "radar_data.duckdb"
    _fill(db_path, [_article("https://example.com/a", published=datetime.now(UTC))])
    daily = data / "daily"
    daily.mkdir()
    historical = daily / "2026-09-13.duckdb"
    historical.write_text(_POINTER, encoding="utf-8")

    result = apply_date_storage_policy(
        database_path=db_path,
        raw_data_dir=tmp_path / "raw",
        report_dir=tmp_path / "reports",
        keep_raw_days=30,
        keep_report_days=30,
        snapshot_db=True,
        parquet_root=data / "parquet",
    )

    assert historical.read_text(encoding="utf-8") == _POINTER
    assert result["duckdb_snapshots_removed"] == 0
    parquet_path = result["parquet_path"]
    assert isinstance(parquet_path, str)
    assert Path(parquet_path).is_file()
    assert not list(daily.glob("*.parquet"))


def test_lfs_tracking_is_removed_from_checkout_and_attributes() -> None:
    attributes = Path(".gitattributes").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/radar-crawler.yml").read_text(encoding="utf-8")
    active = [
        line
        for line in attributes.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert active
    assert all("filter=lfs" not in line for line in active)
    assert "data/parquet/**" in attributes
    assert "lfs: true" not in workflow
    assert "lfs: false" in workflow
    assert "data/parquet/" in workflow
