# SPDX-License-Identifier: MIT-0
"""Ontologie formelle v1 (B, CW-373) : cohérence des trois étages, et NON-CONTRADICTION du protocole universel avec nos
programmes exacts rejoués sur les traces R0 (20 jeux publics, témoins exclus avant toute lecture)."""
import sys
from pathlib import Path

import pytest

from chrysalide.langue.ontologie_formelle import ECONOMIE, MECANISMES, OPTIONS_DOMAINE, PERCEPTION, PROTOCOLE
from chrysalide.langue.roles import roles_ontologie

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "experiments/meta_modele"))
TEM = {"vc33", "tu93", "wa30", "s5i5", "cn04"}


def test_trois_etages_coherents():
    roles = set(roles_ontologie())
    for nom, m in MECANISMES.items():
        assert set(m["roles"]) <= roles, f"{nom} : rôle hors ontologie"
        for cle in ("params", "pre", "effets", "phase", "ecrit", "contre_exemples", "test"):
            assert cle in m, f"{nom} : contrat incomplet ({cle})"
    assert set(PROTOCOLE["retire_de_l_universel"]) and all("defaut" in o for o in OPTIONS_DOMAINE.values())
    assert all({"regle", "test"} <= set(r) for r in PERCEPTION.values())
    assert {"glissement", "prolongation"} <= set(MECANISMES) and "traverse" in MECANISMES["glissement"]["params"]
    # CW-381/382 : économie explicite ; défaite = axiome, vies = option
    assert {"cout_action", "recharge", "defaite_epuisement", "ordre_victoire_epuisement", "perception_jauge"} <= set(ECONOMIE)
    assert "U5_defaite_terminale" in PROTOCOLE["contraintes"] and "vies" in OPTIONS_DOMAINE


def test_fusion_v1_coherente():
    """Fusion B + agent cloud + couche 6 : chaque type d'écart renvoie à des contrats EXISTANTS ; chaque nom de la boucle
    a sa correspondance ; chaque famille a une persona connue ; phases des contrats dans la table."""
    from chrysalide.langue.ontologie_formelle import FAMILLES, NOMS_BOUCLE, PERSONAS, PHASES, PROJECTION, TYPES_ECART
    connus = set(MECANISMES) | set(PROJECTION) | {"autonome"}
    for t, (_, hyp) in TYPES_ECART.items():
        assert set(hyp) <= connus, f"{t} renvoie à un contrat inconnu"
    assert all(p in PERSONAS for _, p in FAMILLES.values())
    assert all(m["phase"] in PHASES for m in MECANISMES.values())
    assert {"Glissement", "Piston", "Trou", "Jauge"} <= set(NOMS_BOUCLE)


def test_temps_et_reparations():
    """CW-389 : le temps au premier rang ; réparations causales typées (7 formes)."""
    from chrysalide.langue.ontologie_formelle import REPARATIONS, TEMPS
    assert {"prec(F)", "evenement(E,T)", "historique(K)"} <= set(TEMPS["fluents"])
    assert {"immediate", "differee", "persistante", "sequentielle"} <= set(TEMPS["formes_de_loi"])
    assert len(REPARATIONS) == 7


def test_rivales_nommees_et_departageables():
    """CW-400 : chaque explication rivale renvoie à des contrats existants et porte au moins un coup qui départage."""
    import re

    from chrysalide.langue.ontologie_formelle import RIVALES
    for r in RIVALES.values():
        assert r["statut"] == "non_departagees" and r["coups_qui_departagent"]
        for h in r["hypotheses"]:
            for nom in re.split(r"\s*\+\s*", h):
                assert re.sub(r"\(.*\)", "", nom).strip() in MECANISMES, nom


def test_transfert_ne_garde_aucune_valeur_de_scene():
    """CW-404 : positions, liaisons, but et paramètres de scène se recalculent ; un paramètre inconnu aussi."""
    from chrysalide.langue.ontologie_formelle import TRANSFERT, separer_pour_transfert
    th = {"mecanisme": "autonome_couloir", "effets": "avance", "positions": [(3, 4)], "liaisons": {"d1": "p1"},
          "but": "atteindre", "params": {"couloir": [(1, 1), (1, 2)], "depart": (1, 1), "declencheur_retour": "ACTION5",
                                         "periode": 2, "inconnu": 7}}
    s = separer_pour_transfert(th)
    assert s["garde"]["params"] == {"declencheur_retour": "ACTION5"} and s["reverifie"] == {"periode": 2}
    assert {"positions", "liaisons", "but", "couloir", "depart", "inconnu"} == set(s["recalcule"])
    assert not TRANSFERT["params_garde"] & TRANSFERT["params_reverifie"]


