# Modèle de données

Schéma PostgreSQL versionné par Alembic (`backend/migrations/versions/0001_schema_initial.py`). Tous les horodatages sont en `timestamptz` (UTC).

| Table | Rôle | Contraintes / index notables |
|---|---|---|
| `sources` | Catalogue : URL, type de connecteur, type de source, fiabilité, pays, langue, fréquence, priorité, état de collecte (ETag, dernière réussite, prochaine exécution, erreurs consécutives), statut de vérification, indicateur synthétique | `uq_sources_url`, `ix_sources_due (enabled, next_run_at)` |
| `collection_runs` | Journal de chaque exécution : statut, éléments, créés, mis à jour, doublons, erreur (type temporaire/permanente/interne), durée | `ix_runs_source_started` |
| `documents` | Document normalisé : titre, titre normalisé, résumé, URL canonique, domaine, auteur, dates (publication, première détection, dernière vérification, mise à jour), langue, pays source et cités, catégories, type d'événement, pertinence, confiance + détails, statut, version, empreinte, synthétique, `search_vector` généré | `uq_documents_canonical_url`, GIN plein texte, GIN trigramme sur `title_norm`, GIN sur catégories et pays |
| `occurrences` | Chaque apparition d'un document dans une source (jamais supprimée lors d'une fusion) : URL, titre brut, dates, type et score de correspondance | `uq_occurrence_source_url` |
| `document_versions` | Versions antérieures d'un document modifié | `uq_doc_version` |
| `companies`, `products` | Référentiel (noms, variantes, pays, fabricant, catégorie, statut annoncé). Champs inconnus = NULL | noms uniques |
| `document_entities` | Mentions détectées (entreprise ou produit) avec le texte reconnu et la méthode | `uq_doc_entity` |
| `watch_rules` | Règles de veille : mots-clés, exclusions, catégories, pays, entreprises, importance | — |
| `alerts` | Alerte = (règle, document) + raison | `uq_alert_rule_document` (anti-doublon) |
| `saved_views` | Filtres de recherche enregistrés | — |
| `audit_log` | Actions sensibles : acteur, action, cible, détails | `ix_audit_at` |

Fonction SQL `f_unaccent(text)` : enveloppe IMMUTABLE d'`unaccent`, nécessaire à la colonne générée `search_vector`.

## Tables prévues (phase 4 et suivantes)

`claims` (affirmations extraites), `corroborations` (lien affirmation ↔ document, nature : confirme / contredit), `ai_analyses` (fournisseur, modèle, prompt versionné, sortie, documents justificatifs), `users`, `user_preferences`, `events` (regroupement de documents décrivant un même événement).
