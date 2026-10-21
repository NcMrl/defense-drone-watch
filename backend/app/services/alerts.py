"""Évaluation des règles de veille et création d'alertes (anti-doublon par contrainte unique)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Alert, Document, WatchRule
from app.services.normalize import normalize_for_compare


def rule_matches(rule: WatchRule, doc: Document, company_ids: list[int]) -> str | None:
    """Renvoie la raison du déclenchement, ou None. Tous les critères renseignés doivent être satisfaits."""
    has_criteria = any([rule.keywords, rule.categories, rule.countries, rule.company_ids])
    if not has_criteria:
        return None
    text = f" {normalize_for_compare(f'{doc.title} {doc.summary or ''}')} "
    reasons: list[str] = []

    if rule.exclude_keywords and any(
        f" {normalize_for_compare(k)} " in text for k in rule.exclude_keywords
    ):
        return None
    if rule.keywords:
        hits = [k for k in rule.keywords if f" {normalize_for_compare(k)} " in text]
        if not hits:
            return None
        reasons.append("mots-clés : " + ", ".join(hits))
    if rule.categories:
        hits = sorted(set(rule.categories) & set(doc.categories or []))
        if not hits:
            return None
        reasons.append("catégories : " + ", ".join(hits))
    if rule.countries:
        hits = sorted(set(rule.countries) & set(doc.countries or []))
        if not hits:
            return None
        reasons.append("pays : " + ", ".join(hits))
    if rule.company_ids:
        hits = sorted(set(rule.company_ids) & set(company_ids))
        if not hits:
            return None
        reasons.append(f"entreprises suivies : {len(hits)}")
    return " ; ".join(reasons)


def evaluate_rules(session: Session, doc: Document, company_ids: list[int]) -> int:
    """Crée les alertes pour un document. Renvoie le nombre d'alertes réellement créées."""
    created = 0
    rules = session.scalars(select(WatchRule).where(WatchRule.enabled.is_(True))).all()
    for rule in rules:
        reason = rule_matches(rule, doc, company_ids)
        if reason is None:
            continue
        result = session.execute(
            insert(Alert)
            .values(rule_id=rule.id, document_id=doc.id, severity=rule.severity, reason=reason)
            .on_conflict_do_nothing(constraint="uq_alert_rule_document")
            .returning(Alert.id)
        )
        if result.scalar_one_or_none() is not None:
            created += 1
    return created
