# Ajouter un connecteur

## 1. Créer la classe

`backend/app/connectors/mon_connecteur.py` :

```python
from app.connectors.base import CollectState, Connector, FetchResult, RawItem
from app.services.net import FetchError, fetch


class MonConnecteur(Connector):
    type = "mon_type"                      # valeur de sources.connector_type
    label = "Nom affiché"
    access_method = "API officielle …"     # affiché dans l'administration
    limits = "Quotas, profondeur d'historique, absence d'exhaustivité…"
    terms = "Conditions d'utilisation applicables"
    default_interval_minutes = 60
    required_env = ("DDW_MON_API_KEY",)    # statut « non configuré » si absente

    def fetch(self, state: CollectState) -> FetchResult:
        resp = fetch(self.url)             # TOUJOURS passer par services.net.fetch
        if resp.status == 429:
            raise FetchError("Quota atteint", status=429)            # temporaire → backoff
        if resp.status in (401, 403):
            raise FetchError("Accès refusé", permanent=True)        # permanent → 24 h
        items = [RawItem(url=..., title=..., summary=..., published_at=...)]
        return FetchResult(items=items, new_state=CollectState(cursor=...))
```

Règles :
- Utiliser `services.net.fetch` (garde SSRF, robots.txt, taille max). Pour un client d'API spécifique, appeler `assert_public_url` avant chaque requête.
- Lever `FetchError(permanent=True)` pour ce qui ne se résoudra pas seul (auth, 404, format), `FetchError()` sinon.
- Ne renvoyer que ce que la source autorise à réutiliser (titre, extrait, lien).
- Ne jamais contourner une limitation d'accès ou un mécanisme anti-automatisation.

## 2. L'enregistrer

Dans `connectors/registry.py`, ajouter la classe au tuple. Puis, pour qu'elle soit planifiée par le worker, ajouter son type à la liste `types` de `claim_due_sources` (`services/ingest.py`).

## 3. La tester sans Internet

Utiliser la fixture `feed_server` de `tests/conftest.py`, qui sert des réponses HTTP locales :

```python
def test_mon_connecteur(db, feed_server, monkeypatch):
    monkeypatch.setenv("DDW_MON_API_KEY", "factice")
    feed_server.routes["/api"] = Route(b'{"items": [...]}', content_type="application/json")
    src = Source(name="Test", url=feed_server.url("/api"), connector_type="mon_type")
    db.add(src); db.commit()
    run = run_source(db, src.id)
    assert run.status == "succes"
```

Tester au minimum : collecte nominale, collecte incrémentale, erreur temporaire, erreur permanente, absence de clé.

## 4. Documenter

Ajouter la clé dans `.env.example` et `docs/CLES_API.md`, et une ligne dans `docs/MATRICE_FONCTIONNALITES.md`.
