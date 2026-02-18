"""
Bubby Vision — WebSocket Streaming

Real-time price feeds, alert notifications, and order push via WebSocket.

Endpoints:
    /ws/stream/{ticker}  — live price stream (polls Alpaca, pushes diffs)
    /ws/alerts            — user alert push notifications
    /ws/orders            — Questrade Plus order status & execution push
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import get_settings

log = structlog.get_logger(__name__)

ws_router = APIRouter()


# ──────────────────────────────────────────────
# WebSocket Authentication
# ──────────────────────────────────────────────


async def _ws_authenticate(
    websocket: WebSocket,
    api_key: str | None = None,
    token: str | None = None,
) -> bool:
    """Validate WebSocket connection auth.

    In development mode, auth is bypassed.
    Accepts either a JWT token or api_key query param.
    Returns True if authenticated, False (and closes) otherwise.
    """
    settings = get_settings()
    if getattr(settings, "app_env", "development") == "development":
        return True

    # 1. Try JWT token first
    if token:
        try:
            from app.auth.jwt_handler import verify_token
            payload = verify_token(token)
            if payload and payload.get("type") == "access":
                return True
        except Exception:
            pass
        await websocket.close(code=4001, reason="Invalid JWT token")
        log.warning("ws.auth_failed", reason="invalid_jwt")
        return False

    # 2. Fall back to API key
    if not api_key:
        await websocket.close(code=4001, reason="Missing auth")
        log.warning("ws.auth_failed", reason="missing_auth")
        return False

    # Validate against configured keys (any valid API key accepted)
    valid_keys = [
        k for k in [
            getattr(settings, "finnhub_api_key", None),
            getattr(settings, "alpaca_api_key", None),
        ] if k
    ]

    if not valid_keys or api_key not in valid_keys:
        await websocket.close(code=4001, reason="Invalid api_key")
        log.warning("ws.auth_failed", reason="invalid_api_key")
        return False

    return True


# ──────────────────────────────────────────────
# Connection Manager
# ──────────────────────────────────────────────


class ConnectionManager:
    """Track active WebSocket connections and broadcast messages."""

    def __init__(self):
        # ticker -> set of websockets
        self._price_clients: dict[str, set[WebSocket]] = {}
        # alert channel clients
        self._alert_clients: set[WebSocket] = set()

    async def connect_price(self, websocket: WebSocket, ticker: str):
        await websocket.accept()
        if ticker not in self._price_clients:
            self._price_clients[ticker] = set()
        self._price_clients[ticker].add(websocket)
        log.info("ws.price.connected", ticker=ticker, total=len(self._price_clients[ticker]))

    def disconnect_price(self, websocket: WebSocket, ticker: str):
        if ticker in self._price_clients:
            self._price_clients[ticker].discard(websocket)
            if not self._price_clients[ticker]:
                del self._price_clients[ticker]
        log.info("ws.price.disconnected", ticker=ticker)

    async def connect_alerts(self, websocket: WebSocket):
        await websocket.accept()
        self._alert_clients.add(websocket)
        log.info("ws.alerts.connected", total=len(self._alert_clients))

    def disconnect_alerts(self, websocket: WebSocket):
        self._alert_clients.discard(websocket)
        log.info("ws.alerts.disconnected")

    async def broadcast_price(self, ticker: str, data: dict):
        """Send price update to all clients watching a ticker."""
        clients = self._price_clients.get(ticker, set())
        dead: list[WebSocket] = []

        for ws in clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            clients.discard(ws)

    async def broadcast_alert(self, data: dict):
        """Send alert to all alert-channel clients."""
        dead: list[WebSocket] = []

        for ws in self._alert_clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._alert_clients.discard(ws)

    @property
    def active_tickers(self) -> list[str]:
        return list(self._price_clients.keys())

    @property
    def total_connections(self) -> int:
        price_count = sum(len(v) for v in self._price_clients.values())
        return price_count + len(self._alert_clients)


# Global manager
manager = ConnectionManager()


# ──────────────────────────────────────────────
# Price Stream Endpoint (Questrade L1 primary, Alpaca WS fallback)
# ──────────────────────────────────────────────


async def _fetch_price(ticker: str) -> Optional[dict]:
    """Fetch latest price data — Questrade L1 primary, Alpaca fallback."""
    # Try Questrade L1 first
    try:
        from app.data.questrade_client import QuestradeClient
        qt = QuestradeClient()
        quote = await qt.get_quote_raw(ticker)
        if quote and quote.get("lastTradePrice"):
            return {
                "ticker": ticker.upper(),
                "source": "questrade",
                "price": quote.get("lastTradePrice"),
                "bid": quote.get("bidPrice"),
                "ask": quote.get("askPrice"),
                "volume": quote.get("volume"),
                "open": quote.get("openPrice"),
                "high": quote.get("highPrice"),
                "low": quote.get("lowPrice"),
                "timestamp": quote.get("lastTradeTime"),
                "is_halted": quote.get("isHalted"),
            }
    except Exception as exc:
        log.debug("ws.questrade_price_failed", ticker=ticker, error=str(exc))

    # Fallback to Alpaca snapshot
    try:
        from app.data.alpaca_client import AlpacaClient
        client = AlpacaClient()
        snapshot = await client.get_stock_snapshot(ticker)

        if isinstance(snapshot, dict):
            trade = snapshot.get("latest_trade", {})
            quote = snapshot.get("latest_quote", {})
            return {
                "ticker": ticker.upper(),
                "source": "alpaca",
                "price": trade.get("price"),
                "bid": quote.get("bid_price"),
                "ask": quote.get("ask_price"),
                "volume": trade.get("size"),
                "timestamp": trade.get("timestamp"),
            }
    except Exception as exc:
        log.debug("ws.alpaca_price_fetch_failed", ticker=ticker, error=str(exc))
    return None


async def _alpaca_native_stream(ticker: str, websocket: WebSocket):
    """Connect to Alpaca's native WebSocket for true real-time data.

    Uses wss://stream.data.alpaca.markets/v2/{feed} for trade updates.
    Falls back to HTTP polling if the native WS connection fails.
    """
    settings = get_settings()
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        log.warning("ws.native_stream_no_keys", ticker=ticker)
        return False

    feed = settings.alpaca_feed  # 'iex', 'sip', or 'delayed_sip'
    ws_url = f"wss://stream.data.alpaca.markets/v2/{feed}"

    try:
        import websockets

        async with websockets.connect(ws_url) as alpaca_ws:
            # Step 1: Receive welcome message
            welcome = json.loads(await asyncio.wait_for(alpaca_ws.recv(), timeout=5))
            log.debug("ws.alpaca_welcome", data=welcome)

            # Step 2: Authenticate
            auth_msg = json.dumps({
                "action": "auth",
                "key": settings.alpaca_api_key,
                "secret": settings.alpaca_secret_key,
            })
            await alpaca_ws.send(auth_msg)
            auth_resp = json.loads(await asyncio.wait_for(alpaca_ws.recv(), timeout=5))
            log.debug("ws.alpaca_auth", data=auth_resp)

            # Check auth success
            if isinstance(auth_resp, list) and auth_resp:
                if auth_resp[0].get("msg") != "authenticated":
                    log.error("ws.alpaca_auth_failed", resp=auth_resp)
                    return False

            # Step 3: Subscribe to trades for the ticker
            sub_msg = json.dumps({
                "action": "subscribe",
                "trades": [ticker.upper()],
            })
            await alpaca_ws.send(sub_msg)
            sub_resp = json.loads(await asyncio.wait_for(alpaca_ws.recv(), timeout=5))
            log.info("ws.alpaca_subscribed", ticker=ticker, feed=feed, resp=sub_resp)

            # Step 4: Stream trade data to our clients
            last_heartbeat = time.monotonic()
            heartbeat_interval = 15.0

            while True:
                try:
                    raw = await asyncio.wait_for(alpaca_ws.recv(), timeout=heartbeat_interval)
                    messages = json.loads(raw)

                    if isinstance(messages, list):
                        for msg in messages:
                            if msg.get("T") == "t":  # Trade update
                                price_data = {
                                    "ticker": msg.get("S", ticker).upper(),
                                    "price": msg.get("p"),
                                    "size": msg.get("s"),
                                    "exchange": msg.get("x"),
                                    "timestamp": msg.get("t"),
                                    "conditions": msg.get("c", []),
                                }
                                await manager.broadcast_price(ticker, {
                                    "type": "price",
                                    "data": price_data,
                                })
                                last_heartbeat = time.monotonic()

                except asyncio.TimeoutError:
                    # No trade data — send heartbeat
                    if time.monotonic() - last_heartbeat > heartbeat_interval:
                        try:
                            await websocket.send_json({
                                "type": "heartbeat",
                                "data": {"ticker": ticker, "ts": int(time.time())},
                            })
                        except Exception:
                            break
                        last_heartbeat = time.monotonic()

                # Check if our client websocket is still open
                if websocket.client_state != WebSocketState.CONNECTED:
                    break

        return True

    except ImportError:
        log.warning("ws.websockets_not_installed", msg="pip install websockets for native streaming")
        return False
    except Exception as exc:
        log.warning("ws.native_stream_failed", ticker=ticker, error=str(exc))
        return False


@ws_router.websocket("/ws/stream/{ticker}")
async def price_stream(
    websocket: WebSocket,
    ticker: str,
    api_key: str | None = Query(None),
    token: str | None = Query(None),
):
    """Live price stream for a single ticker.

    Attempts Questrade L1 polling first (primary, real-time exchange data).
    Falls back to Alpaca native WebSocket if Questrade is unavailable.
    Final fallback: HTTP polling every 2 seconds.

    Message format::

        {"type": "price", "data": {"ticker": "AAPL", "price": 195.23, ...}}
        {"type": "heartbeat", "data": {"ticker": "AAPL", "ts": 1707...}}
    """
    if not await _ws_authenticate(websocket, api_key=api_key, token=token):
        return

    ticker = ticker.upper()
    await manager.connect_price(websocket, ticker)

    try:
        # Try native Alpaca WebSocket first
        native_success = await _alpaca_native_stream(ticker, websocket)

        if not native_success:
            # Fallback to polling mode
            log.info("ws.polling_fallback", ticker=ticker)

            last_price: Optional[float] = None
            last_heartbeat = time.monotonic()
            poll_interval = 2.0
            heartbeat_interval = 15.0

            while True:
                price_data = await _fetch_price(ticker)

                if price_data and price_data.get("price") != last_price:
                    last_price = price_data.get("price")
                    await manager.broadcast_price(ticker, {
                        "type": "price",
                        "data": price_data,
                    })
                    last_heartbeat = time.monotonic()

                elif time.monotonic() - last_heartbeat > heartbeat_interval:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "data": {"ticker": ticker, "ts": int(time.time())},
                    })
                    last_heartbeat = time.monotonic()

                try:
                    msg = await asyncio.wait_for(
                        websocket.receive_text(), timeout=poll_interval
                    )
                    if msg == "close":
                        break
                except asyncio.TimeoutError:
                    pass

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.error("ws.stream_error", ticker=ticker, error=str(exc))
    finally:
        manager.disconnect_price(websocket, ticker)


# ──────────────────────────────────────────────
# Alert Stream Endpoint
# ──────────────────────────────────────────────


@ws_router.websocket("/ws/alerts")
async def alert_stream(
    websocket: WebSocket,
    api_key: str | None = Query(None),
    token: str | None = Query(None),
):
    """Alert notification stream.

    Clients connect and receive price alert triggers in real-time.
    Stays alive with heartbeats.

    Message format::

        {"type": "alert", "data": {"ticker": "TSLA", "threshold": 250.0, ...}}
        {"type": "heartbeat", "data": {"ts": 1707...}}
    """
    if not await _ws_authenticate(websocket, api_key=api_key, token=token):
        return

    await manager.connect_alerts(websocket)

    try:
        while True:
            # Keep alive — wait for any incoming messages
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_text(), timeout=15.0
                )
                if msg == "close":
                    break
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "data": {"ts": int(time.time())},
                })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.error("ws.alert_stream_error", error=str(exc))
    finally:
        manager.disconnect_alerts(websocket)


# ──────────────────────────────────────────────
# Alert Broadcast Helper (called from tasks/routes)
# ──────────────────────────────────────────────


async def push_alert(alert_data: dict):
    """Push an alert to all connected alert-stream clients.

    Called from the watchlist routes or Celery tasks when a price
    alert triggers.
    """
    await manager.broadcast_alert({
        "type": "alert",
        "data": alert_data,
    })


# ──────────────────────────────────────────────
# Order Notification Stream (Questrade Plus)
# ──────────────────────────────────────────────


@ws_router.websocket("/ws/orders")
async def order_notification_stream(
    websocket: WebSocket,
    api_key: str | None = Query(None),
    token: str | None = Query(None),
):
    """Real-time order status and execution push from Questrade.

    Obtains a Questrade notification port, connects to the upstream
    WebSocket, and relays events to the client.

    Message types::

        {"type": "order", "data": {"orderId": 123, "state": "Filled", ...}}
        {"type": "execution", "data": {"orderId": 123, "price": 195.50, ...}}
        {"type": "heartbeat", "data": {"ts": 1707...}}
    """
    if not await _ws_authenticate(websocket, api_key=api_key, token=token):
        return

    await websocket.accept()

    try:
        from app.engines.data_engine import DataEngine
        engine = DataEngine()

        # Get Questrade notification streaming port
        port_info = await engine.get_order_notification_port()
        stream_port = port_info.get("streamPort")

        if not stream_port:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Unable to obtain notification port from Questrade"},
            })
            await websocket.close()
            return

        # Connect to Questrade upstream WebSocket
        try:
            import websockets

            api_server = engine.questrade._api_server or ""
            api_server = api_server.rstrip("/")
            upstream_url = f"wss://{api_server.replace('https://', '')}:{stream_port}/"

            access_token = engine.questrade._access_token or ""

            async with websockets.connect(upstream_url) as upstream_ws:
                # Authenticate with Questrade
                await upstream_ws.send(access_token)

                log.info("ws.orders_connected", port=stream_port)

                last_heartbeat = time.monotonic()
                heartbeat_interval = 15.0

                while True:
                    try:
                        # Listen for upstream order events or timeout for heartbeat
                        raw = await asyncio.wait_for(
                            upstream_ws.recv(), timeout=heartbeat_interval
                        )
                        try:
                            event = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            event = {"raw": str(raw)}

                        # Determine event type
                        event_type = "order"
                        if "executions" in event or "executionId" in event:
                            event_type = "execution"

                        await websocket.send_json({
                            "type": event_type,
                            "data": event,
                        })
                        last_heartbeat = time.monotonic()

                    except asyncio.TimeoutError:
                        # Send heartbeat to keep connection alive
                        if time.monotonic() - last_heartbeat > heartbeat_interval:
                            try:
                                await websocket.send_json({
                                    "type": "heartbeat",
                                    "data": {"ts": int(time.time())},
                                })
                            except Exception:
                                break
                            last_heartbeat = time.monotonic()

                    # Check client still connected
                    if websocket.client_state != WebSocketState.CONNECTED:
                        break

        except ImportError:
            log.warning("ws.websockets_not_installed", msg="pip install websockets for order streaming")
            await websocket.send_json({
                "type": "error",
                "data": {"message": "websockets package not installed — order streaming unavailable"},
            })
        except Exception as upstream_exc:
            log.warning("ws.orders_upstream_failed", error=str(upstream_exc))
            # Fallback: poll order status via REST every 5 seconds
            await websocket.send_json({
                "type": "info",
                "data": {"message": "Upstream connection failed, falling back to polling"},
            })

            last_heartbeat = time.monotonic()
            while True:
                try:
                    # Poll latest orders from Questrade
                    orders = await engine.questrade.get_orders()
                    await websocket.send_json({
                        "type": "order_snapshot",
                        "data": {"orders": orders},
                    })
                    last_heartbeat = time.monotonic()
                    await asyncio.sleep(5.0)
                except Exception:
                    break

                if websocket.client_state != WebSocketState.CONNECTED:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.error("ws.orders_stream_error", error=str(exc))
    finally:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception:
            pass

