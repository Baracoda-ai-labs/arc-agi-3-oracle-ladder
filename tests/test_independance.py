# SPDX-License-Identifier: MIT-0
"""CW-410 (B + G) : paires d'actions indépendantes déduites de l'ontologie v1, et leur sûreté mesurée."""
import json
import sys
from pathlib import Path

import pytest

from chrysalide.langue.independance import conditionnelle, independantes, paires_independantes

R = Path(__file__).resolve().parents[1]
MESURE = R / "experiments/meta_modele/independance.json"


def test_cas_d_ecole():
    assert not independantes(["deplacement"], ["deplacement"])              # même position écrite
    assert independantes(["etat_cyclique"], ["etat_cyclique"])              # suivant mod n : commute
    assert independantes(["etat_cyclique", "economie"], ["etat_cyclique", "economie"])  # coûts : somme
    assert not independantes(["deplacement"], ["selection_clic"])           # qui est contrôlé
    assert not independantes(["etat_cyclique"], ["etat_cyclique"], ["autonome"])  # l'autonome bouge sous le clic
    assert not independantes([], ["etat_cyclique"])                         # effets inconnus : prudence
    assert conditionnelle(["deplacement"], ["deplacement"]) is not None
    assert paires_independantes({"c1": ["etat_cyclique"], "c2": ["etat_cyclique"], "UP": ["deplacement"]}) == \
        [("c1", "c2")]


@pytest.mark.skipif(not MESURE.exists(), reason="mesure absente (independance_mesure.py)")
def test_aucune_paire_predite_independante_ne_casse_la_commutation():
    """Sûreté pour la réduction de G : sur les 20 programmes exacts, toute paire déclarée indépendante commute."""
    sys.path.insert(0, str(R / "experiments/meta_modele"))
    from independance_mesure import theorie_diagnostic
    lois = json.loads((R / "docs/memoire_globale.json").read_text())["lois"]
    d = json.loads(MESURE.read_text())["jeux"]
    faux = [(j, k) for j, v in d.items() for k, r in v["paires"].items()
            if independantes(*(theorie_diagnostic(j, lois)[0].get(c, []) for c in r["classes"]),
                             theorie_diagnostic(j, lois)[1]) and r["n"] and r["commute"] < r["n"]]
    assert not faux, faux
