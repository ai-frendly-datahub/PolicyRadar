from __future__ import annotations

from datetime import UTC, datetime

from policyradar.models import Article, CategoryConfig
from policyradar.reporter import generate_report


def test_generate_report_injects_policy_quality_panel(tmp_path, monkeypatch) -> None:
    fixed_now = datetime(2026, 4, 12, 9, 30, tzinfo=UTC)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("radar_core.report_utils.datetime", FixedDateTime)

    output_path = tmp_path / "reports" / "policy_report.html"
    category = CategoryConfig(
        category_name="policy",
        display_name="Policy",
        sources=[],
        entities=[],
    )
    article = Article(
        title="Public comment on privacy rule",
        link="https://example.com/consultation",
        summary="Comments due by April 30, 2026.",
        published=fixed_now,
        collected_at=fixed_now,
        source="GovInfo Federal Register",
        category="policy",
        matched_entities={"ConsultationDeadline": ["2026-04-30"]},
    )
    quality_report = {
        "classification_scope_note": (
            "Security classification framework rows track public policy signals."
        ),
        "summary": {
            "fresh_sources": 1,
            "stale_sources": 1,
            "missing_sources": 0,
            "skipped_disabled_sources": 1,
            "collection_error_count": 1,
            "public_consultation_events": 1,
            "enforcement_action_events": 1,
            "policy_effective_date_events": 0,
            "platform_policy_change_events": 0,
            "security_classification_framework_events": 1,
            "fresh_policy_events": 1,
            "stale_policy_events": 1,
            "unique_policy_event_key_count": 2,
            "events_with_evidence_url": 2,
        },
        "sources": [
            {
                "source": "SEC Press Releases",
                "status": "stale",
                "event_model": "enforcement_action",
                "age_days": 3,
                "disabled_reason": "",
                "errors": ["SEC Press Releases: timeout"],
            },
            {
                "source": "Legacy RSS",
                "status": "skipped_disabled",
                "event_model": "public_consultation",
                "age_days": None,
                "disabled_reason": "legacy_rss_forbidden_403",
                "errors": [],
            }
        ],
        "events": [
            {
                "source": "GovInfo Federal Register",
                "event_model": "public_consultation",
                "title": "Public comment on privacy rule",
                "consultation_deadline": "2026-04-30",
                "policy_effective_date": "",
                "enforcement_outcomes": [],
                "event_status": "fresh",
                "event_age_days": 0,
                "policy_event_key": "public-consultation:govinfo-federal-register:2026-04-30:privacy-rule",
                "evidence_url": "https://example.com/consultation",
                "security_frameworks": [],
                "official_security_grades": [],
                "internal_operational_overlays": [],
            },
            {
                "source": "NIST News",
                "event_model": "security_classification_framework",
                "title": "N2SF guidance update",
                "consultation_deadline": "",
                "policy_effective_date": "",
                "enforcement_outcomes": [],
                "event_status": "fresh",
                "event_age_days": 1,
                "policy_event_key": "security-classification-framework:nist-news:n2sf-guidance-update",
                "evidence_url": "https://example.com/n2sf",
                "security_frameworks": ["N2SF"],
                "official_security_grades": ["C", "S", "O"],
                "internal_operational_overlays": ["S-Low"],
            },
        ],
    }

    generate_report(
        category=category,
        articles=[article],
        output_path=output_path,
        stats={"sources": 1, "collected": 1, "matched": 1, "window_days": 7},
        quality_report=quality_report,
    )

    html = output_path.read_text(encoding="utf-8")
    dated_html = (tmp_path / "reports" / "policy_20260412.html").read_text(
        encoding="utf-8"
    )

    for rendered in (html, dated_html):
        assert rendered == "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
        assert 'id="policy-quality"' in rendered
        assert "Policy Quality" in rendered
        assert "policy_quality.json" in rendered
        assert "SEC Press Releases" in rendered
        assert "collection errors" in rendered
        assert "event keys" in rendered
        assert "legacy_rss_forbidden_403" in rendered
        assert "Public comment on privacy rule" in rendered
        assert "2026-04-30" in rendered
        assert "public policy signals" in rendered
        assert "framework N2SF" in rendered
        assert "official grade C, S, O" in rendered
        assert "overlay S-Low" in rendered
        assert "https://example.com/n2sf" in rendered

    summary = (tmp_path / "reports" / "policy_20260412_summary.json").read_text(
        encoding="utf-8"
    )
    assert '"repo": "PolicyRadar"' in summary
    assert '"ontology_version": "0.1.0"' in summary
    assert '"policy.enforcement_action"' in summary
