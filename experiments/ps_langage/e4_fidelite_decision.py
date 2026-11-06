# SPDX-License-Identifier: MIT-0
"""CW-250 E4 [session E] : fidélité de la théorie (taux d'explication, rejeu recalé) contre décision (niveau gagné), sans
calcul nouveau. Seule source qui porte les deux pour la même exécution : la campagne PARTIEL=2 de A
(`experiments/moteur_seul/explo_partiel/traces/<explorateur>/<jeu>_trace.jsonl`, CCM-225/226-A).
Unité = (explorateur, jeu, niveau) où le moteur a été appelé en mode partiel au moins une fois. Niveau d'un appel = nombre de
`fin_niveau` vus avant lui. Mesures : dernier taux avant la fin du niveau (ou du temps), niveau fini, fini par un coup du moteur.
Usage : uv run python experiments/ps_langage/e4_fidelite_decision.py"""
import json
from pathlib import Path

from scipy.stats import mannwhitneyu, spearmanr

R = Path(__file__).resolve().parents[2]
TR = R / "experiments/moteur_seul/explo_partiel/traces"


def unites():
    out = []
    for f in sorted(TR.glob("*/*_trace.jsonl")):
        niv, u = 0, {}
        for ligne in f.read_text().splitlines():
            d = json.loads(ligne)
            if d.get("taux_explication") is not None:
                e = u.setdefault(niv, {"explorateur": f.parent.name, "jeu": f.name.split("_")[0], "niveau": niv, "taux": [],
                                       "fini": False, "fini_moteur": False, "plans_joues": 0})
                e["taux"].append(d["taux_explication"])
                e["plans_joues"] += bool(d.get("plan_joue"))
            if d.get("fin_niveau"):
                if niv in u:
                    u[niv]["fini"] = True
                    u[niv]["fini_moteur"] = d.get("source") == "moteur"
                niv += 1
        out += list(u.values())
    return out


def main():
    us = unites()
    for e in us:
        e["dernier"], e["max"], e["appels"] = e["taux"][-1], max(e["taux"]), len(e.pop("taux"))
    print(f"{len(us)} unités (explorateur, jeu, niveau) avec appel partiel ; finies {sum(e['fini'] for e in us)}, "
          f"dont par le moteur {sum(e['fini_moteur'] for e in us)}")
    for e in sorted(us, key=lambda e: -e["dernier"]):
        print(f"  {e['explorateur']:9} {e['jeu']} N{e['niveau'] + 1}  dernier {e['dernier']:.3f}  max {e['max']:.3f}  "
              f"appels {e['appels']:4}  fini {int(e['fini'])}  par moteur {int(e['fini_moteur'])}")
    res = {"unites": us}
    for cle in ("fini", "fini_moteur"):
        oui = [e["dernier"] for e in us if e[cle]]
        non = [e["dernier"] for e in us if not e[cle]]
        rho, p = spearmanr([e["dernier"] for e in us], [int(e[cle]) for e in us]) if len(us) > 2 else (None, None)
        mw = mannwhitneyu(oui, non) if oui and non else None
        res[cle] = {"n_oui": len(oui), "n_non": len(non), "rho": rho, "p_spearman": p,
                    "p_mannwhitney": None if mw is None else mw.pvalue,
                    "mediane_oui": sorted(oui)[len(oui) // 2] if oui else None,
                    "mediane_non": sorted(non)[len(non) // 2] if non else None}
        print(cle, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res[cle].items()})
    (Path(__file__).parent / "resultats/e4_fidelite_decision.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
