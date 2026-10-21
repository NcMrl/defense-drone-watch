# Defense Drone Watch

Plateforme de veille technologique, industrielle et économique **en sources ouvertes** sur les drones, les munitions téléopérées et la lutte anti-drones dans le secteur de la défense.

> Version 0.1 — MVP (phase 2 du plan, une partie des phases 3 à 5). Ce qui fonctionne, ce qui est simulé et ce qui reste à faire est détaillé dans [`docs/MATRICE_FONCTIONNALITES.md`](docs/MATRICE_FONCTIONNALITES.md).

## Ce que fait la version actuelle

- **Collecte RSS/Atom réelle** : requêtes conditionnelles (ETag / Last-Modified), respect de robots.txt, garde SSRF, taille et délai bornés, backoff exponentiel et circuit ouvert par source.
- **Déduplication à 4 niveaux** : URL canonique (paramètres de suivi retirés), empreinte de contenu, titre très similaire sur un autre domaine (pg_trgm + contrôle des nombres), mise à jour versionnée d'un même article. Aucune occurrence n'est supprimée lors d'une fusion.
- **Qualification explicable** : catégories et pays par taxonomie bilingue (avec les termes déclencheurs), pertinence, score de confiance décomposé (fiabilité de la source, corroboration, fraîcheur ; solidité de la preuve explicitement « non évaluée »).
- **Recherche plein texte** PostgreSQL insensible aux accents (`"expression exacte"`, `-exclusion`, `or`) et 15 filtres, vues sauvegardées.
- **Alertes** par règles (mots-clés, exclusions, catégories, pays, entreprises), anti-doublon garanti par contrainte en base, simulation d'une règle avant création.
- **Interface française** : tableau de bord, flux, fiche document (sources associées, horodatage, explication du score), alertes, entreprises, administration des sources et journal des collectes.
- **Mode démonstration** : données fictives passées par le vrai pipeline, marquées partout (« DONNÉE SYNTHÉTIQUE », préfixe « [DÉMO] », domaine `.example`).
- **Exports** CSV et JSON avec attribution, horodatage et indicateur synthétique.

## Démarrage rapide (Docker)

```bash
cp .env.example .env
# Renseigner au minimum POSTGRES_PASSWORD et DDW_ADMIN_TOKEN, ainsi qu'un contact dans DDW_USER_AGENT
docker compose up --build -d
docker compose exec api python -m app.cli seed-demo        # facultatif : données fictives
docker compose exec api python -m app.cli import-catalog   # catalogue initial de sources réelles (non vérifiées)
```

- Interface : http://localhost:3000
- API et documentation interactive : http://localhost:8000/docs

Le worker collecte automatiquement les sources actives selon leur fréquence. Saisissez le jeton d'administration dans la page **Sources & collecte** pour ajouter, tester ou désactiver une source.

> ⚠️ `docker compose up` n'a **pas** pu être exécuté dans l'environnement de développement (pas de démon Docker). La syntaxe du fichier a été validée par `docker compose config`. Le démarrage manuel ci-dessous a, lui, été exécuté et vérifié.

## Démarrage manuel (sans Docker)

Prérequis : Python 3.12+, Node 22+, PostgreSQL 16 avec les extensions `unaccent` et `pg_trgm` (incluses dans le paquet contrib).

```bash
# Backend
cd backend
pip install -r requirements-dev.txt
export DDW_DATABASE_URL=postgresql+psycopg://ddw:motdepasse@localhost:5432/ddw
export DDW_ADMIN_TOKEN=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
alembic upgrade head
python -m app.cli seed-demo          # facultatif
python -m app.cli import-catalog
uvicorn app.main:app --port 8000     # API
python -m app.worker                 # collecte planifiée (autre terminal)

# Frontend
cd ../frontend
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build && npm start
```

## Tests

```bash
cd backend && DDW_TEST_DATABASE_URL=postgresql+psycopg://ddw@localhost:5432/ddw_test pytest -q   # 52 tests
cd frontend && npm test && npx tsc --noEmit && npm run build                                     # 5 tests + typage + build
```

Les tests n'utilisent ni clé API ni Internet : un serveur HTTP local sert les flux. Résultats détaillés : [`docs/TESTS.md`](docs/TESTS.md).

## Première validation sur sources réelles (à faire chez vous)

L'environnement de développement n'avait pas accès aux sites de défense : **aucune source réelle n'a encore été collectée avec succès**. Pour valider :

```bash
python -m app.cli list-sources
python -m app.cli run-source <ID>     # ou bouton « Collecter / tester » dans l'interface
```

Une source passe en `verifiee` à sa première collecte réussie ; une URL erronée apparaît en erreur avec son message. Corrigez ou désactivez les sources qui échouent, puis complétez le catalogue (voir la liste « à ajouter » dans `backend/app/data/catalogue_sources.json`).

## Commandes utiles

| Commande | Effet |
|---|---|
| `python -m app.cli seed-demo` / `purge-demo` | Charger / supprimer les données fictives |
| `python -m app.cli import-catalog` | Importer le catalogue initial |
| `python -m app.cli add-source URL "Nom" --type officielle --country FR` | Ajouter une source |
| `python -m app.cli run-source ID` | Collecte immédiate |
| `python -m app.worker --once` | Un passage du planificateur |

## Documentation

| Document | Contenu |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Composants, décisions structurantes, écarts justifiés par rapport au cahier des charges |
| [`docs/MODELE_DONNEES.md`](docs/MODELE_DONNEES.md) | Tables, contraintes, index |
| [`docs/QUALIFICATION.md`](docs/QUALIFICATION.md) | Déduplication, classification, score de confiance |
| [`docs/AJOUTER_UN_CONNECTEUR.md`](docs/AJOUTER_UN_CONNECTEUR.md) | Écrire et tester un nouveau connecteur |
| [`docs/API.md`](docs/API.md) + `docs/openapi.json` | Points d'accès de l'API |
| [`docs/CLES_API.md`](docs/CLES_API.md) | Clés et variables nécessaires |
| [`docs/EXPLOITATION.md`](docs/EXPLOITATION.md) | Sécurité, sauvegardes, conservation des données |
| [`docs/MATRICE_FONCTIONNALITES.md`](docs/MATRICE_FONCTIONNALITES.md) | Implémenté / testé / simulé / bloqué |
| [`docs/TESTS.md`](docs/TESTS.md) | Tests exécutés et résultats observés |
| [`docs/ENVIRONNEMENT.md`](docs/ENVIRONNEMENT.md) | Environnement de développement et contraintes constatées |
| [`docs/captures/`](docs/captures/) | Captures d'écran de l'interface (données de démonstration) |

## Périmètre et limites assumées

Veille sur des **acteurs industriels, produits, programmes et décisions publiques**, à partir de sources ouvertes. La plateforme ne fait pas de suivi opérationnel ou tactique, n'accède à aucune information classifiée ou privée, ne contourne aucune restriction d'accès et ne stocke pas le texte intégral des articles (titre, chapô du flux et lien uniquement).
