from app.services.normalize import (
    canonicalize_url,
    categorize,
    clean_text,
    content_hash,
    detect_countries,
    detect_language,
    domain_of,
    relevance_score,
    title_similarity,
)


def test_canonical_url_removes_tracking_and_normalizes():
    a = canonicalize_url("HTTPS://WWW.Example.com:443/actu/article/?utm_source=x&b=2&a=1&fbclid=z#section")
    assert a == "https://www.example.com/actu/article?a=1&b=2"


def test_canonical_url_keeps_meaningful_params_and_root():
    assert canonicalize_url("http://example.com") == "http://example.com/"
    assert canonicalize_url("http://example.com:8080/p?id=3") == "http://example.com:8080/p?id=3"


def test_domain_strips_www():
    assert domain_of("https://www.defense.example/x") == "defense.example"


def test_clean_text_removes_scripts_and_markup():
    raw = '<p>Commande&nbsp;de <b>drones</b></p><script>alert("x")</script><style>p{}</style>'
    assert clean_text(raw) == "Commande de drones"


def test_clean_text_truncates_on_word_boundary():
    out = clean_text("un deux trois quatre cinq", max_len=12)
    assert out.endswith("…") and len(out) <= 12


def test_content_hash_ignores_case_accents_and_punctuation():
    assert content_hash("Défense : Drones", "Résumé.") == content_hash("defense drones", "resume")
    assert content_hash("a", "b") != content_hash("a", "c")


def test_title_similarity():
    assert title_similarity("Aérovigie notifiée d'une commande", "Aerovigie notifiee d une commande") == 1.0
    assert title_similarity("Essai de drone", "Ouverture d'une usine") < 0.6


def test_categorize_bilingual_and_explainable():
    cats, matches = categorize("Partnership on counter-UAS radar for unmanned aircraft")
    assert {"anti_drones", "capteurs", "drones_aeriens", "industrie_partenariats"} <= set(cats)
    assert "counter-uas" in matches["anti_drones"]
    cats_fr, _ = categorize("La DGA notifie un contrat de munitions rôdeuses")
    assert {"munitions_rodeuses", "contrats_programmes"} <= set(cats_fr)


def test_relevance_prefers_core_categories():
    assert relevance_score([]) == 0.0
    assert relevance_score(["drones_aeriens"]) >= 0.6
    assert relevance_score(["reglementation"]) < 0.6


def test_language_detection_with_fallback():
    assert detect_language("Le ministère des Armées annonce une commande pour les drones de la France") == "fr"
    assert detect_language("The army announced a contract for the new drones with the company") == "en"
    assert detect_language("Drone", fallback="de") == "de"


def test_country_detection():
    assert detect_countries("Essais en Ukraine avec la DGA et l'OTAN") == ["FR", "NATO", "UA"]
