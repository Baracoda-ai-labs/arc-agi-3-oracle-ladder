# SPDX-License-Identifier: MIT-0
"""F (CW-474.1, CW-475.1) : RECOMPTAGE TYPÉ des interventions de T1, à partir des autopsies (`autopsie/*.json`).
Classes, au 1ᵉʳ coup où prédiction et réalité se séparent (coup par coup, franchissement de niveau lu dans les
événements enregistrés `partie.json` : `levels_completed`, `state`) :
  - victoire_reelle : le niveau est franchi en réalité ;
  - victoire_predite_non_observee : l'issue PRÉDITE est `niveau` ou `victoire`, et le jeu ne la donne pas ;
      sous-classe « images justes » (aucune case fausse : erreur de condition de victoire seule) ou « avec écart visuel » ;
  - defaite_predite : l'issue prédite est une défaite (classe à part) ;
  - ecart_visuel : pas d'issue prédite, l'image prédite diffère de l'image réelle ;
  - hors_plan : l'action observée n'est pas l'action prédite (non comparable).
Usage : uv run python experiments/oracle/recompte_type.py <autopsie.json>:<run> …"""
import collections
import json
import sys
from pathlib import Path


def franchi(run, jeu, niv, k, pas):
    """Le niveau est-il franchi au coup k + pas (événements enregistrés) ?"""
    rows = json.loads((Path(run) / jeu / f"N{niv}" / "partie.json").read_text())["rows"]
    if k + pas - 1 >= len(rows):
        return False
    r, avant = rows[k + pas - 1], rows[k + pas - 2]["levels_completed"] if k + pas >= 2 else 0
    return r["levels_completed"] > avant or "WIN" in str(r.get("state"))


def classe(run, cle, v):
    jeu, niv, k = cle.split(":")
    niv, k = int(niv), int(k)
    pas = v.get("pas") or 0
    n = v.get("coups_executes") or 0
    if v.get("plan") and v.get("plan", [])[:n] != v.get("joues", [])[:n]:
        return "hors_plan"
    if pas and franchi(run, jeu, niv, k, pas):
        return "victoire_reelle"
    iss = v.get("issue_simulee")
    if iss in ("niveau", "victoire"):
        return "victoire_predite_non_observee (" + ("images justes" if not v.get("n_cases") else "avec écart visuel") + ")"
    if iss is not None:
        return "defaite_predite"
    if v.get("etat") in ("divergence", "mort"):
        return "ecart_visuel"
    return "autre : " + str(v.get("etat"))


def main():
    for arg in sys.argv[1:]:
        src, run = arg.split(":", 1)
        d = json.loads(Path(src).read_text())
        c = collections.Counter(classe(run, k, v) for k, v in d.items())
        print(f"{Path(src).stem} ({len(d)} interventions) :")
        for cl, n in sorted(c.items(), key=lambda x: -x[1]):
            print(f"   {n:3d}  {cl}")


if __name__ == "__main__":
    main()
