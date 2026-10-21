"""Modèle de données relationnel. Horodatages en UTC (timestamptz).

Voir docs/MODELE_DONNEES.md pour la description de chaque table.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


TS = DateTime(timezone=True)

SOURCE_TYPES = (
    "officielle",
    "industrielle",
    "media_specialise",
    "scientifique",
    "secondaire",
    "sociale",
    "non_verifiee",
)
DOCUMENT_STATUSES = (
    "collecte",
    "en_analyse",
    "a_verifier",
    "corrobore",
    "conteste",
    "archive",
)
VERIFICATION_STATUSES = ("non_verifiee", "verifiee", "echec")
SEVERITIES = ("info", "important", "critique")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(2000))
    homepage: Mapped[str | None] = mapped_column(String(2000))
    connector_type: Mapped[str] = mapped_column(String(50), default="rss")
    source_type: Mapped[str] = mapped_column(String(30), default="non_verifiee")
    reliability: Mapped[float | None] = mapped_column(Float)
    country: Mapped[str | None] = mapped_column(String(8))
    language: Mapped[str | None] = mapped_column(String(8))
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    verification_status: Mapped[str] = mapped_column(String(20), default="non_verifiee")
    verification_note: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    # État de collecte
    etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(200))
    last_run_at: Mapped[datetime | None] = mapped_column(TS)
    last_success_at: Mapped[datetime | None] = mapped_column(TS)
    next_run_at: Mapped[datetime | None] = mapped_column(TS)
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("url", name="uq_sources_url"),
        Index("ix_sources_due", "enabled", "next_run_at"),
    )


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(TS)
    status: Mapped[str] = mapped_column(String(20), default="en_cours")
    not_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    items_fetched: Mapped[int] = mapped_column(Integer, default=0)
    docs_created: Mapped[int] = mapped_column(Integer, default=0)
    docs_updated: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_kind: Mapped[str | None] = mapped_column(String(20))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_runs_source_started", "source_id", "started_at"),)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    title_norm: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(String(2000))
    domain: Mapped[str] = mapped_column(String(300))
    author: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[datetime | None] = mapped_column(TS)
    first_seen_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    last_checked_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    language: Mapped[str | None] = mapped_column(String(8))
    source_country: Mapped[str | None] = mapped_column(String(8))
    countries: Mapped[list[str]] = mapped_column(ARRAY(String(8)), default=list)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    event_type: Mapped[str | None] = mapped_column(String(50))
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float | None] = mapped_column(Float)
    confidence_details: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="collecte")
    processing_state: Mapped[str] = mapped_column(String(30), default="normalise")
    content_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    first_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('simple', f_unaccent(coalesce(title, ''))), 'A') || "
            "setweight(to_tsvector('simple', f_unaccent(coalesce(summary, ''))), 'B')",
            persisted=True,
        ),
    )

    occurrences: Mapped[list[Occurrence]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Occurrence.discovered_at"
    )

    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_documents_canonical_url"),
        Index("ix_documents_content_hash", "content_hash"),
        Index("ix_documents_published", "published_at"),
        Index("ix_documents_first_seen", "first_seen_at"),
        Index("ix_documents_search", "search_vector", postgresql_using="gin"),
        Index(
            "ix_documents_title_trgm",
            "title_norm",
            postgresql_using="gin",
            postgresql_ops={"title_norm": "gin_trgm_ops"},
        ),
        Index("ix_documents_categories", "categories", postgresql_using="gin"),
        Index("ix_documents_countries", "countries", postgresql_using="gin"),
    )


class Occurrence(Base):
    """Apparition d'un document dans une source (conservée même après fusion)."""

    __tablename__ = "occurrences"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(2000))
    raw_title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(TS)
    discovered_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    match_type: Mapped[str] = mapped_column(String(30), default="origine")
    match_score: Mapped[float | None] = mapped_column(Float)

    document: Mapped[Document] = relationship(back_populates="occurrences")
    source: Mapped[Source] = relationship()

    __table_args__ = (
        UniqueConstraint("source_id", "url", name="uq_occurrence_source_url"),
        Index("ix_occurrences_document", "document_id"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    recorded_at: Mapped[datetime] = mapped_column(TS, default=utcnow)

    __table_args__ = (UniqueConstraint("document_id", "version", name="uq_doc_version"),)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(200)), default=list)
    country: Mapped[str | None] = mapped_column(String(8))
    website: Mapped[str | None] = mapped_column(String(500))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Product(Base):
    """Produit ou programme. Les champs inconnus restent NULL (jamais complétés artificiellement)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(200)), default=list)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    category: Mapped[str | None] = mapped_column(String(50))
    announced_status: Mapped[str | None] = mapped_column(String(30))
    country: Mapped[str | None] = mapped_column(String(8))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class DocumentEntity(Base):
    """Mention d'une entreprise ou d'un produit dans un document (détection par dictionnaire)."""

    __tablename__ = "document_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    matched_text: Mapped[str] = mapped_column(String(200))
    method: Mapped[str] = mapped_column(String(30), default="dictionnaire")

    __table_args__ = (
        UniqueConstraint("document_id", "company_id", "product_id", name="uq_doc_entity"),
        Index("ix_doc_entities_company", "company_id"),
        Index("ix_doc_entities_product", "product_id"),
    )


class WatchRule(Base):
    __tablename__ = "watch_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(200)), default=list)
    exclude_keywords: Mapped[list[str]] = mapped_column(ARRAY(String(200)), default=list)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    countries: Mapped[list[str]] = mapped_column(ARRAY(String(8)), default=list)
    company_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("watch_rules.id", ondelete="CASCADE"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    severity: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(TS)

    rule: Mapped[WatchRule] = relationship()
    document: Mapped[Document] = relationship()

    __table_args__ = (
        # Anti-doublon : une règle ne notifie qu'une fois par document (doublons fusionnés inclus).
        UniqueConstraint("rule_id", "document_id", name="uq_alert_rule_document"),
        Index("ix_alerts_created", "created_at"),
    )


class SavedView(Base):
    __tablename__ = "saved_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (Index("ix_audit_at", "at"),)
