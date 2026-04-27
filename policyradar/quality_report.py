from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Article, CategoryConfig, Source


TRACKED_EVENT_MODEL_ORDER = [
    "public_consultation",
    "enforcement_action",
    "policy_effective_date",
    "platform_policy_change",
    "security_classification_framework",
]
TRACKED_EVENT_MODELS = set(TRACKED_EVENT_MODEL_ORDER)


def build_quality_report(
    *,
    category: CategoryConfig,
    articles: Iterable[Article],
    errors: Iterable[str] | None = None,
    validation_errors: Iterable[str] | None = None,
    quality_config: Mapping[str, object] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated = _as_utc(generated_at or datetime.now(UTC))
    articles_list = list(articles)
    errors_list = [str(error) for error in (errors or [])]
    validation_errors_list = [str(error) for error in (validation_errors or [])]
    quality = _dict(quality_config or {}, "data_quality")
    freshness_sla = _dict(quality, "freshness_sla")
    tracked_event_models = _tracked_event_models(quality)

    source_rows = [
        _build_source_row(
            source=source,
            articles=articles_list,
            errors=errors_list,
            freshness_sla=freshness_sla,
            tracked_event_models=tracked_event_models,
            generated_at=generated,
        )
        for source in category.sources
    ]
    events = _build_event_rows(
        sources=category.sources,
        articles=articles_list,
        tracked_event_models=tracked_event_models,
        freshness_sla=freshness_sla,
        generated_at=generated,
    )

    status_counts = Counter(str(row["status"]) for row in source_rows)
    event_counts = Counter(str(row["event_model"]) for row in events)
    event_status_counts = Counter(str(row["event_status"]) for row in events)
    event_keys = {
        str(row["policy_event_key"])
        for row in events
        if str(row.get("policy_event_key") or "")
    }
    summary = {
        "total_sources": len(source_rows),
        "tracked_sources": sum(1 for row in source_rows if row["tracked"]),
        "fresh_sources": status_counts.get("fresh", 0),
        "stale_sources": status_counts.get("stale", 0),
        "missing_sources": status_counts.get("missing", 0),
        "unknown_event_date_sources": status_counts.get("unknown_event_date", 0),
        "not_tracked_sources": status_counts.get("not_tracked", 0),
        "skipped_disabled_sources": status_counts.get("skipped_disabled", 0),
        "collection_error_count": len(errors_list),
        "validation_error_count": len(validation_errors_list),
        "fresh_policy_events": event_status_counts.get("fresh", 0),
        "stale_policy_events": event_status_counts.get("stale", 0),
        "undated_policy_events": event_status_counts.get("unknown_event_date", 0),
        "unique_policy_event_key_count": len(event_keys),
        "events_with_evidence_url": sum(1 for row in events if row.get("evidence_url")),
        "security_framework_official_scope_events": sum(
            1
            for row in events
            if row.get("classification_scope")
            == "official_framework_signal_not_internal_grade"
        ),
    }
    for event_model in TRACKED_EVENT_MODEL_ORDER:
        summary[f"{event_model}_events"] = event_counts.get(event_model, 0)

    return {
        "category": category.category_name,
        "generated_at": generated.isoformat(),
        "classification_scope_note": (
            "Security classification framework rows track public policy signals. "
            "They do not replace official N2SF C/S/O grading; internal S-Low/S-High "
            "values remain operational overlays only."
        ),
        "summary": summary,
        "sources": source_rows,
        "events": events,
        "errors": errors_list,
        "validation_errors": validation_errors_list,
    }


def write_quality_report(
    report: dict[str, Any],
    *,
    output_dir: Path,
    category_name: str,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = _parse_datetime(str(report.get("generated_at") or "")) or datetime.now(UTC)
    date_stamp = _as_utc(generated_at).strftime("%Y%m%d")

    latest_path = output_dir / f"{category_name}_quality.json"
    dated_path = output_dir / f"{category_name}_{date_stamp}_quality.json"
    encoded = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    latest_path.write_text(encoded + "\n", encoding="utf-8")
    dated_path.write_text(encoded + "\n", encoding="utf-8")
    return {"latest": latest_path, "dated": dated_path}


def quality_lookback_days(
    *,
    category: CategoryConfig,
    quality_config: Mapping[str, object] | None = None,
    minimum_days: int = 7,
) -> int:
    quality = _dict(quality_config or {}, "data_quality")
    freshness_sla = _dict(quality, "freshness_sla")
    tracked_event_models = _tracked_event_models(quality)
    days = [max(1, minimum_days)]
    for source in category.sources:
        if not source.enabled:
            continue
        event_model = _source_event_model(source)
        if event_model not in tracked_event_models:
            continue
        sla_days = _source_sla_days(source, event_model, freshness_sla)
        if sla_days is not None:
            days.append(max(1, sla_days + 1))
    return max(days)


def _build_source_row(
    *,
    source: Source,
    articles: list[Article],
    errors: list[str],
    freshness_sla: Mapping[str, object],
    tracked_event_models: set[str],
    generated_at: datetime,
) -> dict[str, Any]:
    source_articles = [article for article in articles if article.source == source.name]
    source_errors = _source_errors(source.name, errors)
    event_model = _source_event_model(source)
    tracked = _is_tracked_source(source, event_model, tracked_event_models)
    latest_article = _latest_article(source_articles)
    latest_event_at = _event_datetime(latest_article, source) if latest_article else None
    sla_days = _source_sla_days(source, event_model, freshness_sla)
    age_days = _age_days(generated_at, latest_event_at) if latest_event_at else None
    status = _source_status(
        source=source,
        tracked=tracked,
        article_count=len(source_articles),
        latest_event_at=latest_event_at,
        sla_days=sla_days,
        age_days=age_days,
    )

    matched = latest_article.matched_entities if latest_article else {}
    return {
        "source": source.name,
        "source_type": source.type,
        "enabled": source.enabled,
        "tracked": tracked,
        "event_model": event_model,
        "freshness_sla_days": sla_days,
        "status": status,
        "article_count": len(source_articles),
        "latest_event_at": latest_event_at.isoformat() if latest_event_at else None,
        "age_days": round(age_days, 2) if age_days is not None else None,
        "latest_title": latest_article.title if latest_article else "",
        "latest_url": latest_article.link if latest_article else "",
        "latest_consultation_deadline": _first(matched, "ConsultationDeadline"),
        "latest_policy_effective_date": _first(matched, "PolicyEffectiveDate"),
        "latest_enforcement_outcomes": _list(matched.get("EnforcementOutcome")),
        "latest_operational_events": _list(matched.get("OperationalEvent")),
        "classification_scope": _classification_scope(event_model),
        "disabled_reason": str(source.config.get("disabled_reason") or "").strip(),
        "required_before_enable": _list(source.config.get("required_before_enable")),
        "errors": source_errors,
    }


def _build_event_rows(
    *,
    sources: list[Source],
    articles: list[Article],
    tracked_event_models: set[str],
    freshness_sla: Mapping[str, object],
    generated_at: datetime,
) -> list[dict[str, Any]]:
    sources_by_name = {source.name: source for source in sources}
    rows: list[dict[str, Any]] = []
    for article in articles:
        source = sources_by_name.get(article.source)
        if source is None:
            continue
        if not source.enabled:
            continue
        event_models = _article_event_models(article, source, tracked_event_models)
        if not event_models:
            continue
        for event_model in event_models:
            event_at = _policy_event_datetime(article, source, event_model)
            sla_days = _source_sla_days(source, event_model, freshness_sla)
            age_days = _age_days(generated_at, event_at) if event_at else None
            rows.append(
                {
                    "source": source.name,
                    "event_model": event_model,
                    "title": article.title,
                    "url": article.link,
                    "event_at": event_at.isoformat() if event_at else None,
                    "event_age_days": round(age_days, 2) if age_days is not None else None,
                    "event_freshness_sla_days": sla_days,
                    "event_status": _event_status(
                        event_at=event_at,
                        age_days=age_days,
                        sla_days=sla_days,
                    ),
                    "policy_event_key": _policy_event_key(
                        article=article,
                        source=source,
                        event_model=event_model,
                    ),
                    "consultation_deadline": _first(
                        article.matched_entities, "ConsultationDeadline"
                    ),
                    "policy_effective_date": _first(
                        article.matched_entities, "PolicyEffectiveDate"
                    ),
                    "enforcement_outcomes": _list(
                        article.matched_entities.get("EnforcementOutcome")
                    ),
                    "evidence_url": article.link,
                    "evidence_url_present": bool(article.link),
                    "security_frameworks": _security_frameworks(article),
                    "official_security_grades": _list(
                        article.matched_entities.get("OfficialSecurityGrade")
                    ),
                    "internal_operational_overlays": _list(
                        article.matched_entities.get("InternalOperationalOverlay")
                    ),
                    "classification_scope": _classification_scope(event_model),
                }
            )
    return rows


def _article_event_models(
    article: Article,
    source: Source,
    tracked_event_models: set[str],
) -> list[str]:
    values: set[str] = set()
    source_event_model = _source_event_model(source)
    if source_event_model == "security_classification_framework":
        if _has_security_framework_evidence(article) and source_event_model in tracked_event_models:
            values.add(source_event_model)
    elif source_event_model in tracked_event_models:
        values.add(source_event_model)
    for event_model in _list(article.matched_entities.get("OperationalEvent")):
        if event_model in tracked_event_models:
            values.add(event_model)
    return [event_model for event_model in TRACKED_EVENT_MODEL_ORDER if event_model in values]


def _is_tracked_source(
    source: Source,
    event_model: str,
    tracked_event_models: set[str],
) -> bool:
    return source.enabled and event_model in tracked_event_models


def _source_status(
    *,
    source: Source,
    tracked: bool,
    article_count: int,
    latest_event_at: datetime | None,
    sla_days: int | None,
    age_days: float | None,
) -> str:
    if not source.enabled:
        return "skipped_disabled"
    if not tracked:
        return "not_tracked"
    if article_count == 0:
        return "missing"
    if latest_event_at is None or age_days is None:
        return "unknown_event_date"
    if sla_days is not None and age_days > sla_days:
        return "stale"
    return "fresh"


def _has_security_framework_evidence(article: Article) -> bool:
    matched = article.matched_entities
    return any(
        _list(matched.get(key))
        for key in (
            "SecurityFramework",
            "SecurityClassificationFramework",
            "OfficialSecurityGrade",
            "InternalOperationalOverlay",
        )
    ) or "security_classification_framework" in _list(matched.get("OperationalEvent"))


def _security_frameworks(article: Article) -> list[str]:
    direct = _list(article.matched_entities.get("SecurityFramework"))
    if direct:
        return direct
    keyword_hits = _list(article.matched_entities.get("SecurityClassificationFramework"))
    frameworks: list[str] = []
    for keyword in keyword_hits:
        normalized = keyword.lower()
        if "n2sf" in normalized or "국가 망 보안체계" in keyword or "망분리" in keyword:
            frameworks.append("N2SF")
        if "csap" in normalized or "클라우드 보안인증" in keyword:
            frameworks.append("CSAP")
        if "fips 199" in normalized:
            frameworks.append("FIPS 199")
        if (
            "nist csf" in normalized
            or "csf 2.0" in normalized
            or "cybersecurity framework" in normalized
        ):
            frameworks.append("NIST CSF")
        if "cyber ai profile" in normalized:
            frameworks.append("NIST Cyber AI Profile")
        if "fedramp 20x" in normalized:
            frameworks.append("FedRAMP 20x")
        elif "fedramp" in normalized:
            frameworks.append("FedRAMP")
    return list(dict.fromkeys(frameworks))


def _tracked_event_models(quality: Mapping[str, object]) -> set[str]:
    outputs = _dict(quality, "quality_outputs")
    output_models = _string_set(outputs.get("tracked_event_models"))
    if output_models:
        return output_models & TRACKED_EVENT_MODELS or set(TRACKED_EVENT_MODELS)
    configured_models = _string_set(quality.get("event_models"))
    return configured_models & TRACKED_EVENT_MODELS or set(TRACKED_EVENT_MODELS)


def _source_event_model(source: Source) -> str:
    raw = source.config.get("event_model")
    return str(raw).strip() if raw is not None else ""


def _source_sla_days(
    source: Source,
    event_model: str,
    freshness_sla: Mapping[str, object],
) -> int | None:
    raw_source_sla = source.config.get("freshness_sla_days")
    parsed_source_sla = _as_int(raw_source_sla)
    if parsed_source_sla is not None:
        return parsed_source_sla
    model_sla = freshness_sla.get(event_model)
    if isinstance(model_sla, Mapping):
        return _as_int(model_sla.get("max_age_days"))
    return None


def _latest_article(articles: list[Article]) -> Article | None:
    dated: list[tuple[datetime, Article]] = []
    undated: list[Article] = []
    for article in articles:
        article_time = article.published or article.collected_at
        event_at = _as_utc(article_time) if article_time else None
        if event_at:
            dated.append((event_at, article))
        else:
            undated.append(article)
    if dated:
        return max(dated, key=lambda item: item[0])[1]
    return undated[0] if undated else None


def _event_datetime(article: Article | None, source: Source) -> datetime | None:
    if article is None:
        return None
    field = str(
        source.config.get("observed_date_field")
        or source.config.get("event_date_field")
        or ""
    )
    if field == "collected_at":
        return _as_utc(article.collected_at) if article.collected_at else None
    article_time = article.published or article.collected_at
    return _as_utc(article_time) if article_time else None


def _policy_event_datetime(
    article: Article | None,
    source: Source,
    event_model: str,
) -> datetime | None:
    if article is None:
        return None
    if event_model == "public_consultation":
        deadline = _parse_datetime(_first(article.matched_entities, "ConsultationDeadline"))
        if deadline is not None:
            return deadline
    if event_model in {"policy_effective_date", "platform_policy_change"}:
        effective_date = _parse_datetime(_first(article.matched_entities, "PolicyEffectiveDate"))
        if effective_date is not None:
            return effective_date
    return _event_datetime(article, source)


def _event_status(
    *,
    event_at: datetime | None,
    age_days: float | None,
    sla_days: int | None,
) -> str:
    if event_at is None or age_days is None:
        return "unknown_event_date"
    if sla_days is not None and age_days > sla_days:
        return "stale"
    return "fresh"


def _policy_event_key(*, article: Article, source: Source, event_model: str) -> str:
    date_part = (
        _first(article.matched_entities, "ConsultationDeadline")
        if event_model == "public_consultation"
        else _first(article.matched_entities, "PolicyEffectiveDate")
    )
    if event_model == "enforcement_action":
        date_part = article.published.date().isoformat() if article.published else ""
    key_parts = [
        event_model,
        source.country,
        source.name,
        date_part,
        ",".join(_list(article.matched_entities.get("EnforcementOutcome"))),
        ",".join(_list(article.matched_entities.get("SecurityFramework"))),
        article.title or article.link,
    ]
    return ":".join(_normalize_key_text(part) for part in key_parts if str(part).strip())


def _classification_scope(event_model: str) -> str:
    if event_model == "security_classification_framework":
        return "official_framework_signal_not_internal_grade"
    return ""


def _source_errors(source_name: str, errors: list[str]) -> list[str]:
    colon_prefix = f"{source_name}:"
    bracket_prefix = f"[{source_name}]"
    return [
        error
        for error in errors
        if error.startswith(colon_prefix) or error.startswith(bracket_prefix)
    ]


def _first(mapping: Mapping[str, list[str]], key: str) -> str:
    values = _list(mapping.get(key))
    return values[0] if values else ""


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _string_set(value: object) -> set[str]:
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, tuple | set):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, str) and value.strip():
        return {value.strip()}
    return set()


def _normalize_key_text(value: object) -> str:
    text = str(value).strip().lower()
    normalized = "".join(char if char.isalnum() else "-" for char in text)
    return "-".join(part for part in normalized.split("-") if part)


def _age_days(generated_at: datetime, event_at: datetime) -> float:
    return max(0.0, (_as_utc(generated_at) - _as_utc(event_at)).total_seconds() / 86400)


def _dict(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = mapping.get(key)
    return value if isinstance(value, Mapping) else {}


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None
