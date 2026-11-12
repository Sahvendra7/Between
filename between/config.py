"""Settings from the environment. Sandbox only: there is no live PayPal setting."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///between.db"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    secret: str = ""
    base_url: str = "http://127.0.0.1:8000"
    demo_mode: bool = True
    secure_cookies: bool = False
    demo_parent_a_email: str = ""
    demo_parent_b_email: str = ""
    money_ai: bool = False  # the Ledger guide (BETWEEN_MONEY_AI=1); demo mode only
    ag_studio_license: str = ""  # AG Grid supplies one for judging; without it Studio shows a watermark
    frontend_origins: tuple[str, ...] = ()  # BETWEEN_FRONTEND_ORIGINS: the Next.js frontend(s) that proxy to this backend


def _flag(value: str | None, default: bool) -> bool:
    return default if value in (None, "") else value.strip().lower() in ("1", "true", "yes")


def load(env: Mapping[str, str] = os.environ) -> Settings:
    url = env.get("DATABASE_URL") or Settings.database_url
    if url.startswith("postgres://"):  # Render hands out this scheme; SQLAlchemy wants the driver named
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return Settings(
        database_url=url,
        paypal_client_id=env.get("PAYPAL_CLIENT_ID", ""),
        paypal_client_secret=env.get("PAYPAL_CLIENT_SECRET", ""),
        paypal_webhook_id=env.get("PAYPAL_WEBHOOK_ID", ""),
        anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
        gemini_api_key=env.get("GEMINI_API_KEY") or None,
        secret=env.get("BETWEEN_SECRET", ""),
        base_url=(env.get("BETWEEN_BASE_URL") or Settings.base_url).rstrip("/"),
        demo_mode=_flag(env.get("BETWEEN_DEMO_MODE"), True),
        secure_cookies=_flag(env.get("BETWEEN_SECURE_COOKIES"), False),
        demo_parent_a_email=env.get("DEMO_PARENT_A_EMAIL", ""),
        demo_parent_b_email=env.get("DEMO_PARENT_B_EMAIL", ""),
        money_ai=_flag(env.get("BETWEEN_MONEY_AI"), False),
        ag_studio_license=env.get("AG_STUDIO_LICENSE", ""),
        frontend_origins=tuple(o.strip().rstrip("/") for o in env.get("BETWEEN_FRONTEND_ORIGINS", "").split(",") if o.strip()),
    )
