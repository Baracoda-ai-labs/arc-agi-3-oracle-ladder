# SPDX-License-Identifier: MIT-0
"""CW-321 [session B] : audit du méta-modèle des 20 jeux publics. Fusionne
  (a) la lecture du code source (lecture_*.json, une par groupe de 4 jeux, témoins exclus),
  (b) le programme exact (audit_programmes.json, T3.1/regles),
  (c) ce que le moteur apprend ou utilise (constat sur le code du moteur : voir MOTEUR),
et la colonne T4 (audit_programmes.json). Sortie : audit.json + tableau imprimé (repris dans audit.md).
Usage : uv run python experiments/meta_modele/audit.py"""
import collections
import glob
import json
from pathlib import Path

ICI = Path(__file__).resolve().parent
# (c) moteur, d'après le code (20/10) : la chaîne principale (MoteurC) masque l'interface (faits.masque_cases, masque.py :
# barres apprises sur la trajectoire, exclues des objets) ; seule la défaite par CONTACT est apprise (`mort`, exportée en
# `perdre`) ; ni budget ni vies dans la théorie ; `ressource.py` (MoteurCle, ls20) se sert de la jauge comme énergie, hors
# chaîne principale ; les attributs d'état P10 ne sont lus que si la théorie en a (jamais pour budget/vies aujourd'hui).
MOTEUR = {"plateau": "appris (objets, rôles)", "controle": "appris (actions, mobile contrôlé, clic)",
          "dynamique": "appris (lois)", "economie": "non : jauge masquée (sauf ressource.py pour ls20, hors chaîne)",
          "defaite": "contact seulement (`mort`)", "niveaux": "transfert sous drapeau (D)", "interface": "masquée en bloc"}


# relevés à la main dans les lectures (formulations trop variées pour un filtre automatique)
RECHARGE_DANS_LE_NIVEAU = {"ls20": "cases de recharge (remet 42)", "sc25": "objet qui rend 10 actions"}
MINUTEUR = {"bp35": "plafond qui descend (niveaux 1-3)", "ka59": "bombes à retardement"}
COMPTEUR_CACHE = {"lf52": "le compteur affiché n'est pas celui qui fait perdre", "sp80": "4 versements ratés, non affichés",
                  "r11l": "5 contacts de danger, non affichés"}


# (b) budget DANS le programme : un compteur d'état cité par une règle `perdre` (vérifié règle par règle, 20/10 23 h 50) ;
# le comptage des opérations `consommer`/`epuise` ne suffit pas (ls20 écrit `["poser", "epuise", …]`, les autres « coups »)
PROG_BUDGET = {"cd82": "coups", "g50t": "coups", "lf52": "coups", "lp85": "jauge", "ls20": "epuise (jauge)", "sk48": "coups"}
PROG_VIES = {"ls20": "vies", "sp80": "versements (essais ratés)"}
PROG_RECHARGE = {"ls20": "rech"}


def main():
    lect = {}
    for f in sorted(glob.glob(str(ICI / "lecture_*.json"))):
        for r in json.loads(Path(f).read_text()):
            lect[r["jeu"]] = r
    prog = json.loads((ICI / "audit_programmes.json").read_text())
    out, synth = {}, collections.Counter()
    causes, rep = collections.Counter(), collections.Counter()
    for jeu in sorted(lect):
        r, p = lect[jeu], prog["programmes"].get(jeu, {})
        eco = r["economie"]
        cause_def = sorted({d["cause"] for d in r["defaite"]})
        causes.update(cause_def)
        for i in r["interface"]:
            rep[i["represente"]] += 1
        a = {"budget": bool(eco.get("budget_coups")), "vies": eco.get("vies") is not None,
             "recharge": RECHARGE_DANS_LE_NIVEAU.get(jeu), "minuteur": MINUTEUR.get(jeu),
             "compteur_cache": COMPTEUR_CACHE.get(jeu), "defaite_causes": cause_def,
             "defaite_hors_budget": [c for c in cause_def if c not in ("epuisement_budget",)],
             "interface": [i["represente"] for i in r["interface"]]}
        b = {"budget": jeu in PROG_BUDGET, "budget_variable": PROG_BUDGET.get(jeu), "vies": PROG_VIES.get(jeu),
             "defaite": p.get("defaite", 0) > 0,
             "victoire": p.get("victoire", 0) > 0, "contournements": p.get("contournements")}
        trous = []
        if a["budget"] and not b["budget"]:
            trous.append("budget non décrit")
        if a["vies"] and not b["vies"]:
            trous.append("vies non décrites")
        if a["defaite_hors_budget"] and not b["defaite"]:
            trous.append("défaite hors budget non décrite : " + ", ".join(a["defaite_hors_budget"]))
        if a["minuteur"]:
            trous.append("minuteur non décrit")
        if a["recharge"] and jeu not in PROG_RECHARGE:
            trous.append("recharge non décrite")
        synth.update(trous)
        out[jeu] = {"a_jeu": a, "b_programme": b, "c_moteur": MOTEUR, "trous": trous, "lecture": r}
    res = {"jeux": out, "synthese_trous": dict(synth), "causes_defaite": dict(causes), "interfaces": dict(rep),
           "t4": {k: v for k, v in prog["t4"].items() if k != "detail"}, "moteur": MOTEUR}
    (ICI / "audit.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("| jeu | budget (a) | vies | défaite (causes) | interface | budget dans le programme | défaite dans le programme | trous |")
    print("|---|---|---|---|---|---|---|---|")
    for jeu, v in out.items():
        a, b = v["a_jeu"], v["b_programme"]
        print(f"| {jeu} | {lect[jeu]['economie']['budget_coups'][:40]} | {lect[jeu]['economie']['vies'] or '—'} | "
              f"{', '.join(a['defaite_causes'])} | {', '.join(a['interface'])} | {'oui' if b['budget'] else 'non'} | "
              f"{'oui' if b['defaite'] else 'non'} | {len(v['trous'])} |")
    print("synthese", dict(synth)); print("causes", dict(causes)); print("interfaces", dict(rep))


if __name__ == "__main__":
    main()
