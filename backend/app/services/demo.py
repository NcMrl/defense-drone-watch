"""Mode démonstration : données ENTIÈREMENT SYNTHÉTIQUES.

- Entreprises, produits, programmes et articles sont inventés.
- Les URL utilisent le domaine réservé `.example` (RFC 2606) : elles ne pointent vers rien de réel.
- Chaque titre est préfixé « [DÉMO] » et chaque ligne porte `is_synthetic = true`.
Les données passent par le vrai pipeline d'ingestion (normalisation, déduplication, alertes).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.connectors.base import RawItem
from app.models import Company, Document, Product, Source, WatchRule
from app.services.ingest import ingest_items

DEMO_PREFIX = "[DÉMO] "

COMPANIES = [
    ("Aérovigie (fictive)", ["Aerovigie"], "FR"),
    ("NordLynx Robotics (fictive)", ["NordLynx"], "GB"),
    ("Helios Propulsion (fictive)", ["Helios Propulsion"], "DE"),
    ("Kestrel Dynamics (fictive)", ["Kestrel Dynamics"], "US"),
]
PRODUCTS = [
    ("Programme FAUCON-D (fictif)", ["FAUCON-D"], "Aérovigie (fictive)", "drones_aeriens"),
    ("Système VEILLEUR (fictif)", ["VEILLEUR"], "NordLynx Robotics (fictive)", "anti_drones"),
]


def _items(now: datetime) -> dict[str, list[RawItem]]:
    d = lambda days, hours=0: now - timedelta(days=days, hours=hours)  # noqa: E731
    agence = "https://agence.demo.example"
    revue = "https://revue.demo.example"
    return {
        "agence": [
            RawItem(f"{agence}/communiques/faucon-d-commande", "Aérovigie notifiée d'une commande pour le programme FAUCON-D",
                    "Le ministère fictif annonce une commande de drones de surveillance auprès d'Aérovigie dans le cadre du programme FAUCON-D. Les livraisons sont annoncées pour une date non précisée.", "Service presse fictif", d(0, 3)),
            RawItem(f"{agence}/communiques/lutte-anti-drones-essais", "Campagne d'essais de lutte anti-drones en France avec le système VEILLEUR",
                    "Une campagne d'essais du système anti-drone VEILLEUR de NordLynx a été annoncée. Aucune performance n'est communiquée.", None, d(1, 2)),
            RawItem(f"{agence}/communiques/salon-demo", "Présentation de nouveaux drones au salon fictif DemoExpo",
                    "Plusieurs industriels présenteront des drones et des capteurs optroniques lors du salon fictif DemoExpo.", None, d(2)),
            RawItem(f"{agence}/communiques/reglementation", "Nouvelle réglementation fictive sur la certification des drones",
                    "Un texte fictif précise les règles de certification des systèmes de drones pour les essais en vol.", None, d(4)),
        ],
        "revue": [
            # Reprise du communiqué sous une autre URL, avec paramètres de suivi et titre légèrement modifié
            RawItem(f"{revue}/news/aerovigie-faucon-d?utm_source=rss&utm_medium=feed", "Aerovigie notifiée d'une commande pour le programme FAUCON-D",
                    "Selon le communiqué officiel fictif, Aérovigie reçoit une commande de drones de surveillance.", "Rédaction fictive", d(0, 1)),
            RawItem(f"{revue}/news/nordlynx-partnership", "NordLynx Robotics and Kestrel Dynamics announce a counter-UAS partnership",
                    "The two fictional companies announced a partnership on counter-UAS sensors and radar integration in the United Kingdom.", "Fictional desk", d(1)),
            RawItem(f"{revue}/news/helios-hydrogen", "Helios Propulsion unveils hydrogen fuel cell for long-endurance drones",
                    "The fictional German company presented a fuel cell prototype. The company claims extended endurance; no independent test has been reported.", None, d(3)),
            RawItem(f"{revue}/news/swarm-autonomy", "Kestrel Dynamics completes swarm autonomy trial in the United States",
                    "The fictional company states it completed a swarm autonomy trial. Details remain limited to the company's own statement.", None, d(5)),
            RawItem(f"{revue}/news/battery-factory", "Ouverture d'une usine de batteries pour drones en Pologne",
                    "Un industriel fictif annonce l'ouverture d'une usine de production de batteries destinées aux drones en Pologne.", None, d(6)),
            RawItem(f"{revue}/news/loitering-market", "European tender for loitering munitions draws several bids",
                    "A fictional European procurement tender for loitering munitions has reportedly received several bids, according to unnamed sources.", None, d(2, 5)),
        ],
    }


def seed_demo(session: Session) -> dict:
    if session.scalar(select(Source).where(Source.is_synthetic.is_(True)).limit(1)):
        return {"status": "deja_present"}

    companies: dict[str, Company] = {}
    for name, aliases, country in COMPANIES:
        c = Company(name=name, aliases=aliases, country=country, website=None, is_synthetic=True)
        session.add(c)
        companies[name] = c
    session.flush()
    for name, aliases, company, category in PRODUCTS:
        session.add(Product(name=name, aliases=aliases, company_id=companies[company].id,
                            category=category, announced_status=None, is_synthetic=True))

    session.add_all([
        WatchRule(name="[DÉMO] Lutte anti-drones", categories=["anti_drones"], severity="important"),
        WatchRule(name="[DÉMO] Suivi NordLynx", keywords=["NordLynx"], severity="critique"),
        WatchRule(name="[DÉMO] Contrats drones France", keywords=["commande", "contrat"], countries=[], categories=["drones_aeriens"], severity="info"),
    ])

    agence = Source(name="[DÉMO] Agence d'acquisition fictive", url="https://agence.demo.example/flux.xml",
                    homepage="https://agence.demo.example", source_type="officielle", country="FR", language="fr",
                    enabled=False, is_synthetic=True, verification_status="non_verifiee",
                    verification_note="Source synthétique : non collectée.")
    revue = Source(name="[DÉMO] Revue spécialisée fictive", url="https://revue.demo.example/rss",
                   homepage="https://revue.demo.example", source_type="media_specialise", country="GB", language="en",
                   enabled=False, is_synthetic=True, verification_status="non_verifiee",
                   verification_note="Source synthétique : non collectée.")
    panne = Source(name="[DÉMO] Source en erreur simulée", url="https://indisponible.demo.example/flux.xml",
                   source_type="industrielle", enabled=False, is_synthetic=True, consecutive_failures=3,
                   verification_status="echec", last_error="[temporaire] [DÉMO] Erreur simulée : HTTP 503",
                   last_run_at=datetime.now(timezone.utc) - timedelta(minutes=20))
    session.add_all([agence, revue, panne])
    session.flush()

    now = datetime.now(timezone.utc)
    items = _items(now)
    for batch in items.values():
        for it in batch:
            it.title = DEMO_PREFIX + it.title
    counts_a = ingest_items(session, agence, items["agence"])
    counts_r = ingest_items(session, revue, items["revue"])
    agence.last_success_at = revue.last_success_at = now
    return {"status": "cree", "agence": counts_a, "revue": counts_r}


def purge_demo(session: Session) -> int:
    n = session.execute(delete(Document).where(Document.is_synthetic.is_(True))).rowcount
    session.execute(delete(WatchRule).where(WatchRule.name.like("[DÉMO]%")))
    session.execute(delete(Product).where(Product.is_synthetic.is_(True)))
    session.execute(delete(Company).where(Company.is_synthetic.is_(True)))
    session.execute(delete(Source).where(Source.is_synthetic.is_(True)))
    return n
