from __future__ import annotations

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, List, Tuple, cast

import feedparser
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .models import Article, Source


_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (compatible; PolicyRadarBot/1.0; +https://github.com/zzragida/ai-frendly-datahub)",
}


def _fetch_url_with_retry(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    """Fetch URL with retry logic on transient errors."""
    merged = {**_DEFAULT_HEADERS, **(headers or {})}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def _fetch() -> requests.Response:
        response = requests.get(url, timeout=timeout, headers=merged)
        response.raise_for_status()
        return response

    return _fetch()


def collect_sources(
    sources: List[Source],
    *,
    category: str,
    limit_per_source: int = 30,
    timeout: int = 15,
) -> Tuple[List[Article], List[str]]:
    """Fetch items from all configured sources, returning articles and errors."""
    articles: List[Article] = []
    errors: List[str] = []

    for source in sources:
        try:
            articles.extend(
                _collect_single(source, category=category, limit=limit_per_source, timeout=timeout)
            )
        except Exception as exc:  # noqa: BLE001 - surface errors to the caller
            errors.append(f"{source.name}: {exc}")

    return articles, errors


def _collect_single(
    source: Source,
    *,
    category: str,
    limit: int,
    timeout: int,
) -> List[Article]:
    if source.type.lower() != "rss":
        raise ValueError(
            f"Unsupported source type '{source.type}'. Only 'rss' is supported in the template."
        )

    response = _fetch_url_with_retry(source.url, timeout)

    feed = feedparser.parse(response.content)
    items: List[Article] = []

    for raw_entry in cast(list[object], feed.entries[:limit]):
        entry = _entry_to_dict(raw_entry)
        published = _extract_datetime(entry)
        summary = _entry_str(entry, "summary") or _entry_str(entry, "description")

        items.append(
            Article(
                title=_entry_str(entry, "title").strip() or "(no title)",
                link=_entry_str(entry, "link").strip(),
                summary=summary.strip(),
                published=published,
                source=source.name,
                category=category,
            )
        )

    return items


def _entry_to_dict(entry: object) -> dict[str, object]:
    if isinstance(entry, dict):
        source = cast(dict[object, object], entry)
        return {str(k): v for k, v in source.items()}
    return {}


def _entry_str(entry: dict[str, object], key: str) -> str:
    value = entry.get(key)
    return str(value) if isinstance(value, str) else ""


def _extract_datetime(entry: dict[str, object]) -> datetime | None:
    """Parse a feed entry date into a timezone-aware datetime."""
    published_parsed = entry.get("published_parsed")
    if published_parsed is not None:
        try:
            return datetime.fromtimestamp(
                time.mktime(cast(tuple[Any, ...], published_parsed)), tz=timezone.utc
            )
        except Exception:
            pass
    updated_parsed = entry.get("updated_parsed")
    if updated_parsed is not None:
        try:
            return datetime.fromtimestamp(
                time.mktime(cast(tuple[Any, ...], updated_parsed)), tz=timezone.utc
            )
        except Exception:
            pass

    for key in ("published", "updated", "date"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(str(raw))
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                continue
    return None
