"""Telegram notifier for policy change alerts.

Sends alert messages via Telegram Bot API.
Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests
import structlog

from .alert_monitor import AlertMonitor, PolicyAlert

logger = structlog.get_logger(__name__)


@dataclass
class TelegramConfig:
    """Telegram notification configuration."""

    bot_token: str
    chat_id: str
    parse_mode: str = "HTML"
    disable_web_page_preview: bool = True


class TelegramNotifier:
    """Send policy alerts via Telegram."""

    TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        """Initialize Telegram notifier.

        Args:
            bot_token: Telegram Bot API token (or use TELEGRAM_BOT_TOKEN env var)
            chat_id: Telegram chat ID (or use TELEGRAM_CHAT_ID env var)
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    @property
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token and self.chat_id)

    def _format_alert_html(self, alert: PolicyAlert) -> str:
        """Format a single alert as HTML for Telegram."""
        priority_emoji = {
            "high": "🚨",
            "medium": "⚠️",
            "low": "ℹ️",
        }
        emoji = priority_emoji.get(alert.priority, "📢")

        lines = [
            f"{emoji} <b>{self._escape_html(alert.title)}</b>",
            f"출처: {self._escape_html(alert.source)}",
            f"키워드: {', '.join(alert.matched_keywords)}",
            f"<a href=\"{alert.link}\">기사 보기</a>",
        ]

        return "\n".join(lines)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def format_message(self, alerts: list[PolicyAlert]) -> str:
        """Format alerts as HTML message for Telegram.

        Args:
            alerts: List of PolicyAlert objects

        Returns:
            HTML-formatted message
        """
        if not alerts:
            return "✅ <b>정책 변경 알림</b>\n\n감지된 정책 변경 사항이 없습니다."

        lines = ["📋 <b>정책 변경 알림</b>", ""]

        # Group by priority
        high = [a for a in alerts if a.priority == "high"]
        medium = [a for a in alerts if a.priority == "medium"]
        low = [a for a in alerts if a.priority == "low"]

        if high:
            lines.append("🚨 <b>긴급</b>")
            for alert in high:
                lines.append(self._format_alert_html(alert))
                lines.append("")

        if medium:
            lines.append("⚠️ <b>중요</b>")
            for alert in medium:
                lines.append(self._format_alert_html(alert))
                lines.append("")

        if low:
            lines.append("ℹ️ <b>정보</b>")
            for alert in low:
                lines.append(self._format_alert_html(alert))
                lines.append("")

        lines.append(f"총 <b>{len(alerts)}</b>건의 정책 변경이 감지되었습니다.")

        return "\n".join(lines)

    def send(self, message: str) -> bool:
        """Send a message via Telegram.

        Args:
            message: Message to send (HTML format)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            logger.warning("telegram_not_configured")
            return False

        url = self.TELEGRAM_API_URL.format(token=self.bot_token)
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code != 200:
                logger.error(
                    "telegram_send_failed",
                    status_code=response.status_code,
                    response=response.text,
                )
                return False

            logger.info("telegram_message_sent")
            return True

        except requests.RequestException as e:
            logger.error("telegram_request_failed", error=str(e))
            return False

    def send_alerts(self, alerts: list[PolicyAlert]) -> bool:
        """Send policy alerts via Telegram.

        Args:
            alerts: List of PolicyAlert objects

        Returns:
            True if successful, False otherwise
        """
        message = self.format_message(alerts)
        return self.send(message)


def main() -> None:
    """CLI entry point for sending Telegram alerts."""
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Send policy change alerts via Telegram"
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
        "--dry-run",
        action="store_true",
        help="Print message without sending",
    )

    args = parser.parse_args()

    # Check for required env vars
    if not args.dry_run:
        if not os.environ.get("TELEGRAM_BOT_TOKEN"):
            print("Error: TELEGRAM_BOT_TOKEN environment variable not set")
            return
        if not os.environ.get("TELEGRAM_CHAT_ID"):
            print("Error: TELEGRAM_CHAT_ID environment variable not set")
            return

    # Scan for alerts
    monitor = AlertMonitor(args.db_path, args.config)
    alerts = monitor.scan_articles(args.category, args.hours)

    # Create notifier and send
    notifier = TelegramNotifier()
    message = notifier.format_message(alerts)

    if args.dry_run:
        print("=== Telegram Message Preview ===")
        print(message)
        print("================================")
        print(f"Would send to chat_id: {notifier.chat_id or '(not set)'}")
    else:
        success = notifier.send(message)
        if success:
            print(f"Successfully sent {len(alerts)} alert(s) to Telegram")
        else:
            print("Failed to send alerts to Telegram")


if __name__ == "__main__":
    main()
