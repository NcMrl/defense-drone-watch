"""Schémas d'entrée/sortie de l'API (validation des entrées)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models import DOCUMENT_STATUSES, SEVERITIES, SOURCE_TYPES

SourceType = Literal[SOURCE_TYPES]  # type: ignore[valid-type]
DocStatus = Literal[DOCUMENT_STATUSES]  # type: ignore[valid-type]
Severity = Literal[SEVERITIES]  # type: ignore[valid-type]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SourceOut(ORM):
    id: int
    name: str
    url: str
    homepage: str | None
    connector_type: str
    source_type: str
    reliability: float | None
    country: str | None
    language: str | None
    categories: list[str]
    enabled: bool
    priority: int
    interval_minutes: int
    verification_status: str
    verification_note: str | None
    is_synthetic: bool
    last_run_at: datetime | None
    last_success_at: datetime | None
    next_run_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    health: str = "inconnu"
    document_count: int = 0


class SourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    url: HttpUrl
    homepage: HttpUrl | None = None
    connector_type: str = "rss"
    source_type: SourceType = "non_verifiee"
    reliability: float | None = Field(default=None, ge=0, le=1)
    country: str | None = Field(default=None, max_length=8)
    language: str | None = Field(default=None, max_length=8)
    categories: list[str] = Field(default_factory=list, max_length=20)
    enabled: bool = True
    priority: int = Field(default=5, ge=1, le=10)
    interval_minutes: int = Field(default=30, ge=5, le=10080)


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    source_type: SourceType | None = None
    reliability: float | None = Field(default=None, ge=0, le=1)
    country: str | None = Field(default=None, max_length=8)
    language: str | None = Field(default=None, max_length=8)
    categories: list[str] | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=10)
    interval_minutes: int | None = Field(default=None, ge=5, le=10080)


class RunOut(ORM):
    id: int
    source_id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    not_modified: bool
    items_fetched: int
    docs_created: int
    docs_updated: int
    duplicates: int
    errors: int
    error_message: str | None
    error_kind: str | None
    duration_ms: int | None


class OccurrenceOut(ORM):
    id: int
    source_id: int
    source_name: str
    url: str
    raw_title: str | None
    published_at: datetime | None
    discovered_at: datetime
    match_type: str
    match_score: float | None


class EntityRef(BaseModel):
    id: int
    name: str
    kind: Literal["entreprise", "produit"]
    is_synthetic: bool


class DocumentOut(ORM):
    id: int
    title: str
    summary: str | None
    canonical_url: str
    domain: str
    author: str | None
    published_at: datetime | None
    first_seen_at: datetime
    last_checked_at: datetime
    updated_at: datetime
    language: str | None
    source_country: str | None
    countries: list[str]
    categories: list[str]
    event_type: str | None
    relevance: float
    confidence: float | None
    status: str
    version: int
    is_synthetic: bool
    occurrence_count: int = 1
    source_name: str | None = None
    collection_delay_minutes: float | None = None
    entities: list[EntityRef] = []


class DocumentDetail(DocumentOut):
    confidence_details: dict
    occurrences: list[OccurrenceOut]
    versions: list[dict]


class DocumentPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[DocumentOut]
    generated_at: datetime


class DocumentStatusUpdate(BaseModel):
    status: DocStatus


class RuleIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    exclude_keywords: list[str] = Field(default_factory=list, max_length=50)
    categories: list[str] = Field(default_factory=list, max_length=20)
    countries: list[str] = Field(default_factory=list, max_length=30)
    company_ids: list[int] = Field(default_factory=list, max_length=50)
    severity: Severity = "info"
    enabled: bool = True

    @field_validator("keywords", "exclude_keywords")
    @classmethod
    def _strip(cls, v: list[str]) -> list[str]:
        return [k.strip()[:200] for k in v if k.strip()]


class RuleOut(ORM):
    id: int
    name: str
    keywords: list[str]
    exclude_keywords: list[str]
    categories: list[str]
    countries: list[str]
    company_ids: list[int]
    severity: str
    enabled: bool
    created_at: datetime


class AlertOut(ORM):
    id: int
    rule_id: int
    rule_name: str
    document_id: int
    document_title: str
    document_is_synthetic: bool
    severity: str
    reason: str
    created_at: datetime
    read_at: datetime | None


class ViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    filters: dict


class ViewOut(ORM):
    id: int
    name: str
    filters: dict
    created_at: datetime


class CompanyOut(ORM):
    id: int
    name: str
    aliases: list[str]
    country: str | None
    website: str | None
    is_synthetic: bool
    document_count: int = 0
