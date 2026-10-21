"""Interface commune des connecteurs de collecte."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


@dataclass
class RawItem:
    """Élément brut tel que fourni par une source, avant normalisation."""

    url: str
    title: str
    summary: str = ""
    author: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    guid: str | None = None


@dataclass
class CollectState:
    """État incrémental persistant entre deux collectes."""

    etag: str | None = None
    last_modified: str | None = None
    cursor: str | None = None


@dataclass
class FetchResult:
    items: list[RawItem] = field(default_factory=list)
    not_modified: bool = False
    new_state: CollectState = field(default_factory=CollectState)
    feed_language: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class ConnectorStatus:
    configured: bool
    message: str


class Connector(ABC):
    """Contrat de tout connecteur.

    Les métadonnées de classe sont exposées dans l'interface d'administration :
    elles documentent la méthode d'accès, les limites et les conditions d'utilisation.
    """

    type: ClassVar[str]
    label: ClassVar[str]
    access_method: ClassVar[str]
    limits: ClassVar[str]
    terms: ClassVar[str]
    default_interval_minutes: ClassVar[int] = 30
    required_env: ClassVar[tuple[str, ...]] = ()
    implemented: ClassVar[bool] = True
    setup_help: ClassVar[str] = ""

    def __init__(self, url: str, config: dict | None = None):
        self.url = url
        self.config = config or {}

    @classmethod
    def status(cls) -> ConnectorStatus:
        if not cls.implemented:
            return ConnectorStatus(False, f"Interface uniquement — collecte non implémentée. {cls.setup_help}")
        missing = [name for name in cls.required_env if not os.getenv(name)]
        if missing:
            return ConnectorStatus(
                False, f"Non configuré : variable(s) manquante(s) {', '.join(missing)}. {cls.setup_help}"
            )
        return ConnectorStatus(True, "Configuré")

    @abstractmethod
    def fetch(self, state: CollectState) -> FetchResult:
        """Collecte incrémentale. Lève net.FetchError en cas d'échec (temporaire ou permanent)."""
