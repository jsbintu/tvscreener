"""
Bubby Vision — Locust Load Testing

Usage:
    pip install locust
    locust -f locustfile.py --host http://localhost:8000

Dashboard: http://localhost:8089
"""

from locust import HttpUser, between, task


class Bubby VisionUser(HttpUser):
    """Simulates a typical Bubby Vision API consumer."""

    wait_time = between(0.5, 2.0)

    # ── Health & Metrics ──

    @task(5)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(1)
    def metrics(self):
        self.client.get("/metrics", name="/metrics")

    # ── Stock Data ──

    @task(10)
    def get_stock_apple(self):
        self.client.get("/v1/api/stock/AAPL", name="/v1/api/stock/{ticker}")

    @task(8)
    def get_stock_tesla(self):
        self.client.get("/v1/api/stock/TSLA", name="/v1/api/stock/{ticker}")

    @task(5)
    def get_stock_nvidia(self):
        self.client.get("/v1/api/stock/NVDA", name="/v1/api/stock/{ticker}")

    # ── Options ──

    @task(3)
    def get_options(self):
        self.client.get("/v1/api/options/AAPL", name="/v1/api/options/{ticker}")

    # ── Market Data ──

    @task(4)
    def get_fear_greed(self):
        self.client.get("/v1/api/fear-greed", name="/v1/api/fear-greed")

    @task(3)
    def get_movers(self):
        self.client.get("/v1/api/movers", name="/v1/api/movers")

    @task(2)
    def get_wsb(self):
        self.client.get("/v1/api/wsb/trending", name="/v1/api/wsb/trending")

    # ── Watchlist ──

    @task(3)
    def get_watchlist(self):
        self.client.get("/v1/api/watchlist", name="/v1/api/watchlist")

    @task(2)
    def get_alerts(self):
        self.client.get("/v1/api/alerts", name="/v1/api/alerts")

    # ── Extended Data ──

    @task(2)
    def get_sentiment(self):
        self.client.get("/v1/api/sentiment/AAPL", name="/v1/api/sentiment/{ticker}")

    @task(2)
    def get_news(self):
        self.client.get("/v1/api/news/AAPL", name="/v1/api/news/{ticker}")

    # ── Audit Log ──

    @task(1)
    def get_audit_log(self):
        self.client.get("/v1/api/audit-log?limit=10", name="/v1/api/audit-log")

    # ── Swagger Docs ──

    @task(1)
    def swagger_docs(self):
        self.client.get("/docs", name="/docs")
