"""Architecture ARC-AGI-3 (CW-024) : mécanique des 4 pièces, sans modèle ni jeu (grilles fabriquées)."""
import copy

from chrysalide.arc3 import archi
from chrysalide.arc3.archi import MemoireReflexes, Moniteur, Routeur, Verificateur, diff


def grille(v=0):
    return [[v] * 64 for _ in range(64)]


def bouge(g, i, j, c=3):
    g = copy.deepcopy(g)
    g[i][j] = c
    return g


def test_diff_interieur_et_bordure():
    g0 = grille()
    assert diff(g0, bouge(g0, 10, 10)) == (1, 0)
    assert diff(g0, bouge(g0, 0, 5)) == (0, 1)


def test_moniteur_signatures_mortes_et_bloc():
    m, g = Moniteur(), grille()
    e = m.observer(g, {"a": "UP"}, g)
    assert e["sans_effet"] and m.deja_mort(g, {"a": "UP"}) and not m.deja_mort(g, {"a": "DOWN"})
    e = m.observer(g, {"a": "LEFT"}, bouge(g, 0, 1))
    assert e["barre"]  # seule la bordure change
    m.observer(g, {"a": "RIGHT"}, bouge(g, 20, 20), level_completed=True)
    b = m.bloc_etat()
    assert "niveau 1" in b and "signatures mortes 2" in b and "niveau réussi" in b  # bordure seule = sans effet sur le jeu


def test_interrupteurs_eteints_rien_ne_change(monkeypatch):
    """F-C2 : sans CHRYS_ROUTEUR, le routeur délibère toujours, même avec un réflexe applicable."""
    monkeypatch.delenv("CHRYS_ROUTEUR", raising=False)
    mem = MemoireReflexes()
    g = grille()
    mem.enregistrer(g, [{"action": {"a": "UP"}, "sans_effet": False}])
    assert Routeur(mem).decider(g) == ("deliberer", None)


def test_routeur_rejoue_sans_llm_puis_rend_la_main(monkeypatch, tmp_path):
    monkeypatch.setenv("CHRYS_ROUTEUR", "1")
    mem = MemoireReflexes(tmp_path / "r.json")
    g = grille()
    mem.enregistrer(g, [{"action": {"a": "UP"}, "sans_effet": False}, {"action": {"a": "LEFT"}, "sans_effet": False}],
                    fonctions={"f": "def f(): pass"}, provenance={"jeu": "ls20", "niveau": 1})
    assert MemoireReflexes(tmp_path / "r.json").reflexes  # persisté avec provenance
    r = Routeur(mem)
    assert r.decider(g) == ("reflexe", {"a": "UP"})
    assert r.decider(g) == ("reflexe", {"a": "LEFT"})
    assert r.decider(g) == ("deliberer", None) and r.n_sans_llm == 2
    assert Routeur(mem).decider(grille(5)) == ("deliberer", None)  # préconditions non remplies


def test_routeur_evite_une_signature_morte(monkeypatch):
    monkeypatch.setenv("CHRYS_ROUTEUR", "1")
    mem, mon, g = MemoireReflexes(), Moniteur(), grille()
    mem.enregistrer(g, [{"action": {"a": "UP"}, "sans_effet": False}])
    mon.observer(g, {"a": "UP"}, g)  # UP n'a rien fait ici
    assert Routeur(mem, mon).decider(g) == ("deliberer", None)


def test_verification_invalide_le_reflexe(monkeypatch):
    monkeypatch.setenv("CHRYS_ROUTEUR", "1")
    monkeypatch.setenv("CHRYS_VERIF", "1")
    mem, g = MemoireReflexes(), grille()
    rid = mem.enregistrer(g, [{"action": {"a": "UP"}, "sans_effet": False}, {"action": {"a": "UP"}, "sans_effet": False}])
    ro = Routeur(mem)
    v = Verificateur(mem, ro)
    assert ro.decider(g)[0] == "reflexe"
    assert v.verifier({"sans_effet": False, "game_over": False})  # conforme
    assert ro.decider(g)[0] == "reflexe"
    assert not v.verifier({"sans_effet": True, "game_over": False})  # écart : invalidé
    assert mem.reflexes[rid].statut == "perime" and mem.reflexes[rid].historique and v.n_invalides == 1
    assert ro.decider(g) == ("deliberer", None)  # plus jamais proposé
    assert archi.actif("VERIF")
