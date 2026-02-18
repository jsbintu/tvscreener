"""
Bubby Vision — Alert Chain Engine

Manages linked alert chains: pattern completion → entry alert → stop alert.
When a pattern completes, the engine automatically creates follow-up alerts
for entry and stop-loss levels, enabling fully automated trade monitoring.

All chain state is persisted in Redis.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

import structlog

log = structlog.get_logger()


class AlertChainEngine:
    """Linked alert chain manager with Redis persistence."""

    def __init__(self, redis_url: Optional[str] = None):
        self._redis = None
        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                log.warning("alert_chain.redis_init_failed", error=str(e))

    def create_chain(
        self,
        ticker: str,
        pattern_name: str,
        entry: float,
        stop: float,
        targets: Optional[list[float]] = None,
        direction: str = "long",
    ) -> dict:
        """Create a linked alert chain from a pattern signal.

        Chain sequence:
        1. Pattern detected → chain created (PENDING)
        2. Entry price hit → chain becomes ACTIVE, stop alert armed
        3. Target hit OR stop hit → chain becomes COMPLETED or STOPPED

        Args:
            ticker: Stock ticker.
            pattern_name: Name of the triggering pattern.
            entry: Entry price level.
            stop: Stop-loss price level.
            targets: List of target prices [TP1, TP2, TP3].
            direction: 'long' or 'short'.

        Returns:
            Dict with chain_id and initial state.
        """
        chain_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        chain = {
            "chain_id": chain_id,
            "ticker": ticker.upper(),
            "pattern_name": pattern_name,
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "targets": targets or [],
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "events": [
                {"type": "created", "timestamp": now, "detail": f"Pattern: {pattern_name}"}
            ],
            "alerts": [
                {
                    "id": f"{chain_id}-entry",
                    "type": "entry",
                    "price": entry,
                    "status": "armed",
                    "condition": "price_crosses" if direction == "long" else "price_drops_below",
                },
                {
                    "id": f"{chain_id}-stop",
                    "type": "stop",
                    "price": stop,
                    "status": "waiting",
                    "condition": "price_drops_below" if direction == "long" else "price_crosses",
                },
            ],
        }

        # Add target alerts
        for i, tp in enumerate(targets or []):
            chain["alerts"].append({
                "id": f"{chain_id}-tp{i + 1}",
                "type": f"tp{i + 1}",
                "price": tp,
                "status": "waiting",
                "condition": "price_crosses" if direction == "long" else "price_drops_below",
            })

        # Persist to Redis
        if self._redis:
            self._redis.hset("alert:chains", chain_id, json.dumps(chain))
            self._redis.sadd(f"alert:chains:ticker:{ticker.upper()}", chain_id)

        log.info("alert_chain.created", chain_id=chain_id, ticker=ticker, pattern=pattern_name)
        return chain

    def evaluate_chain(
        self,
        chain_id: str,
        current_price: float,
    ) -> dict:
        """Evaluate a chain against the current price.

        Checks all armed alerts in the chain and triggers any that hit.

        Args:
            chain_id: Chain identifier.
            current_price: Current market price.

        Returns:
            Dict with evaluation result and any triggered alerts.
        """
        chain = self.get_chain(chain_id)
        if not chain:
            return {"error": "chain_not_found"}

        if chain["status"] in ("completed", "stopped", "cancelled"):
            return {"chain_id": chain_id, "status": chain["status"], "triggered": []}

        triggered = []
        now = datetime.now().isoformat()
        direction = chain.get("direction", "long")

        for alert in chain.get("alerts", []):
            if alert["status"] != "armed":
                continue

            price = alert["price"]
            hit = False

            if alert["type"] == "entry":
                if direction == "long":
                    hit = current_price >= price
                else:
                    hit = current_price <= price
            elif alert["type"] == "stop":
                if direction == "long":
                    hit = current_price <= price
                else:
                    hit = current_price >= price
            elif alert["type"].startswith("tp"):
                if direction == "long":
                    hit = current_price >= price
                else:
                    hit = current_price <= price

            if hit:
                alert["status"] = "triggered"
                alert["triggered_at"] = now
                alert["triggered_price"] = current_price
                triggered.append(alert)

                chain["events"].append({
                    "type": f"{alert['type']}_triggered",
                    "timestamp": now,
                    "price": current_price,
                })

        # State transitions
        if any(a["type"] == "entry" and a["status"] == "triggered" for a in chain["alerts"]):
            chain["status"] = "active"
            # Arm stop and targets
            for a in chain["alerts"]:
                if a["type"] in ("stop",) or a["type"].startswith("tp"):
                    if a["status"] == "waiting":
                        a["status"] = "armed"

        if any(a["type"] == "stop" and a["status"] == "triggered" for a in chain["alerts"]):
            chain["status"] = "stopped"

        # Check if all targets hit
        target_alerts = [a for a in chain["alerts"] if a["type"].startswith("tp")]
        if target_alerts and all(a["status"] == "triggered" for a in target_alerts):
            chain["status"] = "completed"

        chain["updated_at"] = now

        # Persist
        if self._redis:
            self._redis.hset("alert:chains", chain_id, json.dumps(chain))

        return {
            "chain_id": chain_id,
            "status": chain["status"],
            "current_price": current_price,
            "triggered": triggered,
        }

    def get_chain(self, chain_id: str) -> Optional[dict]:
        """Get a chain by ID."""
        if not self._redis:
            return None

        raw = self._redis.hget("alert:chains", chain_id)
        if raw:
            return json.loads(raw)
        return None

    def get_chains_for_ticker(self, ticker: str) -> list[dict]:
        """Get all chains for a ticker."""
        if not self._redis:
            return []

        chain_ids = self._redis.smembers(f"alert:chains:ticker:{ticker.upper()}")
        chains = []
        for cid in chain_ids:
            chain = self.get_chain(cid)
            if chain:
                chains.append(chain)
        return chains

    def get_active_chains(self) -> list[dict]:
        """Get all pending or active chains."""
        if not self._redis:
            return []

        all_chains = self._redis.hgetall("alert:chains")
        active = []
        for raw in all_chains.values():
            chain = json.loads(raw)
            if chain.get("status") in ("pending", "active"):
                active.append(chain)
        return active

    def cancel_chain(self, chain_id: str) -> dict:
        """Cancel a chain."""
        chain = self.get_chain(chain_id)
        if not chain:
            return {"error": "chain_not_found"}

        chain["status"] = "cancelled"
        chain["updated_at"] = datetime.now().isoformat()
        chain["events"].append({
            "type": "cancelled",
            "timestamp": chain["updated_at"],
        })

        if self._redis:
            self._redis.hset("alert:chains", chain_id, json.dumps(chain))

        return {"chain_id": chain_id, "status": "cancelled"}
