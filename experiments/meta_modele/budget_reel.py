# SPDX-License-Identifier: MIT-0
"""CW-324 P2 (B) : budget de coups MESURÉ dans le vrai jeu, contrôle des programmes corrigés. Depuis le début du niveau k
(préfixe R0, `plafonds.env_au_niveau`), une même action répétée jusqu'à GAME_OVER, changement de niveau ou plafond.
Le budget du niveau est le plus grand nombre de coups qui finit en GAME_OVER (une défaite plus tôt vient d'une autre
cause : chute, contact) ; une action qui ne finit jamais n'est pas décomptée (gratuite, ou sans effet non compté).
Avec `--programme`, le même essai dans le PROGRAMME exact (victoire comprise) : coup où l'issue devient « defaite ».
Usage : uv run python experiments/meta_modele/budget_reel.py <jeu> [niveaux=1] [--programme] → budget_<jeu>.json"""
import copy
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(R), str(R / "experiments/T3.0"), str(R / "experiments/T3.1")]
TEM = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
PLAFOND = 1100
ESSAIS = [(1, None, None), (2, None, None), (3, None, None), (4, None, None), (5, None, None), (6, 0, 0), (6, 32, 32),
          (6, 63, 63)]
NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 6: "MOUSE"}


def reel(env0, coup):
    import plafonds
    env, n0 = copy.deepcopy(env0), None
    for t in range(1, PLAFOND + 1):
        f = plafonds.jouer(env, coup)
        n0 = f.levels_completed if n0 is None else n0
        if f.state.name == "GAME_OVER":
            return t, "defaite"
        if f.state.name == "WIN" or f.levels_completed > n0:
            return t, "niveau"
    return None, "plafond"


def programme(env0, gid, coup):
    from mesure_exhaustivite import _resync

    from chrysalide.arc3.langage import Programme, utilise_canevas
    texte = json.loads((R / "experiments/T3.1/regles" / f"{gid}.json").read_text())
    texte = json.loads(json.dumps(texte).replace('"CLICK"', '"MOUSE"'))
    sc = _resync(copy.deepcopy(env0), None, utilise_canevas(texte))
    p = Programme(texte)
    a = (NOMS[coup[0]], coup[1], coup[2])  # clic : (ligne, colonne) comme le banc
    for t in range(1, PLAFOND + 1):
        p.step(sc, a, sc.niveau)
        if sc.issue == "defaite":
            return t, "defaite"
        if sc.issue in ("niveau", "victoire"):
            return t, "niveau"
    return None, "plafond"


def main(a):
    import plafonds
    gid, niveaux, prog = a[0], [int(x) for x in (a[1] if len(a) > 1 and not a[1].startswith("-") else "1").split(",")], \
        "--programme" in a
    assert gid not in TEM
    sys.path.insert(0, str(R / "experiments/T3.10"))
    import dynamique_exacte as DX
    out = {"jeu": gid, "programmes": DX.version_programmes(), "niveaux": {}}  # CW-330
    for k in niveaux:
        env, f = plafonds.env_au_niveau(gid, k)
        if env is None:
            out["niveaux"][k] = "préfixe absent"
            continue
        acts = set(getattr(f, "available_actions", []) or [])
        lignes = {}
        for coup in ESSAIS:
            if acts and coup[0] not in {int(getattr(x, "value", x)) for x in acts}:
                continue
            nom = NOMS[coup[0]] + ("" if coup[1] is None else f"@{coup[1]},{coup[2]}")
            lignes[nom] = {"jeu": reel(env, coup)}
            if prog:
                try:
                    lignes[nom]["programme"] = programme(env, gid, coup)
                except Exception as e:  # noqa: BLE001
                    lignes[nom]["programme"] = f"{type(e).__name__}: {e}"
        dj = [v["jeu"][0] for v in lignes.values() if v["jeu"][1] == "defaite"]
        out["niveaux"][k] = {"budget_mesure": max(dj) if dj else None, "essais": lignes}
        print(gid, k, out["niveaux"][k]["budget_mesure"], {n: (v["jeu"], v.get("programme")) for n, v in lignes.items()},
              flush=True)
    d = R / "experiments/meta_modele/budgets"
    d.mkdir(exist_ok=True)
    (d / f"budget_{gid}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
