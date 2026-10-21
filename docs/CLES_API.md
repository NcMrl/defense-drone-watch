# Clés et variables nécessaires

| Variable | Obligatoire | Usage | Où l'obtenir |
|---|---|---|---|
| `POSTGRES_PASSWORD` / `DDW_DATABASE_URL` | Oui | Base de données | À choisir |
| `DDW_ADMIN_TOKEN` | Oui pour toute écriture | Administration (sources, règles, statuts) | `python -c "import secrets;print(secrets.token_urlsafe(32))"` |
| `DDW_READ_TOKEN` | Non | Protéger aussi la lecture | Idem |
| `DDW_USER_AGENT` | Recommandé | S'identifier auprès des sites collectés (avec un contact réel) | — |
| `DDW_X_BEARER_TOKEN` | Phase 6 | Connecteur X (non implémenté) | Portail développeur X ; l'accès en lecture dépend de l'offre souscrite |
| `DDW_LINKEDIN_CLIENT_ID` / `_SECRET` | Phase 6 | Connecteur LinkedIn (non implémenté) | Application LinkedIn ; permissions soumises à validation par LinkedIn, lecture de contenus tiers généralement indisponible |
| Fournisseur IA (à définir) | Phase 4 | Résumés, traductions, extraction | — |

**Aucune clé externe n'est nécessaire pour la version actuelle** : la collecte RSS, la recherche, les alertes et le mode démonstration fonctionnent sans.
