"""Routes REST de l'API (préfixe /api). Documentation interactive : /docs (OpenAPI)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.connectors.registry import CONNECTORS, describe_connectors
from app.db import get_db
from app.models import (
    Alert,
    CollectionRun,
    Company,
    Document,
    DocumentEntity,
    DocumentVersion,
    Occurrence,
    Product,
    SavedView,
    Source,
    WatchRule,
)
from app.schemas import (
    AlertOut,
    CompanyOut,
    DocumentDetail,
    DocumentOut,
    DocumentPage,
    DocumentStatusUpdate,
    EntityRef,
    OccurrenceOut,
    RuleIn,
    RuleOut,
    RunOut,
    SourceCreate,
    SourceOut,
    SourceUpdate,
    ViewIn,
    ViewOut,
)
from app.security import audit, require_admin, require_read
from app.services.alerts import rule_matches
from app.services.ingest import run_source
from app.services.search import SearchFilters, search

router = APIRouter(prefix="/api")
SyntheticMode = Literal["include", "exclude", "only"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- santé

@router.get("/health", tags=["système"])
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "time": now_utc().isoformat()}


@router.get("/connectors", tags=["sources"], dependencies=[Depends(require_read)])
def connectors() -> list[dict]:
    return describe_connectors()


# ---------------------------------------------------------------- sources

def source_health(s: Source) -> str:
    if s.is_synthetic:
        return "synthetique"
    if not s.enabled:
        return "desactivee"
    if s.last_error and s.consecutive_failures >= 5:
        return "en_panne"
    if s.last_error and s.last_error.startswith("[permanente]"):
        return "en_panne"
    if s.consecutive_failures > 0:
        return "degradee"
    if s.last_success_at is None:
        return "jamais_collectee"
    return "ok"


def _source_out(s: Source, doc_count: int = 0) -> SourceOut:
    out = SourceOut.model_validate(s)
    out.health = source_health(s)
    out.document_count = doc_count
    return out


@router.get("/sources", response_model=list[SourceOut], tags=["sources"], dependencies=[Depends(require_read)])
def list_sources(db: Session = Depends(get_db)) -> list[SourceOut]:
    counts = dict(
        db.execute(
            select(Occurrence.source_id, func.count(func.distinct(Occurrence.document_id))).group_by(Occurrence.source_id)
        ).all()
    )
    sources = db.scalars(select(Source).order_by(Source.is_synthetic, Source.priority, Source.name)).all()
    return [_source_out(s, counts.get(s.id, 0)) for s in sources]


@router.post("/sources", response_model=SourceOut, status_code=201, tags=["sources"])
def create_source(payload: SourceCreate, db: Session = Depends(get_db), actor: str = Depends(require_admin)) -> SourceOut:
    if payload.connector_type not in CONNECTORS:
        raise HTTPException(422, f"Type de connecteur inconnu : {payload.connector_type}")
    data = payload.model_dump()
    data["url"] = str(payload.url)
    data["homepage"] = str(payload.homepage) if payload.homepage else None
    source = Source(**data)
    db.add(source)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Une source avec cette URL existe déjà") from exc
    audit(db, actor, "source.create", f"source:{source.id}", url=source.url)
    db.commit()
    return _source_out(source)


@router.patch("/sources/{source_id}", response_model=SourceOut, tags=["sources"])
def update_source(source_id: int, payload: SourceUpdate, db: Session = Depends(get_db), actor: str = Depends(require_admin)) -> SourceOut:
    source = db.get(Source, source_id) or _404("Source")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(source, key, value)
    if changes.get("enabled") is True:
        source.next_run_at = None  # collecte dès le prochain passage du worker
    audit(db, actor, "source.update", f"source:{source_id}", changes=changes)
    db.commit()
    return _source_out(source)


@router.post("/sources/{source_id}/run", response_model=RunOut, tags=["sources"])
def run_source_now(source_id: int, db: Session = Depends(get_db), actor: str = Depends(require_admin)) -> RunOut:
    """Lance immédiatement une collecte (sert aussi de test de la source)."""
    source = db.get(Source, source_id) or _404("Source")
    if source.is_synthetic:
        raise HTTPException(409, "Source synthétique : aucune collecte réelle possible")
    run = run_source(db, source_id)
    audit(db, actor, "source.run", f"source:{source_id}", status=run.status)
    db.commit()
    return RunOut.model_validate(run)


@router.get("/sources/{source_id}/runs", response_model=list[RunOut], tags=["sources"], dependencies=[Depends(require_read)])
def source_runs(source_id: int, limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)) -> list[RunOut]:
    runs = db.scalars(
        select(CollectionRun).where(CollectionRun.source_id == source_id).order_by(CollectionRun.started_at.desc()).limit(limit)
    ).all()
    return [RunOut.model_validate(r) for r in runs]


@router.get("/runs", response_model=list[RunOut], tags=["sources"], dependencies=[Depends(require_read)])
def recent_runs(limit: int = Query(50, ge=1, le=500), failed_only: bool = False, db: Session = Depends(get_db)) -> list[RunOut]:
    stmt = select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(limit)
    if failed_only:
        stmt = stmt.where(CollectionRun.status == "echec")
    return [RunOut.model_validate(r) for r in db.scalars(stmt)]


# ---------------------------------------------------------------- documents

def _filters(
    q: str | None = Query(None, max_length=500, description='Mots-clés ; "expression exacte" ; -exclusion ; or'),
    source_id: int | None = None,
    language: str | None = Query(None, max_length=8),
    country: str | None = Query(None, max_length=8),
    category: str | None = Query(None, max_length=50),
    status: str | None = Query(None, max_length=20),
    event_type: str | None = Query(None, max_length=50),
    company_id: int | None = None,
    product_id: int | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    min_relevance: float | None = Query(None, ge=0, le=1),
    published_from: datetime | None = None,
    published_to: datetime | None = None,
    collected_from: datetime | None = None,
    collected_to: datetime | None = None,
    synthetic: SyntheticMode = "include",
    sort: Literal["recent", "pertinence", "publication"] = "recent",
) -> SearchFilters:
    return SearchFilters(**{k: v for k, v in locals().items()})


def _serialize_docs(db: Session, docs: list[Document]) -> list[DocumentOut]:
    if not docs:
        return []
    ids = [d.id for d in docs]
    occ_counts = dict(
        db.execute(select(Occurrence.document_id, func.count()).where(Occurrence.document_id.in_(ids)).group_by(Occurrence.document_id)).all()
    )
    source_names = dict(db.execute(select(Source.id, Source.name)).all())
    ent_rows = db.execute(
        select(DocumentEntity.document_id, Company.id, Company.name, Company.is_synthetic, Product.id, Product.name, Product.is_synthetic)
        .outerjoin(Company, Company.id == DocumentEntity.company_id)
        .outerjoin(Product, Product.id == DocumentEntity.product_id)
        .where(DocumentEntity.document_id.in_(ids))
    ).all()
    entities: dict[int, list[EntityRef]] = {}
    for doc_id, cid, cname, csyn, pid, pname, psyn in ent_rows:
        if cid:
            entities.setdefault(doc_id, []).append(EntityRef(id=cid, name=cname, kind="entreprise", is_synthetic=csyn))
        if pid:
            entities.setdefault(doc_id, []).append(EntityRef(id=pid, name=pname, kind="produit", is_synthetic=psyn))
    out = []
    for d in docs:
        item = DocumentOut.model_validate(d)
        item.occurrence_count = occ_counts.get(d.id, 1)
        item.source_name = source_names.get(d.first_source_id)
        if d.published_at and d.first_seen_at >= d.published_at:
            item.collection_delay_minutes = round((d.first_seen_at - d.published_at).total_seconds() / 60, 1)
        item.entities = entities.get(d.id, [])
        out.append(item)
    return out


@router.get("/documents", response_model=DocumentPage, tags=["documents"], dependencies=[Depends(require_read)])
def list_documents(
    f: SearchFilters = Depends(_filters),
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> DocumentPage:
    total, docs = search(db, f, page, page_size)
    return DocumentPage(total=total, page=page, page_size=page_size, items=_serialize_docs(db, docs), generated_at=now_utc())


@router.get("/documents/{doc_id}", response_model=DocumentDetail, tags=["documents"], dependencies=[Depends(require_read)])
def get_document(doc_id: int, db: Session = Depends(get_db)) -> DocumentDetail:
    doc = db.get(Document, doc_id) or _404("Document")
    base = _serialize_docs(db, [doc])[0]
    occurrences = [
        OccurrenceOut(
            id=o.id, source_id=o.source_id, source_name=o.source.name, url=o.url, raw_title=o.raw_title,
            published_at=o.published_at, discovered_at=o.discovered_at, match_type=o.match_type, match_score=o.match_score,
        )
        for o in doc.occurrences
    ]
    versions = [
        {"version": v.version, "title": v.title, "summary": v.summary, "recorded_at": v.recorded_at}
        for v in db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc_id).order_by(DocumentVersion.version))
    ]
    return DocumentDetail(**base.model_dump(), confidence_details=doc.confidence_details or {}, occurrences=occurrences, versions=versions)


@router.patch("/documents/{doc_id}", response_model=DocumentOut, tags=["documents"])
def set_document_status(doc_id: int, payload: DocumentStatusUpdate, db: Session = Depends(get_db), actor: str = Depends(require_admin)) -> DocumentOut:
    doc = db.get(Document, doc_id) or _404("Document")
    previous = doc.status
    doc.status = payload.status
    audit(db, actor, "document.status", f"document:{doc_id}", before=previous, after=payload.status)
    db.commit()
    return _serialize_docs(db, [doc])[0]


EXPORT_COLUMNS = [
    "id", "titre", "url_source", "domaine", "source_premiere_detection", "publie_le", "collecte_le",
    "langue", "pays", "categories", "confiance", "statut", "nb_occurrences", "donnee_synthetique",
]


@router.get("/export", tags=["documents"], dependencies=[Depends(require_read)])
def export_documents(
    format: Literal["csv", "json"] = "csv",
    f: SearchFilters = Depends(_filters),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> Response:
    _, docs = search(db, f, 1, limit)
    rows = [
        {
            "id": d.id, "titre": d.title, "url_source": d.canonical_url, "domaine": d.domain,
            "source_premiere_detection": d.source_name, "publie_le": d.published_at.isoformat() if d.published_at else "",
            "collecte_le": d.first_seen_at.isoformat(), "langue": d.language or "", "pays": ";".join(d.countries),
            "categories": ";".join(d.categories), "confiance": d.confidence if d.confidence is not None else "",
            "statut": d.status, "nb_occurrences": d.occurrence_count, "donnee_synthetique": "OUI" if d.is_synthetic else "non",
        }
        for d in _serialize_docs(db, docs)
    ]
    stamp = now_utc()
    meta = {
        "genere_le": stamp.isoformat(),
        "outil": "Defense Drone Watch",
        "attribution": "Chaque ligne renvoie à sa publication d'origine (url_source). Contenus propriété de leurs auteurs.",
        "avertissement": "Les lignes marquées donnee_synthetique=OUI sont fictives (mode démonstration).",
    }
    filename = f"ddw-export-{stamp:%Y%m%d-%H%M%S}"
    if format == "json":
        body = json.dumps({"meta": meta, "documents": rows}, ensure_ascii=False, indent=2)
        return Response(body, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'})
    buf = io.StringIO()
    buf.write(f"# Généré le {meta['genere_le']} — {meta['attribution']} {meta['avertissement']}\n")
    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        # Neutralise l'injection de formules dans les tableurs
        writer.writerow({k: (f"'{v}" if isinstance(v, str) and v[:1] in "=+-@" else v) for k, v in row.items()})
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})


# ---------------------------------------------------------------- tableau de bord

@router.get("/stats", tags=["tableau de bord"], dependencies=[Depends(require_read)])
def stats(synthetic: SyntheticMode = "include", db: Session = Depends(get_db)) -> dict:
    now = now_utc()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    syn_clause = {"include": "TRUE", "exclude": "NOT is_synthetic", "only": "is_synthetic"}[synthetic]

    def scalar(sql: str, **params) -> int | float | None:
        return db.execute(text(sql.replace(":syn", syn_clause)), params).scalar()

    totals = {
        "documents": scalar("SELECT count(*) FROM documents WHERE :syn"),
        "nouveaux_24h": scalar("SELECT count(*) FROM documents WHERE :syn AND first_seen_at >= :t", t=now - timedelta(hours=24)),
        "pertinents_aujourdhui": scalar(
            "SELECT count(*) FROM documents WHERE :syn AND first_seen_at >= :t AND relevance >= 0.6", t=day_start
        ),
        "alertes_prioritaires_non_lues": scalar(
            "SELECT count(*) FROM alerts a JOIN documents d ON d.id = a.document_id "
            "WHERE a.read_at IS NULL AND a.severity IN ('important','critique') AND " + syn_clause.replace("is_synthetic", "d.is_synthetic")
        ),
        "occurrences": scalar("SELECT count(*) FROM occurrences o JOIN documents d ON d.id = o.document_id WHERE "
                              + syn_clause.replace("is_synthetic", "d.is_synthetic")),
    }
    occ, docs = totals["occurrences"] or 0, totals["documents"] or 0
    totals["taux_deduplication"] = round((occ - docs) / occ, 3) if occ else None

    sources = db.scalars(select(Source)).all()
    real = [s for s in sources if not s.is_synthetic]
    health_counts: dict[str, int] = {}
    for s in sources:
        h = source_health(s)
        health_counts[h] = health_counts.get(h, 0) + 1
    last_success = max((s.last_success_at for s in real if s.last_success_at), default=None)

    def grouped(sql: str) -> list[dict]:
        return [{"cle": k, "n": n} for k, n in db.execute(text(sql.replace(":syn", syn_clause))).all()]

    return {
        "genere_le": now.isoformat(),
        "mode_actualisation": "periodique",
        "totaux": totals,
        "sources": {
            "par_etat": health_counts,
            "reelles_actives": sum(1 for s in real if s.enabled),
            "derniere_collecte_reussie": last_success.isoformat() if last_success else None,
            "en_erreur": [
                {"id": s.id, "nom": s.name, "erreur": s.last_error, "echecs_consecutifs": s.consecutive_failures,
                 "synthetique": s.is_synthetic}
                for s in sources if s.last_error
            ],
        },
        "par_categorie": grouped("SELECT c, count(*) FROM documents, unnest(categories) c WHERE :syn GROUP BY c ORDER BY 2 DESC"),
        "par_pays": grouped("SELECT c, count(*) FROM documents, unnest(countries) c WHERE :syn GROUP BY c ORDER BY 2 DESC"),
        "par_jour": grouped(
            "SELECT to_char(date_trunc('day', first_seen_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD'), count(*) FROM documents "
            "WHERE :syn AND first_seen_at >= now() - interval '30 days' GROUP BY 1 ORDER BY 1"
        ),
        "par_jour_publication": grouped(
            "SELECT to_char(date_trunc('day', published_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD'), count(*) FROM documents "
            "WHERE :syn AND published_at >= now() - interval '30 days' GROUP BY 1 ORDER BY 1"
        ),
        "entreprises_plus_citees": grouped(
            "SELECT c.name, count(DISTINCT e.document_id) FROM document_entities e JOIN companies c ON c.id = e.company_id "
            "JOIN documents d ON d.id = e.document_id WHERE " + syn_clause.replace("is_synthetic", "d.is_synthetic")
            + " GROUP BY c.name ORDER BY 2 DESC LIMIT 10"
        ),
    }


# ---------------------------------------------------------------- règles et alertes

@router.get("/rules", response_model=list[RuleOut], tags=["alertes"], dependencies=[Depends(require_read)])
def list_rules(db: Session = Depends(get_db)) -> list[RuleOut]:
    return [RuleOut.model_validate(r) for r in db.scalars(select(WatchRule).order_by(WatchRule.id))]


@router.post("/rules", response_model=RuleOut, status_code=201, tags=["alertes"])
def create_rule(payload: RuleIn, db: Session = Depends(get_db), actor: str = Depends(require_admin)) -> RuleOut:
    if not any([payload.keywords, payload.categories, payload.countries, payload.company_ids]):
        raise HTTPException(422, "Une règle doit comporter au moins un critère (mots-clés, catégories, pays ou entreprises).")
    rule = WatchRule(**payload.model_dump())
    db.add(rule)
    db.flush()
    audit(db, actor, "rule.create", f"rule:{rule.id}")
    db.commit()
    return RuleOut.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=204, tags=["alertes"])
def delete_rule(rule_id: int, db: Session = Depends(get_db), actor: str = Depends(require_admin)) -> Response:
    rule = db.get(WatchRule, rule_id) or _404("Règle")
    db.delete(rule)
    audit(db, actor, "rule.delete", f"rule:{rule_id}")
    db.commit()
    return Response(status_code=204)


@router.post("/rules/test", tags=["alertes"], dependencies=[Depends(require_read)])
def test_rule(payload: RuleIn, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)) -> dict:
    """Simule une règle sur les 500 documents les plus récents, sans créer d'alerte."""
    rule = WatchRule(**payload.model_dump())
    docs = db.scalars(select(Document).order_by(Document.first_seen_at.desc()).limit(500)).all()
    company_map: dict[int, list[int]] = {}
    for doc_id, cid in db.execute(
        select(DocumentEntity.document_id, DocumentEntity.company_id).where(DocumentEntity.company_id.is_not(None))
    ):
        company_map.setdefault(doc_id, []).append(cid)
    matches = []
    for d in docs:
        reason = rule_matches(rule, d, company_map.get(d.id, []))
        if reason:
            matches.append({"document_id": d.id, "titre": d.title, "raison": reason, "synthetique": d.is_synthetic})
    return {"documents_evalues": len(docs), "correspondances": len(matches), "exemples": matches[:limit]}


