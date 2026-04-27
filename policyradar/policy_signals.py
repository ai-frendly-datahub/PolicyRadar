from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .models import Article


_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_CONSULTATION_MARKERS = (
    "public comment",
    "comments due",
    "comment period",
    "request for comments",
    "consultation",
    "notice of proposed rulemaking",
    "입법예고",
    "행정예고",
    "의견수렴",
    "의견 제출",
    "의견제출",
    "공청회",
)
_EFFECTIVE_MARKERS = (
    "effective date",
    "effective on",
    "takes effect",
    "will take effect",
    "comes into force",
    "implementation date",
    "시행일",
    "시행됩니다",
    "시행한다",
    "적용일",
    "적용됩니다",
    "공포일",
)
_PLATFORM_POLICY_MARKERS = (
    "terms of service",
    "user agreement",
    "developer policy",
    "platform policy",
    "app review",
    "acceptable use",
    "community guidelines",
    "약관 개정",
    "이용약관",
    "운영정책",
    "개발자 정책",
    "플랫폼 정책",
)
_CLASSIFICATION_MARKERS = (
    "n2sf",
    "csap",
    "fedramp",
    "fedramp 20x",
    "fips 199",
    "nist csf",
    "csf 2.0",
    "cybersecurity framework",
    "cyber ai profile",
    "국가 망 보안체계",
    "망분리",
    "등급분류",
    "클라우드 보안인증",
    "기계가독",
)
_OFFICIAL_CLASSIFICATION_FRAMEWORKS = {
    "N2SF": ("n2sf", "국가 망 보안체계", "망 보안체계"),
    "CSAP": ("csap", "클라우드 보안인증"),
    "FIPS 199": ("fips 199",),
    "NIST CSF": ("nist csf", "csf 2.0", "cybersecurity framework"),
    "NIST Cyber AI Profile": ("cyber ai profile",),
    "FedRAMP 20x": ("fedramp 20x",),
    "FedRAMP": ("fedramp",),
}
_INTERNAL_OVERLAY_MARKERS = {
    "S-Low": ("s-low", "s low", "s_low"),
    "S-High": ("s-high", "s high", "s_high"),
}
_ENFORCEMENT_MARKERS = {
    "penalty": ("penalty", "fine", "civil money penalty", "과징금", "과태료", "벌금"),
    "settlement": ("settlement", "settled", "consent order", "합의", "조정"),
    "corrective_order": ("corrective order", "injunction", "cease and desist", "시정명령", "시정조치"),
    "sanction": ("sanction", "enforcement action", "제재", "처분"),
}


@dataclass(frozen=True)
class PolicyDates:
    consultation_deadline: str | None
    effective_date: str | None


def _contains_any(text_lower: str, markers: Iterable[str]) -> bool:
    return any(marker in text_lower for marker in markers)


def _format_date(year: int, month: int, day: int) -> str | None:
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _extract_dates(text: str, *, reference_date: datetime | None = None) -> list[str]:
    dates: list[str] = []
    for year, month, day in re.findall(r"(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일", text):
        date_value = _format_date(int(year), int(month), int(day))
        if date_value:
            dates.append(date_value)

    default_year = reference_date.year if reference_date else datetime.now().year
    for month, day in re.findall(r"(?<!\d)(\d{1,2})월\s*(\d{1,2})일", text):
        if re.search(rf"20\d{{2}}년\s*{re.escape(month)}월\s*{re.escape(day)}일", text):
            continue
        date_value = _format_date(default_year, int(month), int(day))
        if date_value:
            dates.append(date_value)

    month_names = "|".join(_MONTHS)
    english_pattern = re.compile(rf"\b({month_names})\s+(\d{{1,2}}),\s*(20\d{{2}})\b", re.IGNORECASE)
    for month_name, day, year in english_pattern.findall(text):
        date_value = _format_date(int(year), _MONTHS[month_name.lower()], int(day))
        if date_value:
            dates.append(date_value)

    return list(dict.fromkeys(dates))


