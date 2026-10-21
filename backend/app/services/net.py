"""Accès HTTP sortant sécurisé : garde SSRF, redirections contrôlées, taille bornée, robots.txt.

Limite connue : entre la vérification DNS et la connexion, une résolution différente
(DNS rebinding) reste théoriquement possible. Atténuation prévue en phase 7 :
proxy sortant filtrant ou épinglage de l'IP résolue.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.config import get_settings


class FetchError(Exception):
    """Erreur de collecte. `permanent=True` : inutile de réessayer sans intervention."""

    def __init__(self, message: str, permanent: bool = False, status: int | None = None):
        super().__init__(message)
        self.permanent = permanent
        self.status = status


@dataclass
class HttpResponse:
    url: str
    status: int
    content: bytes
    headers: dict[str, str]


def assert_public_url(url: str) -> None:
    """Refuse les schémas non HTTP(S) et les hôtes résolvant vers des adresses non publiques."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise FetchError(f"Schéma refusé : {parts.scheme or '(vide)'}", permanent=True)
    if not parts.hostname:
        raise FetchError("URL sans hôte", permanent=True)
    settings = get_settings()
    if settings.allow_private_hosts:
        return
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise FetchError("Hôte refusé (localhost) : protection SSRF", permanent=True)
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise FetchError(f"Hôte refusé (adresse non publique {literal}) : protection SSRF", permanent=True)
    try:
        infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        if settings.trust_egress_proxy:
            # Réseau à proxy obligatoire sans DNS local : la résolution et le filtrage
            # sont délégués au proxy sortant (IP privées littérales et localhost déjà refusées).
            return
        raise FetchError(
            f"Résolution DNS impossible pour {host} "
            "(réseau à proxy obligatoire ? voir DDW_TRUST_EGRESS_PROXY)"
        ) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FetchError(
                f"Hôte refusé (adresse non publique {ip}) : protection SSRF", permanent=True
            )


REDIRECT_CODES = {301, 302, 303, 307, 308}  # 304 n'est PAS une redirection

_robots_cache: dict[str, tuple[float, RobotFileParser | None]] = {}
_ROBOTS_TTL_S = 6 * 3600


def _robots_for(url: str, client: httpx.Client) -> RobotFileParser | None:
    parts = urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    cached = _robots_cache.get(root)
    if cached and time.monotonic() - cached[0] < _ROBOTS_TTL_S:
        return cached[1]
    parser: RobotFileParser | None = RobotFileParser()
    try:
        resp = client.get(urljoin(root, "/robots.txt"), follow_redirects=False)
        if resp.status_code == 200:
            parser.parse(resp.text.splitlines())
        elif resp.status_code in (401, 403):
            parser.disallow_all = True
        else:  # 404 ou autre : pas de restriction déclarée
            parser = None
    except httpx.HTTPError:
        parser = None
    _robots_cache[root] = (time.monotonic(), parser)
    return parser


def clear_robots_cache() -> None:
    _robots_cache.clear()


def fetch(url: str, headers: dict[str, str] | None = None, max_redirects: int = 5) -> HttpResponse:
    """GET sécurisé. Chaque redirection est revalidée contre la garde SSRF."""
    settings = get_settings()
    base_headers = {"User-Agent": settings.user_agent, "Accept": "*/*"}
    base_headers.update(headers or {})
    current = url
    with httpx.Client(timeout=settings.http_timeout_s, follow_redirects=False) as client:
        for _ in range(max_redirects + 1):
            assert_public_url(current)
            if settings.respect_robots:
                robots = _robots_for(current, client)
                if robots is not None and not robots.can_fetch(settings.user_agent, current):
                    raise FetchError(f"Collecte interdite par robots.txt : {current}", permanent=True)
            try:
                with client.stream("GET", current, headers=base_headers) as resp:
                    if resp.status_code in REDIRECT_CODES:
                        location = resp.headers.get("location")
                        if not location:
                            raise FetchError("Redirection sans en-tête Location")
                        current = urljoin(current, location)
                        continue
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in resp.iter_bytes():
                        size += len(chunk)
                        if size > settings.max_response_bytes:
                            raise FetchError("Réponse trop volumineuse", permanent=True)
                        chunks.append(chunk)
                    return HttpResponse(
                        url=current,
                        status=resp.status_code,
                        content=b"".join(chunks),
                        headers={k.lower(): v for k, v in resp.headers.items()},
                    )
            except httpx.ProxyError as exc:
                raise FetchError(
                    "Le proxy sortant a refusé la connexion (domaine non autorisé par le réseau ?)"
                ) from exc
            except httpx.TimeoutException as exc:
                raise FetchError(f"Délai dépassé : {current}") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"Erreur réseau : {type(exc).__name__}") from exc
    raise FetchError("Trop de redirections", permanent=True)