def test_fusion_v1_complete():
    """CW-406.1 : lit/écrit partout, contrats d'Astra 3/4 rattachés, familles identiques à la couche 6, fusion adoptée."""
    import ast
    import re

    from chrysalide.langue.ontologie_formelle import DECISIONS_FUSION, FAMILLES, NOMS_ASTRA
    assert all(m.get("lit") and m.get("ecrit") for m in MECANISMES.values())
    for cible in NOMS_ASTRA.values():
        nom = re.sub(r"\(.*\)", "", cible).strip()
        assert nom in MECANISMES or nom in {"PERCEPTION", "ECONOMIE"}, cible
    src = (R / "experiments/defi_llm/couche6/strategies/familles.py").read_text()
    c6 = next(n.value for n in ast.parse(src).body if isinstance(n, ast.Assign) and n.targets[0].id == "FAMILLES")
    assert {k.value for k in c6.keys} <= set(FAMILLES)
    assert all(v.startswith("ADOPTÉ") for v in DECISIONS_FUSION.values())


def _traces():
    vus = {}
    for f in sorted((R / "runs_pod/R0").glob("*/artifacts/*_events.jsonl")):
        if f.name[:4] not in TEM and f.name[:4] not in vus and (R / "experiments/T3.1/regles" / f"{f.name[:4]}.json").exists():
            vus[f.name[:4]] = f
    return vus


TRACES = _traces()


@pytest.mark.skipif(not TRACES, reason="traces R0 absentes (pod)")
@pytest.mark.parametrize("jeu", sorted(TRACES))
def test_programme_ne_contredit_pas_le_protocole(jeu):
    import non_contradiction as NC
    faits, _ = NC.faits_programme(TRACES[jeu], 40)
    regles = "\n".join(PROTOCOLE["contraintes"][k].replace(":-", "viol :-", 1) for k in ("U2_fin_exclusive", "U3_une_ancre"))
    import clingo
    c = clingo.Control(["--warn=none"])
    c.add("base", [], regles + "\n#show viol/0.\n" + "\n".join(faits))
    c.ground([("base", [])])
    viols = []
    c.solve(on_model=lambda m: viols.extend(str(s) for s in m.symbols(shown=True)))
    assert not viols, f"{jeu} : le programme exact contredit le protocole universel"


@pytest.mark.skipif(not TRACES, reason="traces R0 absentes (pod)")
@pytest.mark.parametrize("jeu", sorted(TRACES))
def test_controle_positif_viol_detecte(jeu):
    """Contrôle positif de l'adoption (CW-406.1) : un fait faux injecté (2e ancre d'un même objet) DOIT être vu."""
    import re

    import clingo
    import non_contradiction as NC
    faits, _ = NC.faits_programme(TRACES[jeu], 40)
    m = next(re.match(r"pos\((\w+),\s*(-?\d+),\s*(-?\d+),\s*(\d+)\)\.", f) for f in faits if f.startswith("pos("))
    faits = [*faits, f"pos({m[1]},{int(m[2]) + 1},{m[3]},{m[4]})."]
    regles = PROTOCOLE["contraintes"]["U3_une_ancre"].replace(":-", "viol :-", 1)
    c = clingo.Control(["--warn=none"])
    c.add("base", [], regles + "\n#show viol/0.\n" + "\n".join(faits))
    c.ground([("base", [])])
    viols = []
    c.solve(on_model=lambda mo: viols.extend(str(s) for s in mo.symbols(shown=True)))
    assert viols, f"{jeu} : la contrainte U3 ne voit pas une seconde ancre injectée"


def test_phases_coherentes_avec_les_effets():
    """CCM-078-G : chaque contrat porte une phase de PHASES, cohérente avec ce qu'il écrit."""
    from chrysalide.langue.ontologie_formelle import ECONOMIE, MECANISMES, PHASES, PROJECTION
    attendu = {"selection": {0}, "reserve": {5}, "issue": {6}, "pos": {1, 2, 3, 4}}
    for nom, c in {**MECANISMES, **ECONOMIE, **PROJECTION}.items():
        if c.get("phase") is None:
            continue
        assert c["phase"] in PHASES, f"{nom} : phase {c['phase']} hors de PHASES"
        if c["phase"] >= 9:
            assert not c.get("ecrit"), f"{nom} : un contrat de rendu n'écrit aucun fluent"
        for f in c.get("ecrit", []):
            assert c["phase"] in attendu.get(f, set(PHASES)), f"{nom} écrit {f} en phase {c['phase']}"
