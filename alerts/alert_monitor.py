"""Alert monitor for detecting significant policy changes.

Reads recent articles from DuckDB and detects policy changes based on
Korean keywords (시행, 개정, 폐지, 신설).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from radar_core.storage import RadarStorage


@dataclass
class PolicyAlert:
    """Represents a single policy change alert."""

    title: str
    link: str
    summary: str
    source: str
    published: datetime | None
    priority: str  # "high", "medium", "low"
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "link": self.link,
            "summary": self.summary,
            "source": self.source,
            "published": self.published.isoformat() if self.published else None,
            "priority": self.priority,
            "matched_keywords": self.matched_keywords,
        }


@dataclass
class AlertConfig:
    """Configuration for alert detection."""

    alert_keywords: dict[str, list[str]]
    thresholds: dict[str, int]
    priority_levels: dict[str, dict[str, Any]]
    message_templates: dict[str, str]


class AlertMonitor:
    """Monitor for detecting policy changes in collected articles."""

    def __init__(
        self,
        db_path: Path,
        config_path: Path | None = None,
    ) -> None:
        """Initialize the alert monitor.

        Args:
            db_path: Path to the DuckDB database
            config_path: Path to the alert configuration YAML file
        """
        self.db_path = db_path
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Path | None) -> AlertConfig:
        """Load alert configuration from YAML file."""
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"

        if not config_path.exists():
            # Return default configuration
            return AlertConfig(
                alert_keywords={
                    "implementation": ["시행", "시행령", "발효"],
                    "amendment": ["개정", "개정안"],
                    "abolition": ["폐지", "폐기"],
                    "establishment": ["신설", "제정"],
                },
                thresholds={
                    "min_articles": 1,
                    "max_articles_per_alert": 10,
                    "recent_hours": 24,
                },
                priority_levels={
                    "high": {"keywords": ["시행", "폐지", "제정"]},
                    "medium": {"keywords": ["개정", "개정안"]},
                    "low": {"keywords": ["신설", "도입"]},
                },
                message_templates={
                    "header": "[정책 변경 알림] {date}",
                    "footer": "총 {count}건의 정책 변경이 감지되었습니다.",
                    "no_alerts": "감지된 정책 변경 사항이 없습니다.",
                },
            )

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return AlertConfig(
            alert_keywords=data.get("alert_keywords", {}),
            thresholds=data.get("thresholds", {}),
            priority_levels=data.get("priority_levels", {}),
            message_templates=data.get("message_templates", {}),
        )

    def _get_all_keywords(self) -> list[str]:
        """Get all keywords from all categories."""
        keywords: list[str] = []
        for keyword_list in self.config.alert_keywords.values():
            keywords.extend(keyword_list)
        return keywords

    def _determine_priority(self, matched_keywords: list[str]) -> str:
        """Determine alert priority based on matched keywords."""
        for priority in ["high", "medium", "low"]:
            level_config = self.config.priority_levels.get(priority, {})
            priority_keywords = level_config.get("keywords", [])
            for keyword in matched_keywords:
                if keyword in priority_keywords:
                    return priority
        return "low"

    def _match_keywords(self, text: str) -> list[str]:
        """Find all matching keywords in the text."""
        if not text:
            return []

        matched: list[str] = []
        all_keywords = self._get_all_keywords()

        for keyword in all_keywords:
            if re.search(re.escape(keyword), text, re.IGNORECASE):
                if keyword not in matched:
                    matched.append(keyword)

        return matched

    def scan_articles(
        self,
        category: str = "policy",
        hours: int | None = None,
    ) -> list[PolicyAlert]:
        """Scan recent articles for policy changes.

        Args:
            category: Category to scan
            hours: Number of hours to look back (defaults to config value)

        Returns:
            List of PolicyAlert objects for articles with policy changes
        """
        if hours is None:
            hours = self.config.thresholds.get("recent_hours", 24)

        # Calculate days from hours (round up)
        days = max(1, (hours + 23) // 24)

        alerts: list[PolicyAlert] = []

        with RadarStorage(self.db_path) as storage:
            articles = storage.recent_articles(category, days=days)

        # Filter by actual time window
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        cutoff_naive = cutoff.replace(tzinfo=None)

        for article in articles:
            # Check if article is within the time window
            article_time = article.published or article.collected_at
            if article_time and article_time < cutoff_naive:
                continue

            # Check title and summary for keywords
            text_to_check = f"{article.title} {article.summary}"
            matched_keywords = self._match_keywords(text_to_check)

            if matched_keywords:
                priority = self._determine_priority(matched_keywords)
                alerts.append(
                    PolicyAlert(
                        title=article.title,
                        link=article.link,
                        summary=article.summary,
                        source=article.source,
                        published=article.published,
                        priority=priority,
                        matched_keywords=matched_keywords,
                    )
                )

        # Sort by priority (high first) and then by published date
        priority_order = {"high": 0, "medium": 1, "low": 2}
        alerts.sort(
            key=lambda a: (
                priority_order.get(a.priority, 3),
                -(a.published.timestamp() if a.published else 0),
            )
        )

        # Limit to max articles per alert
        max_alerts = self.config.thresholds.get("max_articles_per_alert", 10)
        return alerts[:max_alerts]

    def generate_alert_message(
        self,
        alerts: list[PolicyAlert],
        format_type: str = "text",
    ) -> str:
        """Generate alert message in Korean.

        Args:
            alerts: List of PolicyAlert objects
            format_type: Output format ("text" or "html")

        Returns:
            Formatted alert message in Korean
        """
        templates = self.config.message_templates
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        if not alerts:
            return templates.get("no_alerts", "감지된 정책 변경 사항이 없습니다.")

        lines: list[str] = []

        # Header
        header = templates.get("header", "[정책 변경 알림] {date}")
        lines.append(header.format(date=date_str))
        lines.append("")

        # Group by priority
        priority_groups: dict[str, list[PolicyAlert]] = {
            "high": [],
            "medium": [],
            "low": [],
        }
        for alert in alerts:
            priority_groups[alert.priority].append(alert)

        # High priority alerts
        if priority_groups["high"]:
            lines.append("=== 긴급 (즉각 조치 필요) ===")
            for alert in priority_groups["high"]:
                lines.append(f"  - {alert.title}")
                lines.append(f"    출처: {alert.source}")
                lines.append(f"    키워드: {', '.join(alert.matched_keywords)}")
                lines.append(f"    링크: {alert.link}")
                lines.append("")

        # Medium priority alerts
        if priority_groups["medium"]:
            lines.append("=== 중요 (검토 필요) ===")
            for alert in priority_groups["medium"]:
                lines.append(f"  - {alert.title}")
                lines.append(f"    출처: {alert.source}")
                lines.append(f"    키워드: {', '.join(alert.matched_keywords)}")
                lines.append(f"    링크: {alert.link}")
                lines.append("")

        # Low priority alerts
        if priority_groups["low"]:
            lines.append("=== 정보 ===")
            for alert in priority_groups["low"]:
                lines.append(f"  - {alert.title}")
                lines.append(f"    출처: {alert.source}")
                lines.append(f"    키워드: {', '.join(alert.matched_keywords)}")
                lines.append(f"    링크: {alert.link}")
                lines.append("")

        # Footer
        footer = templates.get("footer", "총 {count}건의 정책 변경이 감지되었습니다.")
        lines.append(footer.format(count=len(alerts)))

        return "\n".join(lines)


def main() -> None:
    """CLI entry point for alert monitoring."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="Scan PolicyRadar database for policy changes"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/radar_data.duckdb"),
        help="Path to DuckDB database",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to alert configuration YAML",
    )
    parser.add_argument(
        "--category",
        default="policy",
        help="Category to scan",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours to look back",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    monitor = AlertMonitor(args.db_path, args.config)
    alerts = monitor.scan_articles(args.category, args.hours)

    if args.output == "json":
        output = {
            "timestamp": datetime.now(UTC).isoformat(),
            "category": args.category,
            "hours_scanned": args.hours,
            "alert_count": len(alerts),
            "alerts": [a.to_dict() for a in alerts],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        message = monitor.generate_alert_message(alerts)
        print(message)

    # Exit with code 1 if high-priority alerts exist
    if any(a.priority == "high" for a in alerts):
        sys.exit(1)


if __name__ == "__main__":
    main()
