"""Authentification par jetons (MVP), limitation de débit et en-têtes de sécurité.

MVP : deux jetons d'API (lecture facultatif, administration obligatoire pour toute écriture).
Phase 7 : comptes utilisateurs, rôles lecteur/analyste/administrateur, sessions.
"""

from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from app.models import AuditLog

_bearer = HTTPBearer(auto_error=False)


def _matches(provided: str | None, expected: str | None) -> bool:
    return bool(provided and expected and hmac.compare_digest(provided.encode(), expected.encode()))


def require_read(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    s = get_settings()
    if not s.read_token:
        return "anonyme"
    token = creds.credentials if creds else None
    if _matches(token, s.read_token) or _matches(token, s.admin_token):
        return "lecteur"
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton de lecture requis")


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    s = get_settings()
    if not s.admin_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Écritures désactivées : définissez DDW_ADMIN_TOKEN dans l'environnement du serveur.",
        )
    if _matches(creds.credentials if creds else None, s.admin_token):
        return "admin"
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton d'administration requis")


def audit(db: Session, actor: str, action: str, target: str | None = None, **details) -> None:
    db.add(AuditLog(actor=actor, action=action, target=target, details=details))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fenêtre glissante d'une minute par adresse IP (mémoire locale du processus)."""

    def __init__(self, app, limit_per_minute: int) -> None:  # noqa: ANN001
        super().__init__(app)
        self.limit = limit_per_minute
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001, ANN201
        if self.limit <= 0 or not request.url.path.startswith("/api"):
            return await call_next(request)
        key = request.client.host if request.client else "inconnu"
        now = time.monotonic()
        window = self.hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.limit:
            return JSONResponse({"detail": "Trop de requêtes, réessayez dans une minute."}, status_code=429)
        window.append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # noqa: ANN001, ANN201
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response
