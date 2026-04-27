from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from policyradar.models import Article, CategoryConfig, Source
from policyradar.quality_report import (
    build_quality_report,
    quality_lookback_days,
    write_quality_report,
)


def _source(name: str, event_model: str, sla_days: int | None = None) -> Source:
    config: dict[str, object] = {"event_model": event_model}
    if sla_days is not None:
        config["freshness_sla_days"] = sla_days
    return Source(name=name, type="rss", url=f"https://example.com/{name}", config=config)


def test_build_quality_report_tracks_policy_event_statuses() -> None:
    now = datetime(2026, 4, 12, tzinfo=UTC)
    category = CategoryConfig(
        category_name="policy",
        display_name="Policy",
        sources=[
            _source("Consultation Source", "public_consultation", 1),
            _source("Enforcement Source", "enforcement_action", 1),
            _source("Missing Platform", "platform_policy_change", 2),
            _source("Framework Source", "security_classification_framework", 7),
            _source("News Source", "regulatory_guidance", 7),
        ],
        entities=[],
    )
    articles = [
        Article(
            title="Public comment on privacy rule",
            link="https://example.com/consultation",
            summary="Comments due by April 30, 2026.",
            published=now - timedelta(hours=6),
            collected_at=now,
            source="Consultation Source",
            category="policy",
            matched_entities={
                "ConsultationDeadline": ["2026-04-30"],
                "OperationalEvent": ["public_consultation"],
            },
        ),
        Article(
            title="Agency announces civil money penalty",
            link="https://example.com/enforcement",
            summary="The agency announced a fine and consent order.",
            published=now - timedelta(days=3),
            collected_at=now,
            source="Enforcement Source",
            category="policy",
            matched_entities={
                "EnforcementOutcome": ["penalty", "settlement"],
                "OperationalEvent": ["enforcement_action"],
            },
        ),
        Article(
            title="N2SF guidance update",
            link="https://example.com/n2sf",
            summary="N2SF and FIPS 199 policy framework update.",
            published=now - timedelta(days=1),
            collected_at=now,
            source="Framework Source",
            category="policy",
            matched_entities={
                "OperationalEvent": ["security_classification_framework"],
                "SecurityFramework": ["N2SF", "FIPS 199"],
                "OfficialSecurityGrade": ["C", "S", "O"],
                "InternalOperationalOverlay": ["S-Low"],
            },
        ),
        Article(
            title="General policy news",
            link="https://example.com/news",
            summary="Policy context without an operational event.",
            published=now,
            collected_at=now,
            source="News Source",
            category="policy",
        ),
    ]

    report = build_quality_report(
        category=category,
        articles=articles,
        errors=["Enforcement Source: timeout after retry"],
        quality_config={
            "data_quality": {
                "quality_outputs": {
                    "tracked_event_models": [
                        "public_consultation",
                        "enforcement_action",
                        "policy_effective_date",
                        "platform_policy_change",
                        "security_classification_framework",
                    ]
                }
            }
        },
        generated_at=now,
    )

    assert report["summary"]["fresh_sources"] == 2
    assert report["summary"]["stale_sources"] == 1
    assert report["summary"]["missing_sources"] == 1
    assert report["summary"]["not_tracked_sources"] == 1
    assert report["summary"]["public_consultation_events"] == 1
    assert report["summary"]["enforcement_action_events"] == 1
    assert report["summary"]["security_classification_framework_events"] == 1
    assert report["summary"]["collection_error_count"] == 1
    assert report["summary"]["validation_error_count"] == 0
    assert report["summary"]["fresh_policy_events"] == 2
    assert report["summary"]["stale_policy_events"] == 1
    assert report["summary"]["undated_policy_events"] == 0
    assert report["summary"]["unique_policy_event_key_count"] == 3
    assert report["summary"]["events_with_evidence_url"] == 3
    assert report["summary"]["security_framework_official_scope_events"] == 1
    assert "do not replace official N2SF C/S/O grading" in report["classification_scope_note"]

    statuses = {row["source"]: row["status"] for row in report["sources"]}
    assert statuses == {
        "Consultation Source": "fresh",
        "Enforcement Source": "stale",
        "Missing Platform": "missing",
        "Framework Source": "fresh",
        "News Source": "not_tracked",
    }
    consultation_event = next(
        row for row in report["events"] if row["event_model"] == "public_consultation"
    )
    assert consultation_event["consultation_deadline"] == "2026-04-30"
    assert consultation_event["event_status"] == "fresh"
    assert consultation_event["event_age_days"] == 0
    assert consultation_event["policy_event_key"].startswith(
        "public-consultation:consultation-source:2026-04-30"
    )
    assert consultation_event["evidence_url_present"] is True
    enforcement_event = next(
        row for row in report["events"] if row["event_model"] == "enforcement_action"
    )
    assert enforcement_event["enforcement_outcomes"] == ["penalty", "settlement"]
    assert enforcement_event["event_status"] == "stale"
    framework_event = next(
        row
        for row in report["events"]
        if row["event_model"] == "security_classification_framework"
    )
    assert framework_event["classification_scope"] == (
        "official_framework_signal_not_internal_grade"
    )
    assert framework_event["security_frameworks"] == ["N2SF", "FIPS 199"]
    assert framework_event["official_security_grades"] == ["C", "S", "O"]
    assert framework_event["internal_operational_overlays"] == ["S-Low"]


