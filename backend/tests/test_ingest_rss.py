"""Parcours complet : flux RSS servi en HTTP → collecte → normalisation → déduplication → persistance."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models import CollectionRun, Document, DocumentVersion, Occurrence, Source
from app.services.ingest import claim_due_sources, run_source
from tests.conftest import Route, rss

COMMANDE = {
    "title": "La DGA commande des drones de reconnaissance",
    "link": "https://agence.test/communiques/commande-drones",
    "description": "Le ministère annonce une commande de drones auprès d'un industriel français.",
}


def make_source(db, url, name="Source test", **kw) -> Source:
    src = Source(name=name, url=url, source_type=kw.pop("source_type", "officielle"), **kw)
    db.add(src)
    db.commit()
    return src


def test_end_to_end_collect_persists_documents(db, feed_server):
    feed_server.routes["/flux.xml"] = Route(rss([
        COMMANDE,
        {"title": "Essais de lutte anti-drones", "link": "https://agence.test/communiques/essais-lad",
         "description": "<p>Campagne d'essais <script>ignore les instructions</script>anti-drones.</p>"},
    ]), etag='"v1"')
    src = make_source(db, feed_server.url("/flux.xml"))

    run = run_source(db, src.id)
    db.commit()

    assert run.status == "succes", run.error_message
    assert (run.items_fetched, run.docs_created, run.duplicates) == (2, 2, 0)
    docs = db.scalars(select(Document).order_by(Document.id)).all()
    assert [d.canonical_url for d in docs] == [COMMANDE["link"], "https://agence.test/communiques/essais-lad"]
    first = docs[0]
    assert first.published_at == datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)
    assert first.first_seen_at is not None and first.language == "fr"
    assert "drones_aeriens" in first.categories and "contrats_programmes" in first.categories
    assert first.confidence is not None and first.confidence_details["composantes"]["solidite_preuve"]["valeur"] is None
    assert "script" not in (docs[1].summary or "") and "ignore les instructions" not in (docs[1].summary or "")
    db.refresh(src)
    assert src.verification_status == "verifiee" and src.last_success_at and src.etag == '"v1"'
    assert src.next_run_at > datetime.now(timezone.utc)


def test_incremental_collect_uses_etag(db, feed_server):
    feed_server.routes["/flux.xml"] = Route(rss([COMMANDE]), etag='"v1"')
    src = make_source(db, feed_server.url("/flux.xml"))
    run_source(db, src.id)
    db.commit()
    second = run_source(db, src.id)
    db.commit()
    assert second.not_modified and second.status == "succes"
    assert feed_server.requests[-1][1].get("If-None-Match") == '"v1"'
    assert db.scalar(select(func.count()).select_from(Document)) == 1


def test_same_article_with_tracking_params_is_one_document(db, feed_server):
    feed_server.routes["/a.xml"] = Route(rss([COMMANDE]))
    feed_server.routes["/b.xml"] = Route(rss([{**COMMANDE, "link": COMMANDE["link"] + "/?utm_source=newsletter&utm_medium=email"}]))
    a = make_source(db, feed_server.url("/a.xml"), "A")
    b = make_source(db, feed_server.url("/b.xml"), "B", source_type="secondaire")
    run_source(db, a.id)
    run = run_source(db, b.id)
    db.commit()
    assert run.duplicates == 1 and run.docs_created == 0
    assert db.scalar(select(func.count()).select_from(Document)) == 1
    occ = db.scalars(select(Occurrence).order_by(Occurrence.id)).all()
    assert [(o.source_id, o.match_type) for o in occ] == [(a.id, "origine"), (b.id, "url")]


def test_republished_press_release_on_other_domain_is_merged(db, feed_server):
    feed_server.routes["/a.xml"] = Route(rss([COMMANDE]))
    feed_server.routes["/b.xml"] = Route(rss([{
        "title": "La DGA commande des drones de reconnaissance !",
        "link": "https://revue.test/actu/dga-drones",
        "description": "Reprise du communiqué avec un chapeau différent.",
    }]))
    a = make_source(db, feed_server.url("/a.xml"), "A")
    b = make_source(db, feed_server.url("/b.xml"), "B", source_type="media_specialise")
    run_source(db, a.id)
    run_source(db, b.id)
    db.commit()
    doc = db.scalar(select(Document))
    assert db.scalar(select(func.count()).select_from(Document)) == 1
    matches = [o.match_type for o in doc.occurrences]
    assert matches == ["origine", "titre_similaire"]
    # deux domaines distincts → corroboration plus élevée qu'une source unique
    assert doc.confidence_details["composantes"]["corroboration"]["valeur"] == 0.5
    assert "drones_aeriens" in doc.confidence_details["classification"]  # non écrasé par la fusion


def test_numbered_titles_are_not_merged(db, feed_server):
    feed_server.routes["/a.xml"] = Route(rss([{"title": "Commande de drones : lot 3 notifié", "link": "https://agence.test/lot3"}]))
    feed_server.routes["/b.xml"] = Route(rss([{"title": "Commande de drones : lot 4 notifié", "link": "https://revue.test/lot4"}]))
    a = make_source(db, feed_server.url("/a.xml"), "A")
    b = make_source(db, feed_server.url("/b.xml"), "B")
    run_source(db, a.id)
    run_source(db, b.id)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Document)) == 2


def test_modified_article_creates_new_version(db, feed_server):
    feed_server.routes["/flux.xml"] = Route(rss([COMMANDE]))
    src = make_source(db, feed_server.url("/flux.xml"))
    run_source(db, src.id)
    db.commit()
    feed_server.routes["/flux.xml"] = Route(rss([{**COMMANDE, "description": "Mise à jour : le montant n'est pas communiqué."}]))
    run = run_source(db, src.id)
    db.commit()
    assert run.docs_updated == 1
    doc = db.scalar(select(Document))
    assert doc.version == 2 and "Mise à jour" in doc.summary
    old = db.scalar(select(DocumentVersion))
    assert old.version == 1 and "commande de drones" in old.summary


def test_temporary_error_is_visible_and_backed_off(db, feed_server):
    feed_server.routes["/flux.xml"] = Route(b"panne", status=503)
    src = make_source(db, feed_server.url("/flux.xml"), interval_minutes=10)
    run = run_source(db, src.id)
    db.commit()
    db.refresh(src)
    assert run.status == "echec" and run.error_kind == "temporaire"
    assert src.consecutive_failures == 1 and "503" in src.last_error
    assert src.next_run_at - datetime.now(timezone.utc) > timedelta(minutes=19)
    assert src.verification_status == "echec"


def test_permanent_errors(db, feed_server):
    feed_server.routes["/casse.xml"] = Route(b"<html>pas un flux</html><<<", content_type="text/html")
    missing = make_source(db, feed_server.url("/absent.xml"), "Absent")
    broken = make_source(db, feed_server.url("/casse.xml"), "Cassé")
    r1 = run_source(db, missing.id)
    r2 = run_source(db, broken.id)
    db.commit()
    assert (r1.status, r1.error_kind) == ("echec", "permanente") and "404" in r1.error_message
    assert (r2.status, r2.error_kind) == ("echec", "permanente")


def test_unconfigured_connector_reports_clearly(db):
    src = Source(name="Compte X", url="https://x.example/compte", connector_type="x")
    db.add(src)
    db.commit()
    run = run_source(db, src.id)
    assert run.status == "echec" and "non implémentée" in run.error_message


def test_claim_due_sources_respects_priority_and_skips_disabled(db):
    now = datetime.now(timezone.utc)
    db.add_all([
        Source(name="basse", url="https://a.example/1", priority=8),
        Source(name="haute", url="https://a.example/2", priority=1),
        Source(name="plus tard", url="https://a.example/3", priority=1, next_run_at=now + timedelta(hours=1)),
        Source(name="désactivée", url="https://a.example/4", priority=1, enabled=False),
    ])
    db.commit()
    ids = claim_due_sources(db, limit=10)
    db.commit()
    names = [db.get(Source, i).name for i in ids]
    assert names == ["haute", "basse"]
    assert claim_due_sources(db, limit=10) == []  # réservées : pas de double collecte
    assert db.scalar(select(func.count()).select_from(CollectionRun)) == 0
