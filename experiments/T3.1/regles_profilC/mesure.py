# SPDX-License-Identifier: MIT-0
"""CW-112 (test « style ou expressivité », CCM-016-C) : banc honnête de mesure_exhaustivite.py sur un JSON candidat d'un
autre dossier (défaut : ce dossier), SANS écrire exhaustivite.json ni regles/. Ajoute le classement profil C (strict de A,
chrysalide/arc3/profil_c.py ; strict et étendu de C, experiments/T3.0/profil_c.py).
Usage : uv run python experiments/T3.1/regles_profilC/mesure.py [--dossier D] [jeux…]   (défaut : ls20 sp80)"""
import importlib.util
import json
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[2]
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(RACINE))
import mesure_exhaustivite as me

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.profil_c import hors_profil as hors_a

_spec = importlib.util.spec_from_file_location("profil_c_C", RACINE / "experiments/T3.0/profil_c.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


def profil(prog):
    regles = prog["regles"]
    n = len(regles)
    a = sum(not hors_a(r) for r in regles)
    s = sum(not pc.hors_profil(r, pc.PERMIS) for r in regles)
    e = sum(not pc.hors_profil(r, pc.ETENDU) for r in regles)
    un = sum(len(r.get("alors", [])) == 1 for r in regles)  # lois atomiques (CW-113/114) : un seul effet
    return {"regles": n, "un_effet": un, "strict_A": a, "strict_C": s, "etendu_C": e}


def main(argv):
    dossier = ICI
    if argv[:1] == ["--dossier"]:
        dossier, argv = Path(argv[1]).resolve(), argv[2:]
    jeux = argv or ["ls20", "sp80"]

    def charger(jeu):
        f = dossier / f"{jeu}.json"
        prog = Programme(json.loads(f.read_text()))
        return (lambda scene, action: prog.step(scene, action)), str(f)

    me.charger_step = charger  # seule la source des règles change ; la boucle de mesure est celle du banc
    arc = me.arcade()
    for f in me.fichiers_traces(jeux):
        r = me.mesurer(arc, f)
        r["profil"] = profil(json.loads((dossier / f"{r['jeu']}.json").read_text()))
        print(json.dumps({k: r[k] for k in ("jeu", "source", "transitions", "exactes_honnetes", "taux_honnete", "temoin",
                                            "a_vide", "reproduit", "premiere_erreur", "profil")}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
