"""Connecteurs réseaux sociaux : interfaces déclarées, collecte NON implémentée (phase 6).

Ils apparaissent dans l'administration avec leur statut exact afin qu'aucun
utilisateur ne croie à une couverture inexistante.
"""

from __future__ import annotations

from app.connectors.base import CollectState, Connector, FetchResult
from app.services.net import FetchError


class XConnector(Connector):
    type = "x"
    label = "X (API officielle)"
    access_method = "API officielle X v2 (timelines de comptes, recherche récente selon l'offre souscrite)"
    limits = (
        "Accès, volumes et historique dépendent du niveau d'abonnement ; quotas mensuels stricts. "
        "Résultats jamais exhaustifs."
    )
    terms = "Conditions du X Developer Agreement ; pas de collecte hors API."
    default_interval_minutes = 60
    required_env = ("DDW_X_BEARER_TOKEN",)
    implemented = False
    setup_help = "Créer une application sur le portail développeur X puis renseigner DDW_X_BEARER_TOKEN (phase 6)."

    def fetch(self, state: CollectState) -> FetchResult:
        raise FetchError("Connecteur X non implémenté (phase 6)", permanent=True)


class LinkedInConnector(Connector):
    type = "linkedin"
    label = "LinkedIn (API officielle / saisie manuelle)"
    access_method = (
        "API officielle LinkedIn selon les permissions accordées (en pratique : pages administrées par le compte). "
        "Repli : liens saisis manuellement, imports, fournisseurs licenciés."
    )
    limits = (
        "L'API n'offre généralement pas la lecture des publications de pages ou personnes tierces. "
        "Aucune recherche exhaustive des publications n'est possible."
    )
    terms = "Pas de scraping ni de contournement des mécanismes anti-automatisation (conditions LinkedIn)."
    default_interval_minutes = 120
    required_env = ("DDW_LINKEDIN_CLIENT_ID", "DDW_LINKEDIN_CLIENT_SECRET")
    implemented = False
    setup_help = "Nécessite une application LinkedIn avec permissions validées par LinkedIn (phase 6)."

    def fetch(self, state: CollectState) -> FetchResult:
        raise FetchError("Connecteur LinkedIn non implémenté (phase 6)", permanent=True)
