from __future__ import annotations

from datetime import UTC, datetime

from policyradar.models import Article
from policyradar.policy_signals import (
    classify_policy_events,
    enrich_policy_operational_fields,
    extract_enforcement_outcomes,
    extract_policy_dates,
    extract_security_classification_fields,
)


def test_extract_policy_dates_with_korean_consultation_deadline() -> None:
    dates = extract_policy_dates(
        "입법예고 의견 제출은 2026년 4월 30일까지 받습니다.",
        reference_date=datetime(2026, 4, 1, tzinfo=UTC),
    )

    assert dates.consultation_deadline == "2026-04-30"
    assert dates.effective_date is None


def test_extract_policy_dates_with_english_effective_date() -> None:
    dates = extract_policy_dates(
        "The final rule takes effect on May 1, 2026.",
        reference_date=datetime(2026, 4, 1, tzinfo=UTC),
    )

    assert dates.consultation_deadline is None
    assert dates.effective_date == "2026-05-01"


def test_extract_policy_dates_does_not_guess_without_policy_context() -> None:
    dates = extract_policy_dates(
        "The agency published a research note on May 1, 2026.",
        reference_date=datetime(2026, 4, 1, tzinfo=UTC),
    )

    assert dates.consultation_deadline is None
    assert dates.effective_date is None


def test_extract_enforcement_outcomes_maps_penalty_and_order_terms() -> None:
    outcomes = extract_enforcement_outcomes(
        "The agency announced a consent order and civil money penalty."
    )

    assert outcomes == ["penalty", "settlement"]


def test_classify_policy_events_detects_framework_and_platform_policy() -> None:
    events = classify_policy_events(
        "N2SF and FedRAMP 20x guidance updates the platform policy effective on May 1, 2026."
    )

    assert events == [
        "policy_effective_date",
        "platform_policy_change",
        "security_classification_framework",
    ]


def test_extract_security_classification_fields_separates_official_and_overlay() -> None:
    fields = extract_security_classification_fields(
        "N2SF C/S/O 등급분류와 FedRAMP 20x 검증 흐름은 S-Low 운영 오버레이와 분리한다."
    )

    assert fields["SecurityFramework"] == ["N2SF", "FedRAMP 20x"]
    assert fields["OfficialSecurityGrade"] == ["C", "S", "O"]
    assert fields["InternalOperationalOverlay"] == ["S-Low"]


def test_extract_security_classification_fields_tracks_nist_csf_signals() -> None:
    fields = extract_security_classification_fields(
        "NIST published a Cybersecurity Framework Profile for Artificial Intelligence "
        "(Cyber AI Profile) and CSF 2.0 updates."
    )

    assert fields["SecurityFramework"] == ["NIST CSF", "NIST Cyber AI Profile"]


def test_enrich_policy_operational_fields_adds_matched_entities() -> None:
    article = Article(
        title="Public comment on privacy rule",
        link="https://example.com/policy",
        summary=(
            "Comments due by April 30, 2026. The agency announced a fine and "
            "consent order."
        ),
        published=datetime(2026, 4, 1, tzinfo=UTC),
        source="GovInfo Federal Register",
        category="policy",
        matched_entities={"Regulation": ["rule"]},
    )

    enriched = enrich_policy_operational_fields([article])[0]

    assert enriched.matched_entities["ConsultationDeadline"] == ["2026-04-30"]
    assert enriched.matched_entities["EnforcementOutcome"] == ["penalty", "settlement"]
    assert enriched.matched_entities["OperationalEvent"] == [
        "public_consultation",
        "enforcement_action",
    ]
