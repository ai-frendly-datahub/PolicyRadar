from __future__ import annotations

from collections.abc import Iterable
from html import escape
from pathlib import Path
from typing import Any, Mapping

from radar_core.ontology import build_summary_ontology_metadata
from radar_core.report_utils import (
    generate_index_html as _core_generate_index_html,
)
from radar_core.report_utils import (
    generate_report as _core_generate_report,
)

from .models import Article, CategoryConfig


def generate_report(
    *,
    category: CategoryConfig,
    articles: Iterable[Article],
    output_path: Path,
    stats: dict[str, int],
    errors: list[str] | None = None,
    store=None,
    quality_report: Mapping[str, Any] | None = None,
) -> Path:
    """Generate HTML report (delegates to radar-core)."""
    articles_list = list(articles)
    plugin_charts = []

    # --- Universal plugins (entity heatmap + source reliability) ---
    try:
        from radar_core.plugins.entity_heatmap import get_chart_config as _heatmap_config

        _heatmap = _heatmap_config(articles=articles_list)
        if _heatmap is not None:
            plugin_charts.append(_heatmap)
    except Exception:
        pass
    try:
        from radar_core.plugins.source_reliability import get_chart_config as _reliability_config

        _reliability = _reliability_config(store=store)
        if _reliability is not None:
            plugin_charts.append(_reliability)
    except Exception:
        pass

    result = _core_generate_report(
        category=category,
        articles=articles_list,
        output_path=output_path,
        stats=stats,
        errors=errors,
        plugin_charts=plugin_charts if plugin_charts else None,
        ontology_metadata=build_summary_ontology_metadata(
            "PolicyRadar",
            category_name=category.category_name,
            search_from=Path(__file__).resolve(),
        ),
    )
    if quality_report:
        _inject_policy_quality_panel(result, quality_report)
        _inject_latest_dated_report_panel(result, category.category_name, quality_report)
    return result


def generate_index_html(
    report_dir: Path,
    summaries_dir: Path | None = None,
) -> Path:
    """Generate index.html (delegates to radar-core)."""
    radar_name = "Policy Radar"
    return _core_generate_index_html(report_dir, radar_name)


def _inject_latest_dated_report_panel(
    output_path: Path,
    category_name: str,
    quality_report: Mapping[str, Any],
) -> None:
    dated_reports = sorted(
        output_path.parent.glob(
            f"{category_name}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].html"
        ),
        key=lambda path: path.stat().st_mtime,
    )
    if dated_reports:
        _inject_policy_quality_panel(dated_reports[-1], quality_report)


def _inject_policy_quality_panel(
    output_path: Path,
    quality_report: Mapping[str, Any],
) -> None:
    if not output_path.exists():
        return
    html = output_path.read_text(encoding="utf-8")
    if 'id="policy-quality"' in html:
        return

    marker = '<section id="entities"'
    if marker not in html:
        return

    panel = _render_policy_quality_panel(quality_report).rstrip()
    rendered = html.replace(marker, panel + "\n      " + marker, 1)
    rendered = "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
    output_path.write_text(rendered, encoding="utf-8")


def _render_policy_quality_panel(quality_report: Mapping[str, Any]) -> str:
    summary = quality_report.get("summary")
    summary_map = summary if isinstance(summary, Mapping) else {}
    sources = [row for row in _list(quality_report.get("sources")) if isinstance(row, Mapping)]
    events = [row for row in _list(quality_report.get("events")) if isinstance(row, Mapping)]
    flagged_sources = [
        row
        for row in sources
        if str(row.get("status")) in {"stale", "missing", "unknown_event_date", "skipped_disabled"}
        or _list(row.get("errors"))
    ][:8]
    highlighted_events = events[:6]
    chips = [
        ("fresh", summary_map.get("fresh_sources", 0)),
        ("stale", summary_map.get("stale_sources", 0)),
        ("missing", summary_map.get("missing_sources", 0)),
        ("disabled", summary_map.get("skipped_disabled_sources", 0)),
        ("collection errors", summary_map.get("collection_error_count", 0)),
        ("consultations", summary_map.get("public_consultation_events", 0)),
        ("enforcement", summary_map.get("enforcement_action_events", 0)),
        ("effective dates", summary_map.get("policy_effective_date_events", 0)),
        ("platform changes", summary_map.get("platform_policy_change_events", 0)),
        ("framework signals", summary_map.get("security_classification_framework_events", 0)),
        ("fresh events", summary_map.get("fresh_policy_events", 0)),
        ("stale events", summary_map.get("stale_policy_events", 0)),
        ("event keys", summary_map.get("unique_policy_event_key_count", 0)),
        ("evidence URLs", summary_map.get("events_with_evidence_url", 0)),
    ]
    chip_html = "\n".join(
        f'<span class="chip"><strong>{escape(label)}</strong> {escape(str(value))}</span>'
        for label, value in chips
    )
    scope_note = escape(str(quality_report.get("classification_scope_note") or ""))
    return f"""
      <section id="policy-quality" class="section" aria-label="Policy quality">
        <div class="section-hd">
          <h2>Policy Quality</h2>
          <div class="right">
            <span class="kbd">policy_quality.json</span>
          </div>
        </div>
        <article class="panel">
          <header class="panel-hd">
            <div>
              <p class="panel-title">Consultation and Enforcement Checks</p>
              <p class="panel-sub">source freshness, event freshness, operational dates, and evidence URLs</p>
            </div>
          </header>
          <div class="panel-bd">
            <div class="row" aria-label="Policy quality summary">
              {chip_html}
            </div>
            <p class="muted small">{scope_note}</p>
            {_render_quality_sources(flagged_sources)}
            {_render_policy_events(highlighted_events)}
          </div>
        </article>
      </section>
"""


