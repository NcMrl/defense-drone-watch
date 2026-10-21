"""Application FastAPI."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import router
from app.config import get_settings
from app.logging_config import configure_logging
from app.security import RateLimitMiddleware, SecurityHeadersMiddleware

configure_logging()
log = logging.getLogger("ddw.api")
settings = get_settings()

app = FastAPI(
    title="Defense Drone Watch — API",
    version="0.1.0",
    description="Veille technologique en sources ouvertes : drones et munitions téléopérées (secteur défense).",
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse({"detail": "Requête invalide", "erreurs": exc.errors()}, status_code=422)


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Erreur non gérée sur %s", request.url.path)
    return JSONResponse({"detail": "Erreur interne du serveur"}, status_code=500)
