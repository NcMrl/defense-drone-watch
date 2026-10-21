"""Score de confiance explicable. Chaque composante est conservée séparément avec son explication."""

from __future__ import annotations

from datetime import datetime, timezone

from app.config import get_settings


def source_reliability(source_type: str, explicit: float | None) -> float:
    if explicit is not None:
        return max(0.0, min(1.0, explicit))
    table = get_settings().scoring["source_type_reliability"]
    return float(table.get(source_type, table["non_verifiee"]))


def compute_confidence(
    *,
    source_type: str,
    source_reliability_value: float | None,
    distinct_domains: int,
    reference_date: datetime | None,
    now: datetime | None = None,
) -> tuple[float | None, dict]:
    cfg = get_settings().scoring
    now = now or datetime.now(timezone.utc)
    weights: dict[str, float] = cfg["weights"]

    reliability = source_reliability(source_type, source_reliability_value)

    corr_cfg = cfg["corroboration"]
    corroboration = min(
        corr_cfg["max"],
        corr_cfg["base_source_unique"] + corr_cfg["par_domaine_supplementaire"] * max(0, distinct_domains - 1),
    )

    freshness: float | None = None
    if reference_date is not None:
        age_days = max(0.0, (now - reference_date).total_seconds() / 86400)
        horizon = 2 * cfg["fraicheur"]["demi_vie_jours"]
        freshness = round(max(0.0, 1 - age_days / horizon), 3)

    components: dict[str, dict] = {
        "fiabilite_source": {
            "valeur": round(reliability, 3),
            "explication": f"Type de source « {source_type} »"
            + (" (valeur fixée manuellement)" if source_reliability_value is not None else " (valeur par défaut du type)"),
        },
        "solidite_preuve": {
            "valeur": None,
            "explication": "Non évaluée : nécessite l'extraction des affirmations (phase 4).",
        },
        "corroboration": {
            "valeur": round(corroboration, 3),
            "explication": f"{distinct_domains} domaine(s) distinct(s) ont publié ce contenu. "
            "Des reprises d'un même communiqué ne constituent pas une corroboration indépendante prouvée.",
        },
        "fraicheur": {
            "valeur": freshness,
            "explication": "Calculée sur la date de publication (ou de première détection)."
            if freshness is not None
            else "Date inconnue.",
        },
    }

    total_weight = 0.0
    weighted = 0.0
    for key, comp in components.items():
        if comp["valeur"] is None:
            continue
        w = float(weights.get(key, 0))
        total_weight += w
        weighted += w * comp["valeur"]
    score = round(weighted / total_weight, 3) if total_weight else None

    details = {
        "score": score,
        "composantes": components,
        "ponderations": weights,
        "non_evaluees": [k for k, c in components.items() if c["valeur"] is None],
        "avertissement": "La popularité et le nombre de partages ne sont pas pris en compte. "
        "Une source officielle atteste l'existence d'une annonce, pas les performances revendiquées.",
    }
    return score, details
