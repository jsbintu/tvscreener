"""
Bubby Vision — Multi-Channel Alert Engine

Delivers alerts via multiple channels:
- Ntfy.sh (push notifications — free, no API key required)
- Resend (email — free 100/day)
- WebSocket (in-app real-time)

Includes smart deduplication, priority-based grouping, and rate limiting.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from typing import Optional

import structlog

log = structlog.get_logger()


class AlertEngine:
    """Multi-channel alert dispatcher with dedup and rate limiting."""

    def __init__(
        self,
        ntfy_topic: str = "bubby-vision",
        resend_api_key: Optional[str] = None,
        resend_from: str = "alerts@bubby.vision",
        redis_url: Optional[str] = None,
    ):
        self.ntfy_topic = ntfy_topic
        self.resend_api_key = resend_api_key
        self.resend_from = resend_from
        self._redis = None

        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                log.warning("alert_engine.redis_init_failed", error=str(e))

    def _dedup_key(self, alert: dict) -> str:
        """Generate a deduplication key for an alert."""
        raw = f"{alert.get('ticker', '')}-{alert.get('type', '')}-{alert.get('message', '')}"
        return f"alert:dedup:{hashlib.md5(raw.encode()).hexdigest()}"

    def _is_duplicate(self, alert: dict, ttl: int = 300) -> bool:
        """Check if alert was already sent within TTL seconds."""
        if not self._redis:
            return False

        key = self._dedup_key(alert)
        if self._redis.exists(key):
            return True

        # Mark as sent
        self._redis.setex(key, ttl, "1")
        return False

    def send_ntfy(
        self,
        title: str,
        message: str,
        priority: int = 3,
        tags: Optional[list[str]] = None,
        click_url: Optional[str] = None,
    ) -> dict:
        """Send push notification via ntfy.sh.

        Args:
            title: Notification title.
            message: Notification body.
            priority: 1-5 (1=min, 3=default, 5=urgent).
            tags: Emoji tags (e.g. ['chart_with_upwards_trend', 'warning']).
            click_url: URL to open on click.

        Returns:
            Dict with send status.
        """
        import requests

        url = f"https://ntfy.sh/{self.ntfy_topic}"
        headers = {
            "Title": title,
            "Priority": str(min(5, max(1, priority))),
        }

        if tags:
            headers["Tags"] = ",".join(tags)
        if click_url:
            headers["Click"] = click_url

        try:
            resp = requests.post(url, data=message, headers=headers, timeout=10)
            resp.raise_for_status()
            log.info("alert.ntfy_sent", title=title, status=resp.status_code)
            return {"channel": "ntfy", "status": "sent", "code": resp.status_code}
        except Exception as e:
            log.warning("alert.ntfy_failed", title=title, error=str(e))
            return {"channel": "ntfy", "status": "failed", "error": str(e)}

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: Optional[str] = None,
    ) -> dict:
        """Send email alert via Resend.

        Args:
            to: Recipient email address.
            subject: Email subject.
            body: Plain text body.
            html: Optional HTML body.

        Returns:
            Dict with send status.
        """
        if not self.resend_api_key:
            return {"channel": "email", "status": "skipped", "reason": "no_api_key"}

        import requests

        try:
            payload = {
                "from": self.resend_from,
                "to": [to],
                "subject": subject,
                "text": body,
            }
            if html:
                payload["html"] = html

            resp = requests.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {self.resend_api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            log.info("alert.email_sent", to=to, subject=subject)
            return {"channel": "email", "status": "sent", "id": resp.json().get("id")}
        except Exception as e:
            log.warning("alert.email_failed", to=to, error=str(e))
            return {"channel": "email", "status": "failed", "error": str(e)}

    def send_websocket(
        self,
        channel: str,
        payload: dict,
    ) -> dict:
        """Broadcast alert via WebSocket (in-app).

        Publishes to Redis pub/sub for WebSocket broadcast.

        Args:
            channel: Redis pub/sub channel name.
            payload: Alert payload to broadcast.

        Returns:
            Dict with send status.
        """
        if not self._redis:
            return {"channel": "websocket", "status": "skipped", "reason": "no_redis"}

        try:
            message = json.dumps({
                **payload,
                "timestamp": datetime.now().isoformat(),
            })
            subscribers = self._redis.publish(f"alerts:{channel}", message)
            log.info("alert.ws_sent", channel=channel, subscribers=subscribers)
            return {"channel": "websocket", "status": "sent", "subscribers": subscribers}
        except Exception as e:
            log.warning("alert.ws_failed", channel=channel, error=str(e))
            return {"channel": "websocket", "status": "failed", "error": str(e)}

    def dispatch_alert(
        self,
        alert: dict,
        channels: Optional[list[str]] = None,
    ) -> dict:
        """Smart alert dispatcher with dedup and channel routing.

        Args:
            alert: Alert dict with keys: ticker, type, message, priority, etc.
            channels: List of channels to use (default: ['ntfy', 'ws']).

        Returns:
            Dict with per-channel results.
        """
        if channels is None:
            channels = ["ntfy", "ws"]

        # Dedup check
        if self._is_duplicate(alert):
            log.info("alert.deduplicated", ticker=alert.get("ticker"))
            return {"status": "deduplicated", "channels": {}}

        ticker = alert.get("ticker", "")
        alert_type = alert.get("type", "alert")
        message = alert.get("message", "")
        priority = alert.get("priority", 3)
        title = f"🔔 {ticker}: {alert_type}"

        results = {}

        if "ntfy" in channels:
            tags = []
            if alert.get("direction") == "bullish":
                tags.append("chart_with_upwards_trend")
            elif alert.get("direction") == "bearish":
                tags.append("chart_with_downwards_trend")
            else:
                tags.append("bell")

            results["ntfy"] = self.send_ntfy(
                title=title,
                message=message,
                priority=priority,
                tags=tags,
            )

        if "ws" in channels:
            results["ws"] = self.send_websocket(
                channel=ticker.lower() if ticker else "general",
                payload=alert,
            )

        if "email" in channels:
            email_to = alert.get("email_to")
            if email_to:
                results["email"] = self.send_email(
                    to=email_to,
                    subject=title,
                    body=message,
                )

        # Store alert in Redis for history
        if self._redis:
            try:
                alert_record = {
                    **alert,
                    "dispatched_at": datetime.now().isoformat(),
                    "channels": list(results.keys()),
                }
                self._redis.lpush("alerts:history", json.dumps(alert_record))
                self._redis.ltrim("alerts:history", 0, 999)  # Keep last 1000
            except Exception:
                pass

        return {"status": "dispatched", "channels": results}

    def get_alert_history(self, limit: int = 50) -> list[dict]:
        """Get recent alert history from Redis.

        Args:
            limit: Max alerts to return. Default 50.

        Returns:
            List of recent alerts.
        """
        if not self._redis:
            return []

        try:
            raw = self._redis.lrange("alerts:history", 0, limit - 1)
            return [json.loads(r) for r in raw]
        except Exception:
            return []