def extract_policy_dates(text: str, *, reference_date: datetime | None = None) -> PolicyDates:
    text_lower = text.lower()
    dates = _extract_dates(text, reference_date=reference_date)
    if not dates:
        return PolicyDates(consultation_deadline=None, effective_date=None)

    consultation_deadline = dates[-1] if _contains_any(text_lower, _CONSULTATION_MARKERS) else None
    effective_date = dates[0] if _contains_any(text_lower, _EFFECTIVE_MARKERS) else None
    return PolicyDates(consultation_deadline=consultation_deadline, effective_date=effective_date)


def extract_enforcement_outcomes(text: str) -> list[str]:
    text_lower = text.lower()
    outcomes: list[str] = []
    for outcome, markers in _ENFORCEMENT_MARKERS.items():
        if _contains_any(text_lower, markers):
            outcomes.append(outcome)
    return outcomes


def extract_security_classification_fields(text: str) -> dict[str, list[str]]:
    text_lower = text.lower()
    if not _contains_any(text_lower, _CLASSIFICATION_MARKERS):
        return {}

    fields: dict[str, list[str]] = {}
    frameworks: list[str] = []
    for framework, markers in _OFFICIAL_CLASSIFICATION_FRAMEWORKS.items():
        if framework == "FedRAMP" and "fedramp 20x" in text_lower:
            continue
        if _contains_any(text_lower, markers):
            frameworks.append(framework)
    if frameworks:
        fields["SecurityFramework"] = list(dict.fromkeys(frameworks))

    official_grades = _extract_official_security_grades(text)
    if official_grades:
        fields["OfficialSecurityGrade"] = official_grades

    overlays = [
        overlay
        for overlay, markers in _INTERNAL_OVERLAY_MARKERS.items()
        if _contains_any(text_lower, markers)
    ]
    if overlays:
        fields["InternalOperationalOverlay"] = overlays
    return fields


def classify_policy_events(text: str) -> list[str]:
    text_lower = text.lower()
    dates = extract_policy_dates(text)
    outcomes = extract_enforcement_outcomes(text)
    events: list[str] = []
    if dates.consultation_deadline:
        events.append("public_consultation")
    if outcomes:
        events.append("enforcement_action")
    if dates.effective_date:
        events.append("policy_effective_date")
    if _contains_any(text_lower, _PLATFORM_POLICY_MARKERS):
        events.append("platform_policy_change")
    if _contains_any(text_lower, _CLASSIFICATION_MARKERS):
        events.append("security_classification_framework")
    return list(dict.fromkeys(events))


def _append_unique(mapping: dict[str, list[str]], key: str, values: Iterable[str]) -> None:
    existing = mapping.setdefault(key, [])
    for value in values:
        if value and value not in existing:
            existing.append(value)


def enrich_policy_operational_fields(articles: Iterable[Article]) -> list[Article]:
    enriched: list[Article] = []
    for article in articles:
        text = f"{article.title} {article.summary}"
        dates = extract_policy_dates(text, reference_date=article.published)
        outcomes = extract_enforcement_outcomes(text)
        events = classify_policy_events(text)
        classification_fields = extract_security_classification_fields(text)

        matched = dict(article.matched_entities)
        if dates.consultation_deadline:
            _append_unique(matched, "ConsultationDeadline", [dates.consultation_deadline])
        if dates.effective_date:
            _append_unique(matched, "PolicyEffectiveDate", [dates.effective_date])
        if outcomes:
            _append_unique(matched, "EnforcementOutcome", outcomes)
        for key, values in classification_fields.items():
            _append_unique(matched, key, values)
        if events:
            _append_unique(matched, "OperationalEvent", events)
        article.matched_entities = matched
        enriched.append(article)
    return enriched


def _extract_official_security_grades(text: str) -> list[str]:
    text_lower = text.lower()
    grades: list[str] = []
    if "c/s/o" in text_lower:
        grades.extend(["C", "S", "O"])
    if "c·s·o" in text_lower:
        grades.extend(["C", "S", "O"])
    for grade in ("C", "S", "O"):
        if re.search(rf"(?<![A-Za-z]){grade}(?![A-Za-z])\s*(?:등급|grade)", text, re.IGNORECASE):
            grades.append(grade)
    return list(dict.fromkeys(grades))