def test_build_quality_report_attaches_bracket_prefixed_source_errors() -> None:
    now = datetime(2026, 4, 12, tzinfo=UTC)
    disabled = Source(
        name="Legacy RSS",
        type="rss",
        url="https://example.com/legacy.xml",
        enabled=False,
        config={
            "event_model": "public_consultation",
            "disabled_reason": "legacy_rss_forbidden_403",
            "required_before_enable": ["stable_official_feed"],
        },
    )
    category = CategoryConfig(
        category_name="policy",
        display_name="Policy",
        sources=[_source("EPA Regulations", "public_consultation"), disabled],
        entities=[],
    )

    report = build_quality_report(
        category=category,
        articles=[],
        errors=[
            "[EPA Regulations] Request failed: 405 Client Error",
            "Legacy RSS: Source disabled (crawl health threshold reached)",
        ],
        quality_config={},
        generated_at=now,
    )

    rows = {row["source"]: row for row in report["sources"]}
    assert rows["EPA Regulations"]["errors"] == [
        "[EPA Regulations] Request failed: 405 Client Error"
    ]
    assert rows["Legacy RSS"]["status"] == "skipped_disabled"
    assert rows["Legacy RSS"]["tracked"] is False
    assert rows["Legacy RSS"]["disabled_reason"] == "legacy_rss_forbidden_403"
    assert rows["Legacy RSS"]["required_before_enable"] == ["stable_official_feed"]


def test_build_quality_report_excludes_disabled_sources_from_tracking_and_events() -> None:
    now = datetime(2026, 4, 12, tzinfo=UTC)
    active = _source("Active Feed", "public_consultation", 7)
    disabled = Source(
        name="Disabled Feed",
        type="rss",
        url="https://example.com/disabled.xml",
        enabled=False,
        config={
            "event_model": "public_consultation",
            "freshness_sla_days": 7,
            "disabled_reason": "blocked_403",
        },
    )
    category = CategoryConfig(
        category_name="policy",
        display_name="Policy",
        sources=[active, disabled],
        entities=[],
    )
    articles = [
        Article(
            title="Active public comment",
            link="https://example.com/active",
            summary="Comments due by April 30, 2026.",
            published=now,
            collected_at=now,
            source="Active Feed",
            category="policy",
            matched_entities={
                "OperationalEvent": ["public_consultation"],
                "ConsultationDeadline": ["2026-04-30"],
            },
        ),
        Article(
            title="Disabled public comment",
            link="https://example.com/disabled",
            summary="Comments due by April 30, 2026.",
            published=now,
            collected_at=now,
            source="Disabled Feed",
            category="policy",
            matched_entities={
                "OperationalEvent": ["public_consultation"],
                "ConsultationDeadline": ["2026-04-30"],
            },
        ),
    ]

    report = build_quality_report(
        category=category,
        articles=articles,
        quality_config={},
        generated_at=now,
    )

    rows = {row["source"]: row for row in report["sources"]}
    assert report["summary"]["tracked_sources"] == 1
    assert report["summary"]["skipped_disabled_sources"] == 1
    assert rows["Disabled Feed"]["tracked"] is False
    assert rows["Disabled Feed"]["status"] == "skipped_disabled"
    assert [row["source"] for row in report["events"]] == ["Active Feed"]


