# API REST

Base : `http://localhost:8000`. Spécification complète : `docs/openapi.json` ou `/docs` (interface interactive).

Authentification : en-tête `Authorization: Bearer <jeton>`.
- **Lecture** : libre, sauf si `DDW_READ_TOKEN` est défini (jeton de lecture ou d'administration accepté).
- **Écriture** (marquée ✎) : `DDW_ADMIN_TOKEN` obligatoire ; si la variable n'est pas définie, les écritures renvoient 503.

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/api/health` | Santé de l'API et de la base |
| GET | `/api/stats?synthetic=include\|exclude\|only` | Indicateurs du tableau de bord, état des sources, répartitions |
| GET | `/api/documents` | Recherche paginée (filtres ci-dessous) |
| GET | `/api/documents/{id}` | Fiche : occurrences, versions, détail du score |
| PATCH ✎ | `/api/documents/{id}` | Changer le statut (`{"status": "corrobore"}`), journalisé |
| GET | `/api/export?format=csv\|json` | Export des résultats (mêmes filtres, 5 000 max), avec attribution |
| GET | `/api/sources` | Catalogue + santé + nombre de documents |
| POST ✎ | `/api/sources` | Ajouter une source |
| PATCH ✎ | `/api/sources/{id}` | Modifier (activer, fréquence, type…) |
| POST ✎ | `/api/sources/{id}/run` | Collecte immédiate (sert de test) |
| GET | `/api/sources/{id}/runs` · `/api/runs?failed_only=true` | Journal des collectes |
| GET | `/api/connectors` | Types de connecteurs, statut de configuration, limites, conditions |
| GET / POST ✎ / DELETE ✎ | `/api/rules`, `/api/rules/{id}` | Règles de veille |
| POST | `/api/rules/test` | Simuler une règle sur les 500 derniers documents (aucune alerte créée) |
| GET | `/api/alerts?unread_only=true` | Alertes |
| POST | `/api/alerts/{id}/read` | Marquer lue |
| GET | `/api/companies` | Référentiel entreprises |
| GET / POST ✎ | `/api/views` | Vues sauvegardées |

## Filtres de `/api/documents` et `/api/export`

`q` (syntaxe web : `"expression"`, `-exclu`, `or`), `source_id`, `language`, `country`, `category`, `status`, `event_type`, `company_id`, `product_id`, `min_confidence`, `min_relevance`, `published_from`, `published_to`, `collected_from`, `collected_to` (ISO 8601), `synthetic` (`include` par défaut, `exclude`, `only`), `sort` (`recent`, `publication`, `pertinence`), `page`, `page_size` (≤ 100).

Exemple :

```bash
curl "http://localhost:8000/api/documents?q=%22munitions%20r%C3%B4deuses%22%20-salon&country=FR&synthetic=exclude"
```
