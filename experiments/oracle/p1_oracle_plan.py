# SPDX-License-Identifier: MIT-0
"""F (substitution d'oracle DANS P1, volet plan) : P1 figé (paquet GEL27, exploration générique, mode complet, 150 coups
par niveau, graine 0, mémoire inter-jeux, 20 publics dans l'ordre alphabétique), comme `lancer.sh`, sans toucher au
paquet. Avec l'oracle, au début d'un niveau que P1 perd, le plan P0 vérifié (`plans/<jeu>_N<k>.json`) est joué d'abord
(coups comptés dans les 150) ; si le niveau n'est pas gagné, P1 reprend la main. Puis P1 joue seul les niveaux suivants.
La vérité est injectée par le banc ; elle n'entre pas dans la mémoire de P1 (le plan est joué, pas appris).
Contrôle (F-C2) : `--sans-oracle` doit redonner exactement `GEL27_moteur_seul/dev/generique/resume.json`.
`--transfert` (CW-449, report d'un niveau à l'autre) : les coups du plan gagnant sont notés dans la mémoire de coups de
P1, comme ceux d'une victoire de l'exploration générique.
Usage : uv run python experiments/oracle/p1_oracle_plan.py <sortie> [--sans-oracle | --transfert]"""
import json
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
GEL = RACINE / "experiments/GEL27_moteur_seul"
for p in (GEL / "livraison_explo/code", GEL / "references/astra4/livraison_astra4/ajouts", GEL / "livraison_p1/code", GEL):
    sys.path.insert(0, str(p))
import agent_p1.jouer as J  # active les bornes en nœuds, comme runner.py
from agent_p1.generique import Explorateur

JEUX = ["ar25", "bp35", "cd82", "dc22", "ft09", "g50t", "ka59", "lf52", "lp85", "ls20", "m0r0", "r11l", "re86", "sb26",
        "sc25", "sk48", "sp80", "su15", "tn36", "tr87"]  # 20 publics non témoins
DOSSIER = RACINE / "experiments/arc3/environment_files"


def plans():
    out = {}
    for f in (Path(__file__).parent / "plans").glob("*_N*.json"):
        d = json.loads(f.read_text())
        if d.get("plan_p1"):
            out[(d["jeu"], d["niveau"])] = [tuple(a) if isinstance(a, list) else a for a in d["plan_p1"]]
    return out


MEM = []  # mémoire de coups de P1 (Memoire de generique.py), capturée à son chargement


def brancher(table, transfert=False):
    orig, charger = J.essai_poussee, J.charger_memoire

    def charger_et_garder(d):
        m = charger(d)
        MEM[:] = [m]
        return m
    J.charger_memoire = charger_et_garder

    def essai(lab, od, budget, j):
        plan = table.get((str(lab.game)[:4], lab.level))
        if plan:
            for a in plan:
                if lab.won or lab.finished or len(lab.rows) >= budget:
                    break
                lab.play(a, purpose="oracle_plan")
            j.ecrire("oracle_plan", niveau=lab.level, coups=len(plan), gagne=lab.won)
            if lab.won:
                if transfert and MEM:  # --transfert : le plan gagnant nourrit la mémoire de coups, comme une victoire
                    from agent_p1.generique import type_action  # de l'exploration générique (memoire.noter)
                    for i, a in enumerate(plan[:len(lab.rows)]):
                        MEM[0].noter(type_action(a, lab.images[i]), True, victoire=(i == len(lab.rows) - 1))
                return {"agent": "oracle_plan", "victoire": True, "raison": "plan P0 vérifié"}
            if lab.finished:
                lab.reset_apres_defaite()
        return orig(lab, od, budget, j)
    J.essai_poussee = essai


def main():
    sortie, sans = Path(sys.argv[1]), "--sans-oracle" in sys.argv
    J.Explorateur = Explorateur
    table = {} if sans else plans()
    brancher(table, "--transfert" in sys.argv)
    memoire = sortie / "memoire_inter_jeux"
    memoire.mkdir(parents=True, exist_ok=True)
    for f in (GEL / "livraison_p1/memoire_depart").glob("*.json"):
        if not (memoire / f.name).exists():
            shutil.copy(f, memoire / f.name)
    tout = {}
    for g in JEUX:
        r = J.jouer_jeu(str(DOSSIER), g, str(sortie), 150, str(memoire), graine=0)
        tout[g] = {"niveaux_gagnes": sum(x["victoire"] for x in r), "coups": sum(x["coups"] for x in r),
                   "gagnants": [x["gagnant"] for x in r]}
        (sortie / "resume.json").write_text(json.dumps(tout, indent=1))
    print("TOTAL", sum(v["niveaux_gagnes"] for v in tout.values()), "plans", sorted(table), flush=True)


if __name__ == "__main__":
    main()
