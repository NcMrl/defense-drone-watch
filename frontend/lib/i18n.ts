// Libellés de l'interface. Ajouter une langue = ajouter un dictionnaire de même forme.

const fr = {
  categories: {
    drones_aeriens: "Drones aériens",
    munitions_rodeuses: "Munitions rôdeuses",
    anti_drones: "Lutte anti-drones",
    navigation: "Navigation",
    communications: "Communications",
    propulsion_energie: "Propulsion & énergie",
    capteurs: "Capteurs",
    autonomie_ia: "Autonomie & IA",
    contrats_programmes: "Contrats & programmes",
    industrie_partenariats: "Industrie & partenariats",
    essais_demonstrations: "Essais & démonstrations",
    salons_evenements: "Salons & événements",
    reglementation: "Réglementation",
  } as Record<string, string>,
  statuses: {
    collecte: "Collecté",
    en_analyse: "En cours d'analyse",
    a_verifier: "À vérifier",
    corrobore: "Corroboré",
    conteste: "Contesté",
    archive: "Archivé",
  } as Record<string, string>,
  health: {
    ok: "Opérationnelle",
    degradee: "Dégradée",
    en_panne: "En panne",
    jamais_collectee: "Jamais collectée",
    desactivee: "Désactivée",
    synthetique: "Synthétique",
    inconnu: "Inconnu",
  } as Record<string, string>,
  sourceTypes: {
    officielle: "Source primaire officielle",
    industrielle: "Source industrielle directe",
    media_specialise: "Média spécialisé",
    scientifique: "Publication scientifique",
    secondaire: "Source secondaire",
    sociale: "Publication sociale attribuable",
    non_verifiee: "Source non vérifiée",
  } as Record<string, string>,
  matchTypes: {
    origine: "Première détection",
    url: "Même URL",
    empreinte: "Contenu identique",
    titre_similaire: "Titre très similaire",
  } as Record<string, string>,
  confidence: {
    inconnu: "Confiance non évaluée",
    faible: "Confiance faible",
    moyen: "Confiance moyenne",
    eleve: "Confiance élevée",
  } as Record<string, string>,
  severities: { info: "Info", important: "Important", critique: "Critique" } as Record<string, string>,
  countries: {
    FR: "France", GB: "Royaume-Uni", US: "États-Unis", CA: "Canada", UA: "Ukraine", PL: "Pologne",
    IL: "Israël", TR: "Turquie", KR: "Corée du Sud", JP: "Japon", IN: "Inde", CN: "Chine",
    DE: "Allemagne", EU: "Union européenne", NATO: "OTAN",
  } as Record<string, string>,
};

export type Dictionary = typeof fr;
const dictionaries: Record<string, Dictionary> = { fr };

export function dict(lang = "fr"): Dictionary {
  return dictionaries[lang] ?? fr;
}

export function label(group: keyof Dictionary, key: string | null | undefined, lang = "fr"): string {
  if (!key) return "—";
  return dict(lang)[group][key] ?? key;
}