@router.get("/alerts", response_model=list[AlertOut], tags=["alertes"], dependencies=[Depends(require_read)])
def list_alerts(unread_only: bool = False, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)) -> list[AlertOut]:
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if unread_only:
        stmt = stmt.where(Alert.read_at.is_(None))
    return [
        AlertOut(
            id=a.id, rule_id=a.rule_id, rule_name=a.rule.name, document_id=a.document_id, document_title=a.document.title,
            document_is_synthetic=a.document.is_synthetic, severity=a.severity, reason=a.reason,
            created_at=a.created_at, read_at=a.read_at,
        )
        for a in db.scalars(stmt)
    ]


@router.post("/alerts/{alert_id}/read", status_code=204, tags=["alertes"], dependencies=[Depends(require_read)])
def mark_alert_read(alert_id: int, db: Session = Depends(get_db)) -> Response:
    alert = db.get(Alert, alert_id) or _404("Alerte")
    alert.read_at = alert.read_at or now_utc()
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- entreprises, vues

@router.get("/companies", response_model=list[CompanyOut], tags=["référentiel"], dependencies=[Depends(require_read)])
def list_companies(db: Session = Depends(get_db)) -> list[CompanyOut]:
    counts = dict(db.execute(
        select(DocumentEntity.company_id, func.count(func.distinct(DocumentEntity.document_id))).group_by(DocumentEntity.company_id)
    ).all())
    out = []
    for c in db.scalars(select(Company).order_by(Company.name)):
        item = CompanyOut.model_validate(c)
        item.document_count = counts.get(c.id, 0)
        out.append(item)
    return out


@router.get("/views", response_model=list[ViewOut], tags=["recherche"], dependencies=[Depends(require_read)])
def list_views(db: Session = Depends(get_db)) -> list[ViewOut]:
    return [ViewOut.model_validate(v) for v in db.scalars(select(SavedView).order_by(SavedView.name))]


@router.post("/views", response_model=ViewOut, status_code=201, tags=["recherche"])
def create_view(payload: ViewIn, db: Session = Depends(get_db), actor: str = Depends(require_admin)) -> ViewOut:
    allowed = set(SearchFilters.__dataclass_fields__)
    filters = {k: v for k, v in payload.filters.items() if k in allowed}
    view = SavedView(name=payload.name, filters=filters)
    db.add(view)
    db.flush()
    audit(db, actor, "view.create", f"view:{view.id}")
    db.commit()
    return ViewOut.model_validate(view)


def _404(what: str):  # noqa: ANN202
    raise HTTPException(404, f"{what} introuvable")
