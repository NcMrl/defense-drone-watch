# Architecture

## Vue d'ensemble

```
             ┌────────────────────┐        ┌──────────────────────────────┐
 Navigateur ─┤ web (Next.js 16)   ├─HTTP──▶│ api (FastAPI)                │
             │ pages client, poll │        │  /api/* REST, OpenAPI /docs  │
             └────────────────────┘        │  auth jetons, rate limit     │
                                           └──────────────┬───────────────┘
                                                          │ SQLAlchemy
 Sources RSS ◀──HTTP (garde SSRF, robots)──┐   ┌──────────▼───────────────┐
                                           │   │ PostgreSQL 16            │
             ┌────────────────────┐        │   │  tsvector + unaccent     │
             │ worker (Python)    ├────────┘   │  pg_trgm (dédup titres)  │
             │ planif. SKIP LOCKED├───────────▶│  file de collecte        │
             └────────────────────┘            └──────────────────────────┘
```

Monolithe modulaire : un seul code Python (`backend/app`) exécuté sous deux processus (API et worker), un frontend séparé.

## Modules backend

| Module | Rôle |
|---|---|
| `connectors/base.py` | Contrat commun : `fetch(state) → FetchResult`, métadonnées (accès, limites, conditions, clés requises), statut de configuration |
| `connectors/rss.py` | Connecteur RSS/Atom (seul connecteur de collecte implémenté) |
| `connectors/social.py` | Interfaces X et LinkedIn déclarées, **non implémentées**, signalées comme telles |
| `services/net.py` | HTTP sortant : garde SSRF, redirections revalidées, robots.txt, taille max, erreurs temporaires/permanentes |
| `services/normalize.py` | Fonctions pures : URL canonique, nettoyage HTML, empreinte, langue, taxonomie, pays |
| `services/ingest.py` | Pipeline, déduplication, versionnage, journal d'exécution, backoff, réservation des sources dues |
| `services/scoring.py` | Score de confiance explicable (pondérations dans `scoring.json`) |
| `services/entities.py` | Détection d'entreprises/produits par dictionnaire |
| `services/alerts.py` | Évaluation des règles, anti-doublon |
| `services/search.py` | Recherche plein texte et filtres |
| `services/demo.py` | Données synthétiques |
| `api.py`, `security.py` | Routes REST, jetons, limitation de débit, en-têtes, audit |
| `worker.py`, `cli.py` | Planification et commandes d'exploitation |

## Décisions structurantes et écarts par rapport au cahier des charges

| Décision | Justification |
|---|---|
| **Pas de Redis au MVP** : la file de collecte est la table `sources` (`next_run_at` + `SELECT … FOR UPDATE SKIP LOCKED`) | Un seul composant à exploiter ; plusieurs workers possibles sans double collecte ; déduplication des tâches native. Redis sera ajouté si besoin de cache ou de limitation distribuée. |
| **Code synchrone + pool de threads** dans le worker | La collecte est limitée par le réseau, pas le CPU ; code plus simple et plus testable qu'un asyncio complet. Concurrence bornée par `DDW_WORKER_CONCURRENCY`. |
| **Pas de temps réel (SSE/WebSocket)** | L'interface interroge l'API toutes les 60 s et l'affiche explicitement (« actualisation périodique »). Le temps réel n'apporte rien tant que la collecte elle-même est périodique. |
| **Authentification par jetons** (lecture facultatif, administration obligatoire) au lieu de comptes utilisateurs | Suffisant pour un poste ou une petite équipe. Les comptes et rôles lecteur/analyste/administrateur sont prévus en phase 7. Sans `DDW_ADMIN_TOKEN`, toute écriture est refusée (503). |
| **Classification par taxonomie, pas par IA** | Déterministe, explicable (les termes déclencheurs sont conservés), sans coût ni clé. L'IA (phase 4) viendra en complément. |
| **Recherche `simple` + `unaccent`** plutôt que des configurations linguistiques FR/EN | Corpus multilingue : pas de racinisation, mais aucun mot perdu ; insensible aux accents. |
| **Fusion par titre restreinte à des domaines différents** | Sur un même domaine, deux titres voisins sont souvent deux articles distincts (séries, lots numérotés). |
| **Pages frontend en composants client** | L'API est la seule source de vérité ; même code en développement et en production ; pas de clé côté serveur Next. |

## Sécurité réseau des collecteurs

- Seuls `http`/`https` ; `localhost`, IP privées, de lien local, réservées et métadonnées cloud refusées ; chaque redirection est revalidée.
- `DDW_TRUST_EGRESS_PROXY=true` : pour les réseaux à proxy obligatoire **sans DNS local**, la résolution est déléguée au proxy (les IP privées littérales et `localhost` restent refusées). Ce cas a été rencontré dans l'environnement de développement.
- Limite connue : DNS rebinding entre la vérification et la connexion. Atténuation recommandée en production : proxy sortant filtrant.
- Le contenu collecté est nettoyé (HTML retiré) avant stockage ; l'interface n'injecte jamais de HTML et n'ouvre que des liens `http(s)` avec `rel="noopener noreferrer nofollow"`.

## Évolutions prévues (voir la matrice)

Phase 3 : catalogue vérifié, connecteurs sitemap/pages presse. Phase 4 : couche IA abstraite (résumés, traductions étiquetées, extraction d'affirmations, contradictions) avec sorties JSON validées et références obligatoires. Phase 5 : e-mail et messageries, regroupement d'alertes par événement. Phase 6 : X et LinkedIn selon droits réels. Phase 7 : comptes et rôles, sauvegardes automatisées, métriques Prometheus.
