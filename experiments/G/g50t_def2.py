"""[G] g50t N1 en déf. 2 (depuis les observations) avec C (CCM-196/198-C) : théorie INDUITE sur la 1re vie de Franzen
(drapeaux de C), exportée dans le langage, puis `macro_g.chercher` sur ce programme. Aucun programme exact n'est lu ;
le plan éventuel est rejoué dans le vrai jeu. Diagnostic : pastille 297 masquée (DIAG_MASQUER de C).
Usage : CHRYS_RETOUR=1 CHRYS_FANTOME=1 CHRYS_AMODAL=2 CHRYS_POURSUITE_UTILE=1 PYTHONPATH=. .venv/bin/python experiments/G/g50t_def2.py"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1"), str(RACINE / "experiments/G")]
import os

os.chdir(RACINE)
from divergences_traces import trajectoire

from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import induire
from chrysalide.arc3.logique.theorie import cells
from chrysalide.arc3.moteur import _codes_c, _sprite
from chrysalide.arc3.ontologie_exec import Scene


def theorie(gid="g50t", n=600, masquer=(297,)):
    k, grilles, lots = trajectoire(gid, n, str(RACINE / f"experiments/T3.10/diag_ref/traces/{gid}_ref/{gid}_trace.jsonl"))
    tr = Trajectoire([g.tolist() for g in grilles], _codes_c(lots))
    tr.exclues = frozenset(tr.exclues) | {(y, x) for e in tr.etats for o in e if o[0] in masquer for x, y in cells(o)}
    th = induire([(tr, None, None)], limite_s=60)[0]
    th.hors_jeu = tr.exclues
    prog, non = exporter(th, tr.taille)
    sc = Scene((tr.taille[1], tr.taille[0]), tr.fond, tr.fond, [_sprite(o) for o in tr.etats[0]])
    return k, tr, th, prog, non, sc


if __name__ == "__main__":
    from banc_p0 import _init
    _init()
    import macro_g
    k, tr, th, prog, non, sc = theorie()
    print(json.dumps({"niveau": k, "transitions": len(tr.etats) - 1, "echelle": [tr.s, tr.ox, tr.oy], "non_exportes": non,
                      "regles": len(prog.get("regles", []))}, default=str), flush=True)
    if not non:
        r = macro_g.chercher("g50t", k, 20000, 300, texte=prog, scene=sc, etat=prog.get("etat"))
        print(json.dumps(r, default=str), flush=True)
