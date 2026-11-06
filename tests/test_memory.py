"""T0.7 : table invalidable (port du jalon 1) et notation des valeurs."""
from chrysalide.memory.facts import FactStore
from chrysalide.verify.valeur import contient

P = {"source_id": "s1"}


def store():
    s = FactStore()
    s.promote("PEA", "plafond_versements", "165 000 €", P, ["PEA", "plan d'épargne en actions"], ["plafond", "versements"])
    s.promote("PEA", "taux", "2 %", P, ["PEA"], ["taux"])
    s.promote("PEA", "plafond_annuel", "16 500 €", P, ["PEA"], ["annuel"], parents=[("PEA", "plafond_versements")])
    s.promote("PEA", "plafond_mensuel", "1 375 €", P, ["PEA"], ["mensuel"], parents=[("PEA", "plafond_annuel")])
    return s


def test_promote_archive_et_epoques():
    s = store()
    assert s.promote("PEA", "plafond_versements", "180 000 €", {"source_id": "s1-mod"}) == 2
    e = s.get("PEA", "plafond_versements")
    assert e["valeur"] == "180 000 €" and e["historique"][0]["valeur"] == "165 000 €"
    assert s.valeur_a("PEA", "plafond_versements", 1) == "165 000 €"
    assert s.valeur_a("PEA", "plafond_versements", 2) == "180 000 €"


def test_extraction_exacte_et_repli():
    s = store()
    assert s.extraire("Le plafond de versements sur un PEA est")["relation"] == "plafond_versements"
    assert s.extraire("Plan d'épargne en actions : plafond des versements ?")["relation"] == "plafond_versements"
    assert s.extraire("What is the current value for the PEA?") is None
    assert len(s.extraire_entite("What is the current value for the PEA?")) == 4
    assert s.extraire("Quelle est la capitale de la France ?") is None


def test_invalidation_en_cascade():
    s = store()
    touched = s.invalider("PEA", "plafond_versements")
    assert len(touched) == 3  # le fait + ses deux descendants (transitif)
    assert s.get("PEA", "plafond_versements") is None and s.get("PEA", "plafond_mensuel") is None
    assert s.data["entrees"][s.key("PEA", "plafond_mensuel")]["statut"] == "a_reverifier"
    assert s.get("PEA", "taux") is not None  # non dérivé : intact
    assert s.extraire("taux du PEA") is not None and s.extraire("plafond de versements du PEA") is None


def test_contient():
    assert contient("165 000 € (source decret-2026-309)", "165 000 €")
    assert contient("Le taux est de 20 %.", "20")
    assert not contient("de 1990 à 2000", "1")
    assert not contient("1 650 000 €", "165 000 €")
    assert contient("Francfort-sur-le-Main", "Francfort")
    assert not contient("Paris", "Berlin")
    assert contient("1,5 %", "1.5 %")
