# SPDX-License-Identifier: MIT-0
"""CW-365.3 (contrat d'équivalence, régression de CCM-035-G) : chaque but candidat des dossiers de G s'exporte en une
VRAIE condition, et la condition exportée dit la même chose que `Theorie._vrai` sur la scène de départ (où aucun but
n'est atteint, sinon le niveau serait fini). Un but exporté « faux » muet (re86 N5, `marques`) cassait toute recherche."""

import pickle
from pathlib import Path

import pytest

R = Path(__file__).resolve().parents[1] / "experiments/T3.0/dossiers_g"
DOSSIERS = sorted(R.glob("*.pkl")) if R.exists() else []


@pytest.mark.parametrize("chemin", DOSSIERS, ids=[p.stem for p in DOSSIERS])
def test_buts_exportes(chemin, monkeypatch):
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.export_langage import _condition_but
    from chrysalide.arc3.ontologie_exec import Scene
    d = pickle.loads(chemin.read_bytes())
    for k, v in d["drapeaux"].items():
        monkeypatch.setenv(k, v)
    w, h = d["taille"]
    sc = Scene((h, w), d["fond"], d["fond"], [s | {"visible": True} for s in d["sprites_depart"]])
    buts = list(d["buts"]) + ([d["theorie"].but_emboite] if getattr(d["theorie"], "but_emboite", None) else [])
    for but in buts:
        q = _condition_but(but)
        assert q is not None and q is not False, f"{chemin.stem} : but {but[0]} non traduit"
        dit = bool(Programme({"regles": []}).ev(q, {"_scene": sc, "_action": None, "_niveau": 0, "_debut": False}))
        assert not dit, f"{chemin.stem} : but {but[0]} déjà vrai au départ dans le programme"
