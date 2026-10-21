# Matrice des fonctionnalités — v0.1 (21/10/2026)

Légende : ✅ implémenté et testé automatiquement · 🟢 implémenté, vérifié manuellement · 🟡 partiel · 🧪 simulé (démo/fixtures) · ⛔ bloqué (raison indiquée) · ⬜ non commencé (phase prévue)

## Collecte

| Fonctionnalité | État | Preuve / remarque |
|---|---|---|
| Connecteur RSS/Atom | ✅ | `test_end_to_end_collect_persists_documents` (serveur HTTP local) |
| Collecte incrémentale ETag / 304 | ✅ | `test_incremental_collect_uses_etag` — a révélé et corrigé un bogue (304 traité comme redirection) |
| Collecte sur sources réelles | ⛔ | Réseau du poste de développement restreint ; tentatives réelles journalisées en échec. **À valider chez l'utilisateur** |
| Catalogue de sources administrable (ajout, désactivation, test, classement) | ✅ | API + interface ; `test_write_endpoints_require_admin_token` |
| Catalogue initial | 🟡 | 8 flux candidats, **non vérifiés** ; sources institutionnelles FR/UE/OTAN à identifier |
| Garde SSRF, redirections revalidées, taille max | ✅ | `test_net.py` |
| robots.txt | ✅ | `test_robots_disallow_is_respected` |
| Réseau à proxy obligatoire | ✅ | `DDW_TRUST_EGRESS_PROXY`, 2 tests |
| Erreurs temporaires/permanentes, backoff, circuit ouvert | ✅ | `test_temporary_error_is_visible_and_backed_off`, `test_permanent_errors` |
| Planification, priorité, pas de double collecte | ✅ | `test_claim_due_sources…` ; worker exécuté (`--once`) en réel |
| Détection des suppressions | ⬜ | Phase 3 (non disponible dans les flux RSS) |
| Connecteurs sitemap / pages presse / API marchés publics | ⬜ | Phase 3 |
| X | 🟡 | Interface déclarée, signalée « non implémenté » ; phase 6 |
| LinkedIn | 🟡 | Idem ; l'API ne permet généralement pas de lire les contenus tiers |
| YouTube, brevets, publications scientifiques | ⬜ | Phase 7+ |

## Traitement

| Fonctionnalité | État | Preuve / remarque |
|---|---|---|
| Normalisation (URL, HTML, langue FR/EN, pays) | ✅ | `test_normalize.py` |
| Dédup. URL canonique | ✅ | `test_same_article_with_tracking_params_is_one_document` |
| Dédup. reprise sur autre domaine (titre similaire) | ✅ | `test_republished_press_release…`, `test_numbered_titles_are_not_merged` |
| Mise à jour versionnée | ✅ | `test_modified_article_creates_new_version` |
| Conservation de toutes les occurrences | ✅ | Tests ci-dessus + fiche document |
| Classification explicable | ✅ | Taxonomie bilingue, termes déclencheurs stockés |
| Détection d'entités | 🟡 | Par dictionnaire de noms déclarés ; pas d'extraction automatique de nouvelles entités |
| Score de confiance explicable et configurable | ✅ | `scoring.json` ; « solidité de la preuve » non évaluée et signalée |
| Statuts (collecté → archivé) | 🟡 | Statut initial automatique ; changement par analyste journalisé ; « en cours d'analyse » inutilisé avant l'IA |
| Contradictions, regroupement par événement | ⬜ | Phase 4 |
| IA (résumés, traduction étiquetée, extraction) | ⬜ | Phase 4 ; aucune IA n'est utilisée actuellement |
| Protection contre l'injection via contenu collecté | 🟡 | HTML nettoyé, contenu jamais interprété ; protections spécifiques aux prompts IA en phase 4 |

## Restitution

| Fonctionnalité | État | Preuve / remarque |
|---|---|---|
| Recherche plein texte (phrase, exclusion, sans accents) | ✅ | `test_full_text_search_syntax` |
| Filtres (15) | ✅ | `test_filters` (échantillon) ; tous exposés dans l'interface |
| Vues sauvegardées | ✅ | `test_saved_views_keep_only_known_filters` |
| Tableau de bord | 🟢 | Capture `docs/captures/01-tableau-de-bord.png` |
| Flux, fiche document, alertes, sources | 🟢 | Captures 02 à 05 ; parcours flux → fiche → source vérifié en navigateur headless |
| Fiches entreprises | 🟡 | Liste + documents liés ; fiche complète (contrats, chronologie, faits/annonces) phase 4 |
| Fiches produits/programmes | 🟡 | Table et détection présentes, pas de page dédiée |
| Frise chronologique | ⬜ | Phase 4 |
| Recherche sémantique | ⬜ | pgvector absent de l'environnement ; optionnel |
| Export CSV / JSON | ✅ | Attribution, horodatage, indicateur synthétique, neutralisation des formules |
| Export PDF | ⬜ | Phase 5 |
| Indicateurs de fraîcheur, actualisation périodique affichée | 🟢 | En-tête de l'interface |
| Alertes dans l'application, anti-doublon | ✅ | `test_alert_rule_fires_once_end_to_end` |
| Simulation de règle | ✅ | `test_rule_dry_run` |
| Alertes e-mail / messageries, regroupement par événement | ⬜ | Phase 5 |
| Interface multilingue | 🟡 | Français ; libellés centralisés dans `lib/i18n.ts` |

## Plateforme

| Fonctionnalité | État | Preuve / remarque |
|---|---|---|
| Migrations versionnées | ✅ | upgrade / downgrade / upgrade exécutés sur base vide |
| Jetons lecture / administration | ✅ | 3 tests |
| Comptes utilisateurs et rôles | ⬜ | Phase 7 |
| Limitation de débit, en-têtes de sécurité, erreurs sans fuite | ✅/🟢 | `test_security_headers_present` ; limitation non testée automatiquement |
| Journal d'audit | ✅ | `test_document_status_change_is_audited` |
| Mode démonstration signalé | ✅ | `test_demo_is_flagged_everywhere`, bandeau global, badges |
| Docker Compose | ⛔ | Syntaxe validée ; exécution impossible (pas de démon Docker dans l'environnement) |
| CI GitHub Actions | 🟡 | Fichier écrit, non exécuté |
| Sauvegarde / restauration | 🟡 | Procédure documentée, non testée |
| Métriques (latence, quotas) | 🟡 | Durées par collecte stockées ; pas d'export Prometheus |
