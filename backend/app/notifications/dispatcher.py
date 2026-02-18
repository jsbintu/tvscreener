"""
Bubby Vision — Multi-Channel Notification Dispatcher

Sends alerts to Discord (webhook) and Telegram (bot API).
Channels are auto-skipped when credentials are not configured.
"""

from __future__ import annotations

import enum
from typing import Optional

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


class AlertType(str, enum.Enum):
    TRADE_SIGNAL = "trade_signal"
    RISK_ALERT = "risk_alert"
    EARNINGS = "earnings"
    SYSTEM = "system"


# Discord embed colour palette
_ALERT_COLORS: dict[AlertType, int] = {
    AlertType.TRADE_SIGNAL: 0x00FF88,  # green
    AlertType.RISK_ALERT: 0xFF4444,    # red
    AlertType.EARNINGS: 0xFFAA00,      # amber
    AlertType.SYSTEM: 0x5865F2,        # blurple
}

_ALERT_EMOJI: dict[AlertType, str] = {
    AlertType.TRADE_SIGNAL: "📈",
    AlertType.RISK_ALERT: "🚨",
    AlertType.EARNINGS: "📊",
    AlertType.SYSTEM: "⚙️",
}


# ──────────────────────────────────────────────
# Channel Notifiers
# ──────────────────────────────────────────────


class DiscordNotifier:
    """Send rich embed messages via Discord webhook."""

    def __init__(self, webhook_url: str):
        self._url = webhook_url

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def send(
        self,
        title: str,
        message: str,
        alert_type: AlertType = AlertType.SYSTEM,
    ) -> bool:
        if not self.configured:
            return False

        emoji = _ALERT_EMOJI.get(alert_type, "📌")
        payload = {
            "embeds": [
                {
                    "title": f"{emoji} {title}",
                    "description": message,
                    "color": _ALERT_COLORS.get(alert_type, 0x5865F2),
                    "footer": {"text": "Bubby Vision"},
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._url, json=payload)
                resp.raise_for_status()
            log.info("notification.discord.sent", title=title)
            return True
        except Exception as exc:
            log.error("notification.discord.failed", error=str(exc))
            return False


class TelegramNotifier:
    """Send messages via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str):
        self._token = bot_token
        self._chat_id = chat_id

    @property
    def configured(self) -> bool:
        return bool(self._token and self._chat_id)

    async def send(
        self,
        title: str,
        message: str,
        alert_type: AlertType = AlertType.SYSTEM,
    ) -> bool:
        if not self.configured:
            return False

        emoji = _ALERT_EMOJI.get(alert_type, "📌")
        text = f"{emoji} *{title}*\n\n{message}"

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            log.info("notification.telegram.sent", title=title)
            return True
        except Exception as exc:
            log.error("notification.telegram.failed", error=str(exc))
            return False


# ──────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────


class NotificationDispatcher:
    """Fan-out delivery to all configured notification channels.

    Usage::

        dispatcher = get_dispatcher()
        await dispatcher.send(
            title="AAPL Breakout",
            message="Price broke above $195 resistance with 2.3x volume.",
            alert_type=AlertType.TRADE_SIGNAL,
        )
    """

    def __init__(self):
        settings = get_settings()
        self._channels = [
            DiscordNotifier(settings.discord_webhook_url),
            TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id),
        ]

    async def send(
        self,
        title: str,
        message: str,
        alert_type: AlertType = AlertType.SYSTEM,
    ) -> dict[str, bool]:
        """Send to all configured channels. Returns delivery status per channel."""
        results: dict[str, bool] = {}
        for channel in self._channels:
            name = type(channel).__name__
            if channel.configured:
                results[name] = await channel.send(title, message, alert_type)
            else:
                results[name] = False
        return results

    @property
    def active_channels(self) -> list[str]:
        return [type(c).__name__ for c in self._channels if c.configured]


_dispatcher: Optional[NotificationDispatcher] = None


def get_dispatcher() -> NotificationDispatcher:
    """Singleton accessor for the notification dispatcher."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
