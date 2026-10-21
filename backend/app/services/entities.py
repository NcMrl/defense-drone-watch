"""Détection d'entreprises et de produits par dictionnaire (noms et variantes déclarés)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Company, DocumentEntity, Product
from app.services.normalize import normalize_for_compare


@dataclass
class EntityDictionary:
    companies: list[tuple[int, list[str]]]
    products: list[tuple[int, list[str]]]

    @classmethod
    def load(cls, session: Session) -> EntityDictionary:
        def terms(name: str, aliases: list[str] | None) -> list[str]:
            out = {normalize_for_compare(t) for t in [name, *(aliases or [])]}
            return [t for t in out if len(t) >= 3]

        companies = [(c.id, terms(c.name, c.aliases)) for c in session.scalars(select(Company))]
        products = [(p.id, terms(p.name, p.aliases)) for p in session.scalars(select(Product))]
        return cls(companies, products)

    def match(self, text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
        norm = f" {normalize_for_compare(text)} "

        def find(entries: list[tuple[int, list[str]]]) -> list[tuple[int, str]]:
            found = []
            for entity_id, terms in entries:
                hit = next((t for t in terms if f" {t} " in norm), None)
                if hit:
                    found.append((entity_id, hit))
            return found

        return find(self.companies), find(self.products)


def link_entities(session: Session, document_id: int, text: str, dictionary: EntityDictionary) -> list[int]:
    """Crée les liens document ↔ entités. Renvoie les identifiants d'entreprises détectées."""
    companies, products = dictionary.match(text)
    for company_id, hit in companies:
        session.execute(
            insert(DocumentEntity)
            .values(document_id=document_id, company_id=company_id, product_id=None, matched_text=hit)
            .on_conflict_do_nothing()
        )
    for product_id, hit in products:
        session.execute(
            insert(DocumentEntity)
            .values(document_id=document_id, company_id=None, product_id=product_id, matched_text=hit)
            .on_conflict_do_nothing()
        )
    return [cid for cid, _ in companies]
