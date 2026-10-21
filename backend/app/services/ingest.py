"""Pipeline d'ingestion : normalisation → déduplication → persistance → qualification → alertes."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.connectors.base import CollectState, RawItem
from app.connectors.registry import get_connector_class
from app.models import CollectionRun, Document, DocumentVersion, Occurrence, Source
from app.services.alerts import evaluate_rules
from app.services.entities import EntityDictionary, link_entities
from app.services.net import FetchError
from app.services.normalize import (
    canonicalize_url,
    categorize,
    clean_text,
    content_hash,
    detect_countries,
    detect_language,
    domain_of,
    event_type,
    normalize_for_compare,
    relevance_score,
    title_similarity,
)
from app.services.scoring import compute_confidence

log = logging.getLogger("ddw.ingest")

MAX_BACKOFF = timedelta(hours=24)
CIRCUIT_THRESHOLD = 5


@dataclass
class IngestContext:
    entities: EntityDictionary
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    alerts_created: int = 0


def _digits(value: str) -> list[str]:
    return re.findall(r"\d+", value)


def _refresh_quality(session: Session, doc: Document, source: Source, now: datetime) -> None:
    # Domaine réel de chaque occurrence
    urls = session.scalars(select(Occurrence.url).where(Occurrence.document_id == doc.id)).all()
    distinct_domains = len({domain_of(u) for u in urls}) or 1
    first_source = session.get(Source, doc.first_source_id) if doc.first_source_id else source
    score, details = compute_confidence(
        source_type=first_source.source_type if first_source else "non_verifiee",
        source_reliability_value=first_source.reliability if first_source else None,
        distinct_domains=distinct_domains,
        reference_date=doc.published_at or doc.first_seen_at,
        now=now,
    )
    doc.confidence = score
    previous = doc.confidence_details or {}
    if "classification" in previous:  # conserver l'explication des catégories
        details["classification"] = previous["classification"]
    doc.confidence_details = details


def _find_similar(session: Session, title_norm: str, domain: str, ref: datetime) -> tuple[Document, float] | None:
    settings = get_settings()
    window = timedelta(days=settings.dedup_window_days)
    candidates = session.execute(
        select(Document)
        .where(
            Document.domain != domain,
            func.coalesce(Document.published_at, Document.first_seen_at).between(ref - window, ref + window),
            Document.title_norm.op("%")(title_norm),
        )
        .order_by(func.similarity(Document.title_norm, title_norm).desc())
        .limit(5)
    ).scalars().all()
    for cand in candidates:
        if _digits(cand.title_norm) != _digits(title_norm):
            continue  # « Lot 3 » ≠ « Lot 4 », « 2025 » ≠ « 2026 »
        score = title_similarity(cand.title_norm, title_norm)
        if score >= settings.dedup_title_threshold:
            return cand, score
    return None


def _add_occurrence(
    session: Session, doc: Document, source: Source, url: str, item: RawItem, match: str, score: float | None, now: datetime
) -> bool:
    existing = session.scalar(
        select(Occurrence).where(Occurrence.source_id == source.id, Occurrence.url == url)
    )
    if existing:
        existing.last_seen_at = now
        return False
    session.add(
        Occurrence(
            document_id=doc.id,
            source_id=source.id,
            url=url,
            raw_title=item.title[:1000],
            published_at=item.published_at,
            discovered_at=now,
            last_seen_at=now,
            match_type=match,
            match_score=score,
        )
    )
    session.flush()
    return True


def ingest_item(session: Session, source: Source, item: RawItem, ctx: IngestContext) -> str:
    """Ingère un élément. Renvoie 'created', 'updated', 'duplicate' ou 'unchanged'."""
    now = ctx.now
    title = clean_text(item.title, 500)
    summary = clean_text(item.summary, 1200)
    if not title:
        return "unchanged"
    canon = canonicalize_url(item.url)
    digest = content_hash(title, summary)
    title_norm = normalize_for_compare(title)
    domain = domain_of(canon)

    # Niveau 1 : URL canonique identique (même document, éventuellement mis à jour)
    doc = session.scalar(select(Document).where(Document.canonical_url == canon))
    if doc:
        doc.last_checked_at = now
        new_occ = _add_occurrence(session, doc, source, canon, item, "url", 1.0, now)
        if doc.content_hash != digest:
            session.add(
                DocumentVersion(
                    document_id=doc.id, version=doc.version, title=doc.title,
                    summary=doc.summary, content_hash=doc.content_hash, recorded_at=now,
                )
            )
            doc.version += 1
            doc.title, doc.title_norm, doc.summary, doc.content_hash = title, title_norm, summary, digest
            doc.updated_at = now
            _qualify(session, doc, source, ctx)
            return "updated"
        _refresh_quality(session, doc, source, now)
        return "duplicate" if new_occ else "unchanged"

    # Niveau 2 : empreinte de contenu identique (reprise à l'identique sous une autre URL)
    doc = session.scalar(select(Document).where(Document.content_hash == digest).limit(1))
    match, score = "empreinte", 1.0
    # Niveau 3 : titre très similaire sur un autre domaine dans la fenêtre temporelle
    if doc is None:
        found = _find_similar(session, title_norm, domain, item.published_at or now)
        if found:
            doc, score = found
            match = "titre_similaire"
    if doc is not None:
        doc.last_checked_at = now
        new_occ = _add_occurrence(session, doc, source, canon, item, match, round(score, 3), now)
        _refresh_quality(session, doc, source, now)
        return "duplicate" if new_occ else "unchanged"

    # Nouveau document
    full_text = f"{title} {summary}"
    doc = Document(
        title=title,
        title_norm=title_norm,
        summary=summary or None,
        canonical_url=canon,
        domain=domain,
        author=clean_text(item.author, 300) or None,
        published_at=item.published_at,
        first_seen_at=now,
        last_checked_at=now,
        updated_at=now,
        language=detect_language(full_text, fallback=item.language or source.language),
        source_country=source.country,
        content_hash=digest,
        is_synthetic=source.is_synthetic,
        first_source_id=source.id,
    )
    session.add(doc)
    session.flush()
    _add_occurrence(session, doc, source, canon, item, "origine", None, now)
    _qualify(session, doc, source, ctx)
    return "created"


def _qualify(session: Session, doc: Document, source: Source, ctx: IngestContext) -> None:
    full_text = f"{doc.title} {doc.summary or ''}"
    categories, matches = categorize(full_text)
    doc.categories = categories
    doc.countries = detect_countries(full_text)
    doc.relevance = relevance_score(categories)
    doc.event_type = event_type(categories)
    if doc.status == "collecte" and source.source_type in get_settings().scoring["a_verifier_si_type"]:
        doc.status = "a_verifier"
    _refresh_quality(session, doc, source, ctx.now)
    doc.confidence_details = {**doc.confidence_details, "classification": matches}
    doc.processing_state = "qualifie"
    company_ids = link_entities(session, doc.id, full_text, ctx.entities)
    session.flush()
    ctx.alerts_created += evaluate_rules(session, doc, company_ids)


def ingest_items(session: Session, source: Source, items: list[RawItem], run: CollectionRun | None = None) -> dict[str, int]:
    ctx = IngestContext(entities=EntityDictionary.load(session))
    counts = {"created": 0, "updated": 0, "duplicate": 0, "unchanged": 0, "errors": 0}
    for item in items:
        for attempt in (1, 2):
            savepoint = session.begin_nested()
            try:
                outcome = ingest_item(session, source, item, ctx)
                savepoint.commit()
                counts[outcome] += 1
                break
            except IntegrityError:
                savepoint.rollback()  # course entre workers : on retente, le doublon sera détecté
                if attempt == 2:
                    counts["errors"] += 1
            except Exception:  # un élément défaillant ne bloque pas la collecte
                savepoint.rollback()
                log.exception("Échec d'ingestion d'un élément de la source %s", source.id)
                counts["errors"] += 1
                break
    counts["alerts"] = ctx.alerts_created
    if run is not None:
        run.items_fetched = len(items)
        run.docs_created = counts["created"]
        run.docs_updated = counts["updated"]
        run.duplicates = counts["duplicate"] + counts["unchanged"]
        run.errors = counts["errors"]
    return counts


def _schedule_after_failure(source: Source, permanent: bool, now: datetime) -> None:
    source.consecutive_failures += 1
    if permanent:
        delay = MAX_BACKOFF
    elif source.consecutive_failures >= CIRCUIT_THRESHOLD:
        delay = timedelta(hours=6)  # circuit ouvert
    else:
        delay = min(timedelta(minutes=source.interval_minutes) * (2 ** source.consecutive_failures), MAX_BACKOFF)
    source.next_run_at = now + delay


def run_source(session: Session, source_id: int) -> CollectionRun:
    """Exécute une collecte complète pour une source et journalise l'exécution."""
    source = session.get(Source, source_id)
    if source is None:
        raise ValueError(f"Source {source_id} introuvable")
    started = time.monotonic()
    now = datetime.now(timezone.utc)
    run = CollectionRun(source_id=source.id, started_at=now, status="en_cours")
    session.add(run)
    session.flush()
    source.last_run_at = now

    try:
        connector_cls = get_connector_class(source.connector_type)
        status = connector_cls.status()
        if not status.configured:
            raise FetchError(status.message, permanent=True)
        connector = connector_cls(source.url, source.config)
        result = connector.fetch(CollectState(etag=source.etag, last_modified=source.last_modified))
        run.not_modified = result.not_modified
        if not result.not_modified:
            ingest_items(session, source, result.items, run)
            source.etag = result.new_state.etag
            source.last_modified = result.new_state.last_modified
        run.status = "succes" if run.errors == 0 else "partiel"
        source.consecutive_failures = 0
        source.last_success_at = now
        source.last_error = None
        source.verification_status = "verifiee"
        source.verification_note = f"Collecte réussie par l'application le {now:%Y-%m-%d %H:%M} UTC"
        source.next_run_at = now + timedelta(minutes=source.interval_minutes)
    except FetchError as exc:
        run.status = "echec"
        run.error_kind = "permanente" if exc.permanent else "temporaire"
        run.error_message = str(exc)[:2000]
        source.last_error = f"[{run.error_kind}] {exc}"[:2000]
        if source.last_success_at is None:
            source.verification_status = "echec"
        _schedule_after_failure(source, exc.permanent, now)
        log.warning("Collecte échouée pour la source %s : %s", source.id, exc)
    except Exception as exc:  # erreur interne : visible, sans fuite de détails sensibles
        run.status = "echec"
        run.error_kind = "interne"
        run.error_message = f"Erreur interne : {type(exc).__name__}"
        source.last_error = run.error_message
        _schedule_after_failure(source, False, now)
        log.exception("Erreur interne pendant la collecte de la source %s", source.id)

    run.finished_at = datetime.now(timezone.utc)
    run.duration_ms = int((time.monotonic() - started) * 1000)
    session.flush()
    return run


def claim_due_sources(session: Session, limit: int) -> list[int]:
    """Réserve les sources à collecter (SKIP LOCKED : plusieurs workers sans double collecte)."""
    rows = session.execute(
        text(
            """
            SELECT id FROM sources
            WHERE enabled AND connector_type = ANY(:types)
              AND (next_run_at IS NULL OR next_run_at <= now())
            ORDER BY priority ASC, next_run_at NULLS FIRST
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
            """
        ),
        {"limit": limit, "types": ["rss"]},
    ).scalars().all()
    if rows:
        # Repousse provisoirement pour qu'aucun autre worker ne les reprenne pendant la collecte
        session.execute(
            text("UPDATE sources SET next_run_at = now() + interval '15 minutes' WHERE id = ANY(:ids)"),
            {"ids": list(rows)},
        )
    return list(rows)
