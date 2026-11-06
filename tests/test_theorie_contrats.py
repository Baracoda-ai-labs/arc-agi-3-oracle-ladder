# SPDX-License-Identifier: MIT-0
"""Correspondance théorie de C ⇄ contrats de la langue unique : aller-retour identique, refus listés, contrats existants chez B."""
import glob
import pickle

import pytest

from chrysalide.langue.ontologie_formelle import MECANISMES
from chrysalide.langue.theorie_contrats import TABLE, actifs, depuis_contrats, vers_contrats

DOSSIERS = sorted(glob.glob("experiments/T3.0/dossiers_g/*.pkl"))


def test_contrats_de_la_table_existent_chez_B():
    from chrysalide.langue.theorie_contrats import PROPOSES
    assert all(c[1] in MECANISMES or c[1] in PROPOSES for c in TABLE.values() if c[0] == "mecanisme")
    assert not set(PROPOSES) & set(MECANISMES)  # adopté par B → le retirer de PROPOSES


@pytest.mark.parametrize("f", DOSSIERS, ids=lambda f: f.split("/")[-1])
def test_aller_retour(f):
    with open(f, "rb") as h:
        th = pickle.load(h)["theorie"]  # dossiers de C, dans le dépôt
    t = vers_contrats(th)
    th2 = depuis_contrats(t)
    assert all(getattr(th2, c) == getattr(th, c) for c in actifs(th) if c in TABLE)
    assert set(t["non_exprimes"]) == {c for c in actifs(th) if c not in TABLE}


def test_cw410_sept_sur_sept_et_prolongation():
    """CW-410 : 7/7 avec les contrats de B seuls depuis l'adoption de `selection_marqueur` (CCM-293-B, 5/7 avant) ;
    glisse[4] → prolongation (CCM-300-C)."""
    import glob
    import pickle

    from chrysalide.langue.theorie_contrats import PROPOSES, actifs, depuis_contrats, vers_contrats
    fs = sorted(glob.glob("experiments/T3.0/dossiers_g/*.pkl"))
    if len(fs) != 7:
        pytest.skip("dossiers de C absents")
    ok_b = ok_p = 0
    for f in fs:
        with open(f, "rb") as h:
            T = pickle.load(h)["theorie"]
        b, p = vers_contrats(T, proposes=False), vers_contrats(T)
        ok_b += not b["non_exprimes"]
        ok_p += not p["non_exprimes"]
        r = depuis_contrats(p)
        assert all(getattr(r, k) == getattr(T, k) for k in actifs(T))
        assert {i["contrat"] for i in p["instances"] if i["champ"] in p["proposes"]} <= set(PROPOSES)
        if f.endswith("ka59_n4_creux.pkl"):
            assert [i["params"]["surface"] for i in p["instances"] if i["contrat"] == "prolongation"] == [frozenset({15})]
    assert (ok_b, ok_p) == (7, 7)