def test_build_quality_report_separates_validation_errors_from_collection_errors() -> None:
    now = datetime(2026, 4, 12, tzinfo=UTC)
    category = CategoryConfig(
        category_name="policy",
        display_name="Policy",
        sources=[_source("SEC Press Releases", "enforcement_action", 3)],
        entities=[],
    )

    report = build_quality_report(
        category=category,
        articles=[],
        errors=["SEC Press Releases: Request failed"],
        validation_errors=["https://example.com/article: summary is missing"],
        quality_config={},
        generated_at=now,
    )

    assert report["summary"]["collection_error_count"] == 1
    assert report["summary"]["validation_error_count"] == 1
    assert report["errors"] == ["SEC Press Releases: Request failed"]
    assert report["validation_errors"] == [
        "https://example.com/article: summary is missing"
    ]
    assert report["sources"][0]["errors"] == ["SEC Press Releases: Request failed"]


def test_quality_lookback_days_uses_enabled_tracked_source_slas() -> None:
    disabled = Source(
        name="Disabled Framework",
        type="rss",
        url="https://example.com/disabled.xml",
        enabled=False,
        config={
            "event_model": "security_classification_framework",
            "freshness_sla_days": 90,
        },
    )
    category = CategoryConfig(
        category_name="policy",
        display_name="Policy",
        sources=[
            _source("Short SLA", "public_consultation", 3),
            _source("Framework Feed", "security_classification_framework", 45),
            disabled,
            _source("Guidance Feed", "regulatory_guidance", 120),
        ],
        entities=[],
    )

    assert quality_lookback_days(category=category, quality_config={}, minimum_days=7) == 46


def test_build_quality_report_normalizes_legacy_security_framework_entity_hits() -> None:
    now = datetime(2026, 4, 12, tzinfo=UTC)
    category = CategoryConfig(
        category_name="policy",
        display_name="Policy",
        sources=[_source("KISA 보안공지", "security_classification_framework", 7)],
        entities=[],
    )

    report = build_quality_report(
        category=category,
        articles=[
            Article(
                title="2026년 국가 망 보안체계(N2SF) 도입 지원사업 모집 공고",
                link="https://example.com/n2sf",
                summary="N2SF 도입 지원사업 공고",
                published=now,
                collected_at=now,
                source="KISA 보안공지",
                category="policy",
                matched_entities={"SecurityClassificationFramework": ["n2sf"]},
            )
        ],
        quality_config={},
        generated_at=now,
    )

    event = report["events"][0]
    assert event["event_model"] == "security_classification_framework"
    assert event["security_frameworks"] == ["N2SF"]


def test_write_quality_report_writes_latest_and_dated_files(tmp_path) -> None:
    report = {
        "category": "policy",
        "generated_at": "2026-04-12T03:04:05+00:00",
        "classification_scope_note": "note",
        "summary": {},
        "sources": [],
        "events": [],
        "errors": [],
    }

    paths = write_quality_report(report, output_dir=tmp_path, category_name="policy")

    assert paths["latest"] == tmp_path / "policy_quality.json"
    assert paths["dated"] == tmp_path / "policy_20260412_quality.json"
    assert json.loads(paths["latest"].read_text(encoding="utf-8")) == report
    assert json.loads(paths["dated"].read_text(encoding="utf-8")) == report
