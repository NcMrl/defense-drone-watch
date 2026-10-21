"""Configuration chargée depuis les variables d'environnement (aucun secret dans le code)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "oui", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str
    admin_token: str | None
    read_token: str | None
    allow_private_hosts: bool
    trust_egress_proxy: bool
    user_agent: str
    http_timeout_s: float
    max_response_bytes: int
    respect_robots: bool
    worker_concurrency: int
    worker_poll_s: int
    dedup_title_threshold: float
    dedup_window_days: int
    rate_limit_per_minute: int
    cors_origins: list[str] = field(default_factory=list)
    scoring: dict = field(default_factory=dict)


def _load_scoring() -> dict:
    path = Path(os.getenv("DDW_SCORING_FILE", str(BASE_DIR / "scoring.json")))
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DDW_DATABASE_URL", "postgresql+psycopg://ddw@localhost:5432/ddw"
        ),
        admin_token=os.getenv("DDW_ADMIN_TOKEN") or None,
        read_token=os.getenv("DDW_READ_TOKEN") or None,
        allow_private_hosts=_bool("DDW_ALLOW_PRIVATE_HOSTS", False),
        trust_egress_proxy=_bool("DDW_TRUST_EGRESS_PROXY", False),
        user_agent=os.getenv(
            "DDW_USER_AGENT",
            "DefenseDroneWatch/0.1 (veille sources ouvertes; contact: a-configurer)",
        ),
        http_timeout_s=float(os.getenv("DDW_HTTP_TIMEOUT_S", "20")),
        max_response_bytes=_int("DDW_MAX_RESPONSE_BYTES", 5 * 1024 * 1024),
        respect_robots=_bool("DDW_RESPECT_ROBOTS", True),
        worker_concurrency=_int("DDW_WORKER_CONCURRENCY", 4),
        worker_poll_s=_int("DDW_WORKER_POLL_S", 30),
        dedup_title_threshold=float(os.getenv("DDW_DEDUP_TITLE_THRESHOLD", "0.88")),
        dedup_window_days=_int("DDW_DEDUP_WINDOW_DAYS", 7),
        rate_limit_per_minute=_int("DDW_RATE_LIMIT_PER_MINUTE", 240),
        cors_origins=[
            o.strip()
            for o in os.getenv("DDW_CORS_ORIGINS", "http://localhost:3000").split(",")
            if o.strip()
        ],
        scoring=_load_scoring(),
    )
