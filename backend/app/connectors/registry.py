"""Registre des types de connecteurs. Ajouter un connecteur = créer la classe et l'enregistrer ici."""

from __future__ import annotations

from app.connectors.base import Connector
from app.connectors.rss import RssConnector
from app.connectors.social import LinkedInConnector, XConnector

CONNECTORS: dict[str, type[Connector]] = {
    cls.type: cls for cls in (RssConnector, XConnector, LinkedInConnector)
}


def get_connector_class(connector_type: str) -> type[Connector]:
    try:
        return CONNECTORS[connector_type]
    except KeyError as exc:
        raise ValueError(f"Type de connecteur inconnu : {connector_type}") from exc


def describe_connectors() -> list[dict]:
    out = []
    for cls in CONNECTORS.values():
        status = cls.status()
        out.append(
            {
                "type": cls.type,
                "label": cls.label,
                "implemented": cls.implemented,
                "configured": status.configured,
                "status_message": status.message,
                "access_method": cls.access_method,
                "limits": cls.limits,
                "terms": cls.terms,
                "default_interval_minutes": cls.default_interval_minutes,
                "required_env": list(cls.required_env),
            }
        )
    return out
