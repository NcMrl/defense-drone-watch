"""Fixtures de test : base PostgreSQL dédiée, serveur HTTP local servant des flux, client API.

Les tests n'exigent aucune clé API ni accès Internet.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from email.utils import format_datetime
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

os.environ["DDW_DATABASE_URL"] = os.getenv(
    "DDW_TEST_DATABASE_URL", "postgresql+psycopg://ddw@localhost:5433/ddw_test"
)
os.environ["DDW_ALLOW_PRIVATE_HOSTS"] = "1"  # le serveur de test écoute sur 127.0.0.1
os.environ["DDW_ADMIN_TOKEN"] = "jeton-admin-de-test"
os.environ["DDW_RATE_LIMIT_PER_MINUTE"] = "0"
os.environ.pop("DDW_READ_TOKEN", None)
os.environ.pop("DDW_X_BEARER_TOKEN", None)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import get_engine, get_sessionmaker  # noqa: E402
from app.services import net  # noqa: E402

ADMIN = {"Authorization": "Bearer jeton-admin-de-test"}
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    with get_engine().begin() as conn:
        tables = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'")
        ).scalars().all()
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    net.clear_robots_cache()
    yield


@pytest.fixture
def db():
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ------------------------------------------------------------------ serveur HTTP local

@dataclass
class Route:
    body: bytes
    status: int = 200
    content_type: str = "application/rss+xml; charset=utf-8"
    etag: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class FeedServer:
    def __init__(self) -> None:
        self.routes: dict[str, Route] = {}
        self.requests: list[tuple[str, dict[str, str]]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # silence
                pass

            def do_GET(self) -> None:  # noqa: N802
                server.requests.append((self.path, dict(self.headers)))
                route = server.routes.get(self.path)
                if route is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                if route.etag and self.headers.get("If-None-Match") == route.etag:
                    self.send_response(304)
                    self.end_headers()
                    return
                self.send_response(route.status)
                self.send_header("Content-Type", route.content_type)
                if route.etag:
                    self.send_header("ETag", route.etag)
                for k, v in route.headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(route.body)))
                self.end_headers()
                self.wfile.write(route.body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def url(self, path: str) -> str:
        return self.base + path

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def feed_server() -> Iterator[FeedServer]:
    server = FeedServer()
    yield server
    server.close()


def rss(items: list[dict], language: str = "fr") -> bytes:
    """Construit un flux RSS 2.0. Chaque item : title, link, description, date (datetime)."""
    entries = []
    for it in items:
        date = it.get("date") or datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)
        entries.append(
            "<item>"
            f"<title><![CDATA[{it['title']}]]></title>"
            f"<link>{it['link']}</link>"
            f"<guid>{it['link']}</guid>"
            f"<description><![CDATA[{it.get('description', '')}]]></description>"
            f"<pubDate>{format_datetime(date)}</pubDate>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        f"<title>Flux de test</title><link>https://test.example</link><language>{language}</language>"
        + "".join(entries)
        + "</channel></rss>"
    ).encode("utf-8")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
