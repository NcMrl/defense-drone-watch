"""Recherche plein texte PostgreSQL et filtres.

Syntaxe de la requête (websearch_to_tsquery) :
  mots-clés          → tous les termes
  "expression exacte" → phrase
  -terme             → exclusion
  a or b             → alternative
Les accents sont ignorés (unaccent).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentEntity, Occurrence


@dataclass
class SearchFilters:
    q: str | None = None
    source_id: int | None = None
    language: str | None = None
    country: str | None = None
    category: str | None = None
    status: str | None = None
    event_type: str | None = None
    company_id: int | None = None
    product_id: int | None = None
    min_confidence: float | None = None
    min_relevance: float | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    collected_from: datetime | None = None
    collected_to: datetime | None = None
    synthetic: str = "include"  # include | exclude | only
    sort: str = "recent"  # recent | pertinence | publication


def _tsquery(q: str):
    return func.websearch_to_tsquery("simple", func.f_unaccent(q))


def build_query(f: SearchFilters) -> Select:
    stmt = select(Document)
    if f.q and f.q.strip():
        stmt = stmt.where(Document.search_vector.op("@@")(_tsquery(f.q.strip())))
    if f.source_id is not None:
        stmt = stmt.where(
            Document.id.in_(select(Occurrence.document_id).where(Occurrence.source_id == f.source_id))
        )
    if f.company_id is not None:
        stmt = stmt.where(
            Document.id.in_(select(DocumentEntity.document_id).where(DocumentEntity.company_id == f.company_id))
        )
    if f.product_id is not None:
        stmt = stmt.where(
            Document.id.in_(select(DocumentEntity.document_id).where(DocumentEntity.product_id == f.product_id))
        )
    if f.language:
        stmt = stmt.where(Document.language == f.language)
    if f.country:
        stmt = stmt.where(Document.countries.contains([f.country]))
    if f.category:
        stmt = stmt.where(Document.categories.contains([f.category]))
    if f.status:
        stmt = stmt.where(Document.status == f.status)
    if f.event_type:
        stmt = stmt.where(Document.event_type == f.event_type)
    if f.min_confidence is not None:
        stmt = stmt.where(Document.confidence >= f.min_confidence)
    if f.min_relevance is not None:
        stmt = stmt.where(Document.relevance >= f.min_relevance)
    if f.published_from:
        stmt = stmt.where(Document.published_at >= f.published_from)
    if f.published_to:
        stmt = stmt.where(Document.published_at <= f.published_to)
    if f.collected_from:
        stmt = stmt.where(Document.first_seen_at >= f.collected_from)
    if f.collected_to:
        stmt = stmt.where(Document.first_seen_at <= f.collected_to)
    if f.synthetic == "exclude":
        stmt = stmt.where(Document.is_synthetic.is_(False))
    elif f.synthetic == "only":
        stmt = stmt.where(Document.is_synthetic.is_(True))
    return stmt


def search(session: Session, f: SearchFilters, page: int = 1, page_size: int = 25) -> tuple[int, list[Document]]:
    base = build_query(f)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    stmt = base
    if f.sort == "pertinence" and f.q:
        stmt = stmt.order_by(func.ts_rank(Document.search_vector, _tsquery(f.q.strip())).desc(), Document.id.desc())
    elif f.sort == "publication":
        stmt = stmt.order_by(Document.published_at.desc().nulls_last(), Document.id.desc())
    else:
        stmt = stmt.order_by(Document.first_seen_at.desc(), Document.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    return total, list(session.scalars(stmt))
