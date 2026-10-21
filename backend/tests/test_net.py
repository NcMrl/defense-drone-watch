import dataclasses

import pytest

from app.config import get_settings
from app.services import net
from app.services.net import FetchError, assert_public_url, fetch
from tests.conftest import Route


@pytest.fixture
def strict(monkeypatch):
    """Réactive la garde SSRF (désactivée globalement pour le serveur de test local)."""
    settings = dataclasses.replace(get_settings(), allow_private_hosts=False)
    monkeypatch.setattr(net, "get_settings", lambda: settings)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "gopher://x", "javascript:alert(1)"])
def test_rejects_non_http_schemes(url):
    with pytest.raises(FetchError) as exc:
        assert_public_url(url)
    assert exc.value.permanent


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://localhost:8000/", "http://10.0.0.5/", "http://169.254.169.254/latest/meta-data"])
def test_ssrf_guard_rejects_private_addresses(strict, url):
    with pytest.raises(FetchError, match="SSRF"):
        assert_public_url(url)


def test_robots_disallow_is_respected(feed_server):
    feed_server.routes["/robots.txt"] = Route(b"User-agent: *\nDisallow: /prive/\n", content_type="text/plain")
    feed_server.routes["/prive/flux.xml"] = Route(b"<rss/>")
    with pytest.raises(FetchError, match="robots.txt") as exc:
        fetch(feed_server.url("/prive/flux.xml"))
    assert exc.value.permanent


def test_redirects_are_followed_and_revalidated(feed_server):
    feed_server.routes["/ancien"] = Route(b"", status=301, headers={"Location": "/nouveau"})
    feed_server.routes["/nouveau"] = Route(b"ok")
    resp = fetch(feed_server.url("/ancien"))
    assert resp.status == 200 and resp.content == b"ok" and resp.url.endswith("/nouveau")


def test_oversized_response_rejected(feed_server, monkeypatch):
    settings = dataclasses.replace(get_settings(), max_response_bytes=100)
    monkeypatch.setattr(net, "get_settings", lambda: settings)
    feed_server.routes["/gros"] = Route(b"x" * 1000)
    with pytest.raises(FetchError, match="volumineuse"):
        fetch(feed_server.url("/gros"))


def test_trusted_proxy_mode_still_blocks_literal_private_hosts(monkeypatch):
    settings = dataclasses.replace(get_settings(), allow_private_hosts=False, trust_egress_proxy=True)
    monkeypatch.setattr(net, "get_settings", lambda: settings)
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(net.socket.gaierror()))
    assert_public_url("https://flux.example/rss")  # résolution déléguée au proxy
    for url in ("http://localhost/", "http://127.0.0.1/", "http://[::1]/", "http://192.168.1.10/"):
        with pytest.raises(FetchError, match="SSRF"):
            assert_public_url(url)


def test_dns_failure_without_trusted_proxy_is_explicit(monkeypatch):
    settings = dataclasses.replace(get_settings(), allow_private_hosts=False, trust_egress_proxy=False)
    monkeypatch.setattr(net, "get_settings", lambda: settings)
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(net.socket.gaierror()))
    with pytest.raises(FetchError, match="DDW_TRUST_EGRESS_PROXY"):
        assert_public_url("https://flux.example/rss")
