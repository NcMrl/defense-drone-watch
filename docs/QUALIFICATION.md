# Qualification : déduplication, classification, confiance

## Déduplication (ordre d'application)

| Niveau | Règle | Type d'occurrence |
|---|---|---|
| 1 | URL canonique identique : schéma et hôte en minuscules, port par défaut, fragment, slash final et paramètres de suivi (`utm_*`, `fbclid`, `gclid`, `xtor`…) retirés, paramètres triés | `url` |
| 1 bis | Même URL, contenu différent → **nouvelle version** (l'ancienne est archivée dans `document_versions`) | — |
| 2 | Empreinte SHA-256 du titre + résumé normalisés (minuscules, sans accents ni ponctuation) identique | `empreinte` |
| 3 | Titre très similaire (pg_trgm puis `SequenceMatcher` ≥ `DDW_DEDUP_TITLE_THRESHOLD`, 0,88 par défaut), **domaine différent**, mêmes nombres dans le titre, dans une fenêtre de ± `DDW_DEDUP_WINDOW_DAYS` jours | `titre_similaire` (avec score) |

Une fusion ajoute une occurrence ; elle ne supprime jamais rien. La fiche document montre la première détection et toutes les reprises.

Non couvert à ce stade : reprises sociales (phase 6), regroupement de documents différents décrivant un même événement (phase 4).

## Classification

Taxonomie bilingue FR/EN dans `services/normalize.py` (`TAXONOMY`, `COUNTRY_TERMS`). Pour chaque catégorie, les termes qui l'ont déclenchée sont stockés et affichés (« Pourquoi ces catégories »).

- **Pertinence** : 0,6 dès qu'une catégorie cœur (drones aériens, munitions rôdeuses, anti-drones) est présente, +0,1 par catégorie supplémentaire, plafonnée à 1.
- **Type d'événement** : première catégorie présente parmi contrats/programmes, essais, industrie, salons, réglementation.
- **Statut initial** : `a_verifier` si la source est de type secondaire, sociale ou non vérifiée ; sinon `collecte`. Les autres statuts (`corrobore`, `conteste`, `archive`) sont posés par un analyste (action journalisée).

## Score de confiance

Fichier `backend/app/scoring.json` (modifiable sans toucher au code). Chaque composante est dans [0, 1] et stockée séparément avec son explication.

| Composante | Calcul actuel | Poids |
|---|---|---|
| Fiabilité de la source | Valeur fixée sur la source, sinon valeur par défaut de son type (officielle 0,9 … non vérifiée 0,2) | 0,40 |
| Solidité de la preuve | **Non évaluée** (nécessite l'extraction d'affirmations, phase 4) — exclue du calcul et signalée | 0,25 |
| Corroboration | 0,25 + 0,25 par domaine distinct supplémentaire, plafonnée à 1 | 0,20 |
| Fraîcheur | Décroissance linéaire de 1 à 0 sur 2 × 15 jours | 0,15 |

Score = moyenne pondérée des composantes évaluées.

Garde-fous affichés avec chaque score : la popularité et les partages ne comptent pas ; plusieurs reprises d'un même communiqué ne sont pas une corroboration indépendante prouvée ; une source officielle atteste l'existence d'une annonce, pas les performances revendiquées.
