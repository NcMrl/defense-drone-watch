# Tests exécutés — session du 21/10/2026

## Backend — `pytest -q` (PostgreSQL 16 local)

**Résultat observé : 52 passed in 13.69s**

| Fichier | Tests | Couverture |
|---|---|---|
| `test_normalize.py` | 11 | URL canonique, nettoyage HTML, empreinte, similarité, taxonomie, langue, pays |
| `test_net.py` | 13 | Schémas refusés, garde SSRF (127.0.0.1, localhost, 10.x, 169.254.169.254), robots.txt, redirections, taille max, mode proxy |
| `test_ingest_rss.py` | 10 | Bout en bout RSS via HTTP local, ETag/304, utm, reprise sur autre domaine, titres numérotés, versions, erreurs temporaires et permanentes, connecteur non configuré, planification |
| `test_api.py` | 18 | Démo signalée, syntaxe de recherche, filtres, fiche, authentification, connecteurs, alerte de bout en bout unique, simulation de règle, erreurs visibles, exports, injection de formules, audit, vues, en-têtes |

Anomalies révélées et corrigées pendant la session :
1. **Réponse 304 traitée comme une redirection** → collecte incrémentale cassée. Corrigé (`REDIRECT_CODES`).
2. **Explication des catégories perdue après une fusion de doublon**. Corrigé, assertion ajoutée.
3. Garde SSRF incompatible avec les réseaux sans DNS local → option `DDW_TRUST_EGRESS_PROXY`.

## Frontend

| Commande | Résultat observé |
|---|---|
| `npm test` (node:test) | 5 pass, 0 fail |
| `npx tsc --noEmit` | aucune erreur |
| `npm run build` (Next.js 16.4) | succès, 7 routes |

## Vérifications manuelles

| Vérification | Résultat |
|---|---|
| `alembic upgrade head` → `downgrade base` → `upgrade head` sur base vide | OK |
| `python -m app.cli seed-demo` | 10 éléments → 9 documents, 1 fusion par titre, 5 alertes |
| `python -m app.worker --once` sur le catalogue réel | 8 tentatives, 8 échecs réseau (environnement restreint), erreurs visibles dans l'interface |
| API + interface lancées, navigation headless (Chromium) | Tableau de bord, flux, fiche document (via clic depuis le flux), sources, alertes : rendus corrects ; captures dans `docs/captures/` ; seule erreur console : 404 sur une ressource absente (favicon) |
| `docker compose config` | syntaxe valide |

## Non testé

`docker compose up`, CI GitHub Actions, collecte sur sources réelles, limitation de débit, restauration de sauvegarde, tests de bout en bout automatisés de l'interface (Playwright scripté non intégré à la suite).