def _render_quality_sources(flagged_sources: list[Mapping[str, Any]]) -> str:
    if not flagged_sources:
        return '<p class="muted small">No stale or missing tracked sources in this run.</p>'

    items: list[str] = []
    for row in flagged_sources:
        source = escape(str(row.get("source", "")))
        status = escape(str(row.get("status", "")))
        model = escape(str(row.get("event_model", "")))
        age = row.get("age_days")
        age_text = "" if age is None else f", age {escape(str(age))}d"
        disabled_reason = str(row.get("disabled_reason") or "")
        errors = _list(row.get("errors"))
        details: list[str] = []
        if disabled_reason:
            details.append(f"disabled reason {escape(disabled_reason)}")
        if errors:
            details.append(f"error {escape(str(errors[0]))}")
        details_text = "" if not details else ": " + "; ".join(details)
        items.append(
            f"<li><strong>{source}</strong>: {status} ({model}{age_text}){details_text}</li>"
        )
    return "<ul>" + "\n".join(items) + "</ul>"


def _render_policy_events(events: list[Mapping[str, Any]]) -> str:
    if not events:
        return '<p class="muted small">No tracked policy events in this run.</p>'

    items: list[str] = []
    for event in events:
        title = escape(str(event.get("title", "")))
        model = escape(str(event.get("event_model", "")))
        source = escape(str(event.get("source", "")))
        details = _event_details(event)
        items.append(f"<li><strong>{model}</strong> {title} ({source}){details}</li>")
    return "<ul>" + "\n".join(items) + "</ul>"


def _event_details(event: Mapping[str, Any]) -> str:
    values: list[str] = []
    deadline = str(event.get("consultation_deadline") or "")
    effective_date = str(event.get("policy_effective_date") or "")
    outcomes = _list(event.get("enforcement_outcomes"))
    event_status = str(event.get("event_status") or "")
    event_age = event.get("event_age_days")
    event_key = str(event.get("policy_event_key") or "")
    security_frameworks = _list(event.get("security_frameworks"))
    official_grades = _list(event.get("official_security_grades"))
    overlays = _list(event.get("internal_operational_overlays"))
    if deadline:
        values.append(f"comment deadline {escape(deadline)}")
    if effective_date:
        values.append(f"effective {escape(effective_date)}")
    if outcomes:
        values.append("outcome " + escape(", ".join(str(item) for item in outcomes)))
    if event_status:
        age_text = "" if event_age is None else f" {escape(str(event_age))}d"
        values.append(f"event {escape(event_status)}{age_text}")
    if security_frameworks:
        values.append("framework " + escape(", ".join(str(item) for item in security_frameworks)))
    if official_grades:
        values.append("official grade " + escape(", ".join(str(item) for item in official_grades)))
    if overlays:
        values.append("overlay " + escape(", ".join(str(item) for item in overlays)))
    if event_key:
        values.append("key " + escape(event_key[:64]))
    evidence_url = str(event.get("evidence_url") or "")
    if evidence_url:
        values.append("evidence " + escape(evidence_url))
    return "" if not values else ": " + "; ".join(values)


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []
