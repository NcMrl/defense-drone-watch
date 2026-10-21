"""Tests de l'API : recherche, filtres, sources, alertes, exports, sécurité, mode démo."""

import dataclasses

from sqlalchemy import func, select

from app import security
from app.config import get_settings
from app.db import session_scope
from app.models import Alert, AuditLog
from app.services.demo import seed_demo
from tests.conftest import ADMIN, Route, rss


def seed():
    with session_scope() as s:
        return seed_demo(s)


def titles(resp) -> list[str]:
    assert resp.status_code == 200, resp.text
    return [d["title"] for d in resp.json()["items"]]


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_demo_is_flagged_everywhere(client):
    assert seed()["status"] == "cree"
    assert seed()["status"] == "deja_present"  # idempotent
    page = client.get("/api/documents").json()
    assert page["total"] == 9
    assert all(d["is_synthetic"] and d["title"].startswith("[DÉMO]") for d in page["items"])
    assert client.get("/api/documents", params={"synthetic": "exclude"}).json()["total"] == 0
    assert all(s["is_synthetic"] for s in client.get("/api/sources").json())


def test_full_text_search_syntax(client):
    seed()
    assert any("Aérovigie" in t for t in titles(client.get("/api/documents", params={"q": "aerovigie"})))  # sans accent
    phrase = titles(client.get("/api/documents", params={"q": '"lutte anti-drones"'}))
    assert len(phrase) == 1 and "lutte anti-drones" in phrase[0]
    with_salon = titles(client.get("/api/documents", params={"q": "drones"}))
    without = titles(client.get("/api/documents", params={"q": "drones -salon"}))
    assert any("salon" in t for t in with_salon) and not any("salon" in t for t in without)
    ranked = client.get("/api/documents", params={"q": "NordLynx", "sort": "pertinence"}).json()
    assert ranked["total"] >= 1


def test_filters(client):
    seed()
    anti = titles(client.get("/api/documents", params={"category": "anti_drones"}))
    assert len(anti) == 2
    en = client.get("/api/documents", params={"language": "en"}).json()["items"]
    assert en and all(d["language"] == "en" for d in en)
    uk = titles(client.get("/api/documents", params={"country": "GB"}))
    assert any("NordLynx" in t for t in uk)
    assert client.get("/api/documents", params={"min_confidence": 0.99}).json()["total"] == 0
    companies = client.get("/api/companies").json()
    nordlynx = next(c for c in companies if c["name"].startswith("NordLynx"))
    by_company = titles(client.get("/api/documents", params={"company_id": nordlynx["id"]}))
    assert len(by_company) == nordlynx["document_count"] == 2
    assert client.get("/api/documents", params={"min_confidence": 2}).status_code == 422


def test_document_detail_shows_occurrences_and_confidence(client):
    seed()
    doc = client.get("/api/documents", params={"q": "FAUCON-D commande"}).json()["items"][0]
    detail = client.get(f"/api/documents/{doc['id']}").json()
    assert [o["match_type"] for o in detail["occurrences"]] == ["origine", "titre_similaire"]
    assert detail["occurrence_count"] == 2
    comps = detail["confidence_details"]["composantes"]
    assert set(comps) == {"fiabilite_source", "solidite_preuve", "corroboration", "fraicheur"}
    assert "solidite_preuve" in detail["confidence_details"]["non_evaluees"]
    assert client.get("/api/documents/999999").status_code == 404


def test_write_endpoints_require_admin_token(client):
    payload = {"name": "Flux test", "url": "https://flux.example/rss"}
    assert client.post("/api/sources", json=payload).status_code == 401
    assert client.post("/api/sources", json=payload, headers={"Authorization": "Bearer faux"}).status_code == 401
    created = client.post("/api/sources", json=payload, headers=ADMIN)
    assert created.status_code == 201 and created.json()["health"] == "jamais_collectee"
    assert client.post("/api/sources", json=payload, headers=ADMIN).status_code == 409
    assert client.post("/api/sources", json={"name": "x", "url": "pas-une-url"}, headers=ADMIN).status_code == 422
    patched = client.patch(f"/api/sources/{created.json()['id']}", json={"enabled": False}, headers=ADMIN)
    assert patched.json()["health"] == "desactivee"
    with session_scope() as s:
        actions = s.scalars(select(AuditLog.action)).all()
    assert actions == ["source.create", "source.update"]


def test_writes_disabled_without_admin_token(client, monkeypatch):
    settings = dataclasses.replace(get_settings(), admin_token=None)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    resp = client.post("/api/sources", json={"name": "Flux", "url": "https://f.example/rss"}, headers=ADMIN)
    assert resp.status_code == 503 and "DDW_ADMIN_TOKEN" in resp.json()["detail"]


def test_read_token_enforced_when_configured(client, monkeypatch):
    settings = dataclasses.replace(get_settings(), read_token="lecture")
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    assert client.get("/api/documents").status_code == 401
    assert client.get("/api/documents", headers={"Authorization": "Bearer lecture"}).status_code == 200


def test_connectors_report_configuration_status(client):
    connectors = {c["type"]: c for c in client.get("/api/connectors").json()}
    assert connectors["rss"]["configured"] and connectors["rss"]["implemented"]
    assert not connectors["x"]["configured"] and "non implémentée" in connectors["x"]["status_message"]
    assert "DDW_LINKEDIN_CLIENT_ID" in connectors["linkedin"]["required_env"]


