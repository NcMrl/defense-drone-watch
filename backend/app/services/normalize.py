"""Normalisation : URL canonique, nettoyage du texte, empreintes, langue, catégories.

Fonctions pures, sans accès réseau ni base de données, entièrement testables.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid",
    "ref", "ref_src", "cmpid", "xtor", "_hsenc", "_hsmi", "spm",
}
TRACKING_PREFIXES = ("utm_", "pk_", "mtm_")


def canonicalize_url(url: str) -> str:
    """Forme canonique d'une URL pour la déduplication de niveau 1.

    Minuscules pour schéma et hôte, port par défaut retiré, fragment retiré,
    paramètres de suivi retirés, paramètres restants triés, slash final retiré.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PREFIXES)
    ]
    query.sort()
    return urlunsplit((scheme, host, path, urlencode(query), ""))


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in {"script", "style", "noscript", "iframe"}:
            self._skip += 1
        elif tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "iframe"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def clean_text(value: str | None, max_len: int | None = None) -> str:
    """Retire le HTML (le contenu collecté n'est jamais affiché tel quel) et normalise les espaces."""
    if not value:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(value)
        parser.close()
        text = "".join(parser.parts)
    except Exception:  # HTML très malformé : repli prudent
        text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_len and len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text


def strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def normalize_for_compare(value: str) -> str:
    value = strip_accents(value.lower())
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def content_hash(title: str, summary: str) -> str:
    basis = normalize_for_compare(f"{title} {summary}")
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_for_compare(a), normalize_for_compare(b)).ratio()


_FR = {"le", "la", "les", "des", "du", "une", "et", "est", "pour", "dans", "sur", "avec", "par", "au", "aux", "qui", "que", "ministere", "armees"}
_EN = {"the", "and", "of", "to", "in", "for", "with", "on", "is", "by", "from", "that", "at", "as", "an", "its", "army", "defense", "defence"}


def detect_language(text: str, fallback: str | None = None) -> str | None:
    """Heuristique FR/EN par mots-outils. Renvoie `fallback` si le signal est trop faible."""
    words = normalize_for_compare(text).split()
    if len(words) < 4:
        return fallback
    fr = sum(w in _FR for w in words)
    en = sum(w in _EN for w in words)
    if max(fr, en) < 2 or fr == en:
        return fallback
    return "fr" if fr > en else "en"


# Taxonomie par mots-clés (FR/EN). Classification déterministe et explicable ;
# l'IA (phase 4) pourra l'affiner sans la remplacer.
TAXONOMY: dict[str, tuple[str, ...]] = {
    "drones_aeriens": ("drone", "drones", "uav", "uas", "rpas", "sans pilote", "unmanned aerial", "unmanned aircraft", "mini-drone", "male drone"),
    "munitions_rodeuses": ("munition rodeuse", "munitions rodeuses", "loitering munition", "loitering munitions", "munition teleoperee", "kamikaze drone", "one-way attack"),
    "anti_drones": ("anti-drone", "anti drone", "lutte anti-drones","counter-uas", "counter uas", "c-uas", "counter-drone", "drone interceptor", "intercepteur"),
    "navigation": ("navigation", "gnss", "gps", "inertiel", "inertial", "positionnement", "positioning"),
    "communications": ("liaison de donnees", "datalink", "data link", "communications", "satcom", "radio", "reseau maille", "mesh network"),
    "propulsion_energie": ("propulsion", "batterie", "battery", "batteries", "moteur", "engine", "hydrogene", "hydrogen", "pile a combustible", "fuel cell"),
    "capteurs": ("capteur", "capteurs", "sensor", "sensors", "radar", "optronique", "electro-optical", "infrarouge", "infrared", "lidar"),
    "autonomie_ia": ("autonomie", "autonomous", "autonomy", "intelligence artificielle", "artificial intelligence", "essaim", "swarm", "swarming"),
    "contrats_programmes": ("contrat", "contract", "commande", "order", "programme", "program", "acquisition", "procurement", "appel d offres", "tender", "marche public"),
    "industrie_partenariats": ("partenariat", "partnership", "rachat", "acquires", "acquisition de", "levee de fonds", "funding round", "investissement", "investment", "joint venture", "usine", "factory", "production"),
    "essais_demonstrations": ("essai", "essais", "test", "trial", "trials", "demonstration", "qualification", "campagne de tirs", "flight test"),
    "salons_evenements": ("salon", "eurosatory", "paris air show", "salon du bourget", "dsei", "idex", "ausa", "farnborough", "exposition", "conference"),
    "reglementation": ("reglementation", "regulation", "loi", "law", "directive", "export control", "controle des exportations", "certification", "norme", "standard"),
}

EVENT_TYPE_PRIORITY = (
    "contrats_programmes",
    "essais_demonstrations",
    "industrie_partenariats",
    "salons_evenements",
    "reglementation",
)

CORE_CATEGORIES = {"drones_aeriens", "munitions_rodeuses", "anti_drones"}


def categorize(text: str) -> tuple[list[str], dict[str, list[str]]]:
    """Renvoie les catégories détectées et, pour chacune, les termes qui l'ont déclenchée."""
    norm = f" {normalize_for_compare(text)} "
    matches: dict[str, list[str]] = {}
    for category, terms in TAXONOMY.items():
        hits = [t for t in terms if f" {normalize_for_compare(t)} " in norm]
        if hits:
            matches[category] = hits
    return sorted(matches), matches


def relevance_score(categories: list[str]) -> float:
    """Pertinence pour la veille : forte si une catégorie cœur (drones, munitions, anti-drones) est présente."""
    if not categories:
        return 0.0
    core = len(CORE_CATEGORIES.intersection(categories))
    other = len(categories) - core
    return round(min(1.0, (0.6 if core else 0.0) + 0.1 * core + 0.1 * other), 2)


def event_type(categories: list[str]) -> str | None:
    for candidate in EVENT_TYPE_PRIORITY:
        if candidate in categories:
            return candidate
    return None


COUNTRY_TERMS: dict[str, tuple[str, ...]] = {
    "FR": ("france", "francais", "francaise", "dga", "armee de terre", "armee de l air"),
    "GB": ("royaume uni", "united kingdom", "british", "uk mod", "britannique"),
    "US": ("etats unis", "united states", "u s army", "pentagon", "pentagone", "us army", "us air force", "diu"),
    "CA": ("canada", "canadian", "canadien"),
    "UA": ("ukraine", "ukrainian", "ukrainien", "ukrainienne"),
    "PL": ("pologne", "poland", "polish"),
    "IL": ("israel", "israeli", "israelien"),
    "TR": ("turquie", "turkey", "turkiye", "turkish", "turc"),
    "KR": ("coree du sud", "south korea", "korean", "coreen"),
    "JP": ("japon", "japan", "japanese", "japonais"),
    "IN": ("inde", "india", "indian", "indien"),
    "CN": ("chine", "china", "chinese", "chinois"),
    "DE": ("allemagne", "germany", "german", "bundeswehr"),
    "EU": ("union europeenne", "european union", "edf", "fonds europeen de la defense", "european defence fund"),
    "NATO": ("otan", "nato", "diana"),
}


def detect_countries(text: str) -> list[str]:
    norm = f" {normalize_for_compare(text)} "
    return sorted(
        code
        for code, terms in COUNTRY_TERMS.items()
        if any(f" {normalize_for_compare(t)} " in norm for t in terms)
    )
