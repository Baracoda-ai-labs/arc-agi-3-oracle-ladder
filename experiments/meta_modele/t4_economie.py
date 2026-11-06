# SPDX-License-Identifier: MIT-0
"""CW-324 P2 (B) : économie et défaite dans les `verite.json` des 104 jeux T4. Les 104 jeux partagent le même code de pas
(`pas_dedale`, `pas_tuiles`, `JeuGenere.step` : même empreinte), lu une fois :
  budget G par niveau (déjà `jauge_max`) ; 1 par action DÉCODÉE (dédale : flèches et SPACE, blocages compris, clic gratuit ;
  tuiles : chaque clic, hors plateau compris, le reste gratuit) ; victoire testée d'abord, défaite si le budget tombe à 0 ;
  recharge (dédale) : chaque case `recharges`, une fois, remet le budget à G ; défaites hors budget : lave, poursuivant.
Contrôle dans le VRAI jeu (niveau 1 de chaque jeu) : une même action répétée → GAME_OVER au coup G (la plus longue des
défaites), et une action gratuite ne finit jamais. Usage : uv run python experiments/meta_modele/t4_economie.py [--ecrire]"""
import ast
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
ENVS = R / "experiments/T4/jeux/t4/environment_files"
MARQUE = "CW-324 P2"


def niveaux_source(py):
    t = ast.parse(py.read_text())
    return next(ast.literal_eval(n.value) for n in t.body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "NIVEAUX")


def economie(N):
    ded = N["famille"] == "dedale"
    d = {"budget": N["G"], "remise": "début de niveau (et RESET)",
         "cout": ({"UP": 1, "DOWN": 1, "LEFT": 1, "RIGHT": 1, "SPACE": 1, "CLICK": 0} if ded
                  else {"CLICK": 1, "UP": 0, "DOWN": 0, "LEFT": 0, "RIGHT": 0, "SPACE": 0}),
         "cout_bloque": 1 if ded else None, "victoire_prime": True,
         "recharges": len(N.get("recharges") or []) if ded else 0}
    if d["recharges"]:
        d["recharge"] = "case de recharge, une fois chacune : budget remis à G"
    causes = ["epuisement_budget"]
    if ded and N.get("lave"):
        causes.append("lave")
    if ded and N.get("poursuivant"):
        causes.append("poursuivant")
    return d, causes


def controle(envs, gid, famille, G):
    from arc_agi import Arcade, OperationMode
    from arcengine.enums import GameAction
    arc = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(envs))
    out = {}
    essais = ([("UP", GameAction.ACTION1, None), ("DOWN", GameAction.ACTION2, None), ("LEFT", GameAction.ACTION3, None),
               ("RIGHT", GameAction.ACTION4, None), ("SPACE", GameAction.ACTION5, None), ("CLICK", GameAction.ACTION6,
                                                                                         {"x": 0, "y": 0})]
              if famille == "dedale" else [("CLICK", GameAction.ACTION6, {"x": 0, "y": 0}), ("UP", GameAction.ACTION1, None)])
    for nom, a, data in essais:
        env = arc.make(gid)
        env.reset()
        res = "plafond"
        for t in range(1, 3 * G + 5):
            f = env.step(a, data=data) if data else env.step(a)
            if f.state.name == "GAME_OVER":
                res = t
                break
            if f.levels_completed > 0 or f.state.name == "WIN":
                res = f"niveau@{t}"
                break
        out[nom] = res
    return out


def main(a):
    ecrire = "--ecrire" in a
    bilan = {"jeux": 0, "controle_ok": 0, "ecarts": []}
    for meta in sorted(ENVS.glob("*/*/metadata.json")):
        gid = json.loads(meta.read_text())["game_id"]
        v = json.loads((meta.parent / "verite.json").read_text())
        src = niveaux_source(next(meta.parent.glob("y*.py")))
        assert len(src) == len(v["niveaux"])
        for lv, N in zip(v["niveaux"], src):
            assert lv.get("jauge_max") == N["G"]
            lv["economie"], lv["defaite"] = economie(N)
        v["economie_regle"] = (f"{MARQUE} : budget G (jauge_max) remis au début du niveau ; 1 par action décodée "
                               "(dédale : flèches, SPACE, blocages compris ; tuiles : clics, hors plateau compris) ; "
                               "victoire testée avant la défaite ; défaite à 0 ; recharges et défaites hors budget par niveau")
        c = controle(ENVS, gid, v["famille"], src[0]["G"])
        gratuits = [k for k, x in v["niveaux"][0]["economie"]["cout"].items() if x == 0 and k in c]
        payants = [k for k in c if k not in gratuits]
        fins = [x for k, x in c.items() if k in payants and isinstance(x, int)]
        ok = bool(fins) and max(fins) == src[0]["G"] and all(c[k] == "plafond" for k in gratuits)
        bilan["jeux"] += 1
        bilan["controle_ok"] += ok
        if not ok:
            bilan["ecarts"].append({"jeu": gid, "famille": v["famille"], "G": src[0]["G"], "essais": c})
        if ecrire:
            (meta.parent / "verite.json").write_text(json.dumps(v, ensure_ascii=False) + "\n")
    print(json.dumps({k: bilan[k] for k in ("jeux", "controle_ok")}), json.dumps(bilan["ecarts"][:5], ensure_ascii=False))
    (R / "experiments/meta_modele/t4_economie_controle.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
