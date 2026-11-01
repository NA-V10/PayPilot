"""Application settings, loaded from environment variables / .env."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing import Annotated

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    app_name: str = "PayPilot"
    environment: str = "development"

    # Empty → local SQLite file, so the app runs with zero infrastructure.
    database_url: str = ""

    # LLM provider abstraction. "openai" works with any OpenAI-compatible endpoint; "none" disables it.
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 20.0

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_environment: str = "sandbox"
    # PayPal sandbox accounts settle most reliably in USD; INR amounts are converted
    # at the explicit FX rates below and the conversion is shown to the user.
    paypal_settlement_currency: str = "USD"
    # Where PayPal sends the buyer back after approving an order (redirect flow).
    frontend_url: str = "http://localhost:3000"

    demo_mode: bool = True

    # Optional API key. When set, every mutating endpoint requires `X-PayPilot-Key`.
    paypilot_api_key: str = ""

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Units of currency per 1 USD. Deterministic and auditable on purpose.
    fx_rates: dict[str, Decimal] = Field(
        default_factory=lambda: {
            "USD": Decimal("1"),
            "INR": Decimal("84"),
            "EUR": Decimal("0.92"),
            "GBP": Decimal("0.79"),
        }
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            url = self.database_url
            # Render/Neon hand out postgres:// URLs; SQLAlchemy needs an explicit driver.
            if url.startswith("postgres://"):
                url = "postgresql+psycopg://" + url[len("postgres://") :]
            elif url.startswith("postgresql://"):
                url = "postgresql+psycopg://" + url[len("postgresql://") :]
            return url
        return f"sqlite:///{(BACKEND_DIR / 'paypilot.db').as_posix()}"

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    @property
    def llm_configured(self) -> bool:
        return self.llm_provider != "none" and bool(self.openai_api_key)

    @property
    def paypal_base_url(self) -> str:
        if self.paypal_environment == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
