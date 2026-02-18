"""
Bubby Vision — Configuration Management

Pydantic Settings: loads from .env, validates all configuration at startup.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ──
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-in-production"

    # ── JWT Authentication ──
    jwt_secret_key: str = "change-me-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_access_expiry_minutes: int = 30
    jwt_refresh_expiry_days: int = 7

    # ── Google Gemini ──
    google_api_key: str = ""

    # ── LangSmith ──
    langsmith_api_key: str = ""
    langsmith_project: str = "Bubby Vision"
    langsmith_tracing_v2: bool = True

    # ── QuestDB ──
    questdb_host: str = "localhost"
    questdb_port: int = 8812
    questdb_http_port: int = 9000

    @property
    def questdb_dsn(self) -> str:
        return f"postgresql://admin:quest@{self.questdb_host}:{self.questdb_port}/qdb"

    @property
    def questdb_http_url(self) -> str:
        return f"http://{self.questdb_host}:{self.questdb_http_port}"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── ChromaDB ──
    chromadb_host: str = "localhost"
    chromadb_port: int = 8100

    @property
    def chromadb_url(self) -> str:
        return f"http://{self.chromadb_host}:{self.chromadb_port}"

    # ── Data Source API Keys ──
    finnhub_api_key: str = ""
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True
    alpaca_feed: str = "iex"  # 'iex' (free), 'sip' (paid $99/mo), 'delayed_sip'

    quantdata_api_key: str = ""

    # ── FRED (Federal Reserve Economic Data) ──
    fred_api_key: str = ""

    # ── OptionStrats Scraping (always active) ──
    optionstrats_scrape_interval: int = 300  # seconds between flow scrapes
    optionstrats_iv_scrape_interval: int = 1800  # seconds between IV surface scrapes
    optionstrats_insider_scrape_interval: int = 900  # seconds between insider flow scrapes (15 min)
    playwright_headless: bool = True  # Set False for scraper debugging

    # ── TradingView ──
    tradingview_username: str = ""
    tradingview_password: str = ""

    # ── Questrade ──
    questrade_refresh_token: str = ""       # OAuth2 refresh token from Questrade
    questrade_account_id: str = ""          # Account number (for positions/balances)
    questrade_is_practice: bool = False     # True = practice server, False = live

    # ── Notifications ──
    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── CORS ──
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — created once, reused everywhere."""
    return Settings()