def test_alert_rule_fires_once_end_to_end(client, feed_server):
    rule = client.post("/api/rules", json={"name": "Munitions", "keywords": ["munitions rôdeuses"], "severity": "critique"}, headers=ADMIN)
    assert rule.status_code == 201
    assert client.post("/api/rules", json={"name": "vide"}, headers=ADMIN).status_code == 422

    article = {"title": "Appel d'offres européen pour des munitions rodeuses", "link": "https://agence.test/ao-munitions"}
    feed_server.routes["/a.xml"] = Route(rss([article]))
    feed_server.routes["/b.xml"] = Route(rss([{**article, "link": article["link"] + "?utm_campaign=x"}]))
    a = client.post("/api/sources", json={"name": "Source A", "url": feed_server.url("/a.xml")}, headers=ADMIN).json()
    b = client.post("/api/sources", json={"name": "Source B", "url": feed_server.url("/b.xml")}, headers=ADMIN).json()
    assert client.post(f"/api/sources/{a['id']}/run", headers=ADMIN).json()["status"] == "succes"
    assert client.post(f"/api/sources/{b['id']}/run", headers=ADMIN).json()["duplicates"] == 1

    alerts = client.get("/api/alerts").json()
    assert len(alerts) == 1 and alerts[0]["severity"] == "critique" and "munitions" in alerts[0]["reason"]
    assert client.post(f"/api/alerts/{alerts[0]['id']}/read").status_code == 204
    assert client.get("/api/alerts", params={"unread_only": True}).json() == []
    with session_scope() as s:
        assert s.scalar(select(func.count()).select_from(Alert)) == 1


def test_rule_dry_run(client):
    seed()
    result = client.post("/api/rules/test", json={"name": "Essai", "categories": ["anti_drones"]}).json()
    assert result["correspondances"] == 2 and result["documents_evalues"] == 9


def test_source_errors_visible_in_stats_and_runs(client, feed_server):
    seed()
    feed_server.routes["/ko.xml"] = Route(b"", status=500)
    src = client.post("/api/sources", json={"name": "Source KO", "url": feed_server.url("/ko.xml")}, headers=ADMIN).json()
    run = client.post(f"/api/sources/{src['id']}/run", headers=ADMIN).json()
    assert run["status"] == "echec" and run["error_kind"] == "temporaire"
    stats = client.get("/api/stats").json()
    errors = {e["nom"]: e for e in stats["sources"]["en_erreur"]}
    assert "Source KO" in errors and not errors["Source KO"]["synthetique"]
    assert errors["[DÉMO] Source en erreur simulée"]["synthetique"]
    assert stats["totaux"]["documents"] == 9 and stats["totaux"]["taux_deduplication"] == 0.1
    assert stats["mode_actualisation"] == "periodique"
    assert client.get("/api/runs", params={"failed_only": True}).json()[0]["source_id"] == src["id"]
    health = {s["name"]: s["health"] for s in client.get("/api/sources").json()}
    assert health["Source KO"] == "degradee"


def test_synthetic_source_cannot_be_collected(client):
    seed()
    demo = client.get("/api/sources").json()[0]
    assert client.post(f"/api/sources/{demo['id']}/run", headers=ADMIN).status_code == 409


def test_exports_carry_attribution_and_synthetic_flag(client, feed_server):
    seed()
    csv_resp = client.get("/api/export", params={"format": "csv"})
    assert csv_resp.status_code == 200 and "attachment" in csv_resp.headers["content-disposition"]
    lines = csv_resp.text.splitlines()
    assert lines[0].startswith("# Généré le") and "fictives" in lines[0]
    assert lines[1].startswith("id,titre,url_source")
    assert all(line.endswith("OUI") for line in lines[2:])
    js = client.get("/api/export", params={"format": "json", "category": "anti_drones"}).json()
    assert len(js["documents"]) == 2 and js["meta"]["attribution"]


def test_csv_export_neutralizes_formula_injection(client, feed_server):
    feed_server.routes["/f.xml"] = Route(rss([{"title": "=HYPERLINK(\"http://x\") drone", "link": "https://agence.test/f"}]))
    src = client.post("/api/sources", json={"name": "Source F", "url": feed_server.url("/f.xml")}, headers=ADMIN).json()
    client.post(f"/api/sources/{src['id']}/run", headers=ADMIN)
    body = client.get("/api/export").text
    assert "'=HYPERLINK" in body


def test_document_status_change_is_audited(client):
    seed()
    doc_id = client.get("/api/documents").json()["items"][0]["id"]
    assert client.patch(f"/api/documents/{doc_id}", json={"status": "inconnu"}, headers=ADMIN).status_code == 422
    resp = client.patch(f"/api/documents/{doc_id}", json={"status": "corrobore"}, headers=ADMIN)
    assert resp.json()["status"] == "corrobore"
    with session_scope() as s:
        log = s.scalar(select(AuditLog).where(AuditLog.action == "document.status"))
    assert log.details == {"before": "collecte", "after": "corrobore"}


def test_saved_views_keep_only_known_filters(client):
    resp = client.post("/api/views", json={"name": "Anti-drones UE", "filters": {"category": "anti_drones", "hack": "x"}}, headers=ADMIN)
    assert resp.json()["filters"] == {"category": "anti_drones"}
    assert len(client.get("/api/views").json()) == 1


def test_security_headers_present(client):
    resp = client.get("/api/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
