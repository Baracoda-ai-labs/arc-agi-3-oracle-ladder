"""[G] V1-B (CW-351.4) sur g50t N1, déf. 2 : la théorie GAGNANTE de C (`experiments/T3.0/g50t_def2/theorie_victoire.pkl`,
Franzen + 5 coups-expériences, but `centre`), exportée dans le langage ; depuis l'état après exploration, trois recherches
sur CE programme induit, même budget : meilleur d'abord guidé par V1-B (relations de C), meilleur d'abord non guidé
(h = 0 : largeur), `macro_g` (gel 2). Aucun programme exact lu ; plan non rejoué (c'est la mesure de la recherche).
Usage : CHRYS_RETOUR=1 CHRYS_FANTOME=1 CHRYS_AMODAL=2 CHRYS_POURSUITE_UTILE=1 CHRYS_TENUE=1 CHRYS_TRAITS_FINS=1 \
        CHRYS_BUT_CENTRE=1 PYTHONPATH=. .venv/bin/python experiments/G/v1b_g50t.py [but_index_ou_texte]"""
import json
import pickle
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/G"), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
from guidage import h_relations, meilleur_dabord  # noqa: E402

from chrysalide.arc3.logique.export_langage import exporter  # noqa: E402
from chrysalide.arc3.moteur import _sprite  # noqa: E402
from chrysalide.arc3.ontologie_exec import Scene  # noqa: E402
from chrysalide.arc3.sim_rapide import ProgrammeCompile  # noqa: E402


def main():
    d = pickle.loads((RACINE / "experiments/T3.0/g50t_def2/theorie_victoire.pkl").read_bytes())
    th = d["th2"]
    th.but = ("centre", 281, 9)
    prog, non = exporter(th, d["taille"])
    assert not non, non
    s = Scene((d["taille"][1], d["taille"][0]), d["fond"], d["fond"], [_sprite(o) for o in d["tr2_0"]])
    p = ProgrammeCompile(prog)
    for a in d["joues"]:
        p.step(s, (a, None, None))
    noms = [(a, None, None) for a in ("UP", "DOWN", "LEFT", "RIGHT", "SPACE")]
    h = h_relations(th)
    print(json.dumps({"h_depart": h(s), "tenue_cases": len(th.tenue_cases)}), flush=True)
    for nom, hh in (("V1-B", h), ("non guidé", lambda sc: 0)):
        plan, inf = meilleur_dabord(prog, s, p.etat, noms, hh, 200000, 300)
        print(json.dumps({"recherche": nom, "plan": None if plan is None else len(plan), **inf}), flush=True)
    from banc_p0 import _init
    _init()
    import macro_g
    r = macro_g.chercher("g50t", 1, 20000, 300, texte=prog, scene=s, etat=p.etat, actions=[1, 2, 3, 4, 5], verifier=False)
    print(json.dumps({"recherche": "macro_g", **{x: r.get(x) for x in ("arret", "plan", "etats_hauts", "cpu")}}), flush=True)


if __name__ == "__main__":
    main()
