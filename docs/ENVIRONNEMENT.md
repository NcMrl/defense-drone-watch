# Environnement de développement (session du 21/10/2026)

| Élément | Constat |
|---|---|
| Système | Linux, Python 3.13.16, Node 22.22.0 |
| PostgreSQL | 16, lancé localement (port 5433) ; extensions `unaccent` et `pg_trgm` disponibles ; `pgvector` **absent** |
| Docker | Client présent, **aucun démon** : `docker compose up` non exécutable ; syntaxe validée par `docker compose config` |
| Navigateur | Chromium headless (Playwright) pour les captures |
| Réseau sortant | **Uniquement registres de paquets** (PyPI, npm). Pas de DNS local, proxy obligatoire refusant les autres domaines |

## Conséquences

1. Les 8 sources du catalogue initial ont été importées et le worker les a réellement tentées : **toutes ont échoué** pour cause réseau (« Résolution DNS impossible », puis avec `DDW_TRUST_EGRESS_PROXY=true` : « Le proxy sortant a refusé la connexion »). Ces erreurs sont visibles dans l'interface, comme prévu.
2. La collecte de bout en bout a donc été validée contre un **serveur HTTP local** servant des flux RSS réels (format, ETag, 304, redirections, erreurs 404/503, robots.txt) dans les tests automatisés.
3. La validation sur sources réelles reste **à faire chez l'utilisateur** (voir README, « Première validation »).
4. Ce constat a conduit à ajouter l'option `DDW_TRUST_EGRESS_PROXY` pour les réseaux d'entreprise à proxy obligatoire.
