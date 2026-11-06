# SPDX-License-Identifier: MIT-0
"""CW-371 (B) : non-contradiction des axiomes universels (docs/ONTOLOGIE_FORMELLE_GDL_VGDL.md) avec les VRAIS jeux.
On rejoue la 1re trace R0 de chaque jeu public (témoins exclus avant toute lecture) dans le vrai moteur et on émet, à
chaque pas, des faits ASP tirés de l'état réel. clingo cherche ensuite les violations des contraintes. Une violation veut
dire qu'un axiome est trop fort pour ce jeu (ou que l'émission est fausse) : elle est listée, jamais « corrigée ».
  A-U4 exclusivité de fin : jamais fin de niveau ET défaite au même pas ;
  A-U6 solidité : (chevauchement NOUVEAU, absent au pas d'avant : le décor peut se chevaucher par construction) deux sprites BLOQUANTS (BlockingMode ≠ NOT_BLOCKED), collidables et TANGIBLES, ne se chevauchent pas
        en fin de pas (test de collision du moteur) ;
  A-U3 unicité : un même sprite (identité) n'a qu'une position par pas (contrôle de l'émetteur).
Usage : uv run python experiments/meta_modele/non_contradiction.py [pas_max=300] [jeux…] → non_contradiction.json"""
import json
import sys
from itertools import combinations
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(R), str(R / "experiments/T3.1"), str(R / "experiments/T3.0"), str(R / "experiments/T2.12")]
TEM = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
REGLES = """
viol(au4, T) :- fin_niveau(T), defaite(T).
viol(au6, T, A, B) :- chevauche(A, B, T), not chevauche(A, B, T-1), T > 1, tangible(A, T), tangible(B, T), A < B.
viol(au3, T, O) :- pos(O, X1, Y1, T), pos(O, X2, Y2, T), (X1, Y1) != (X2, Y2).
exemple(N1, N2, T) :- viol(au6, T, A, B), nom(A, N1, T), nom(B, N2, T).
#show viol/2. #show viol/3. #show viol/4. #show exemple/3.
"""


def faits_trace(f, pas_max):
    from arcengine.enums import GameAction
    from fidelite import NUM, evenements
    from mesure_exhaustivite import action_de, arcade
    env = arcade().make(Path(f).name.split("_p")[0])
    env.reset()
    out, t, niv = [], 0, env._game._current_level_index
    stable = {}  # identité STABLE d'un sprite sur toute la trace (même objet Python), pas son rang dans la liste du pas
    for e in evenements(f):
        if "board" not in e or e.get("type") == "initial" or e.get("action_name", "") not in NUM:
            continue
        a = action_de(e)
        nom = e["action_name"]
        obs = env.step(GameAction.from_id(NUM[nom]), data={"x": a[2], "y": a[1]}) if NUM[nom] == 6 else \
            env.step(GameAction.from_id(NUM[nom]))
        t += 1
        if env._game._current_level_index != niv:
            out.append(f"fin_niveau({t}).")
            stable.clear()  # nouveau niveau : nouveaux objets
            niv = env._game._current_level_index
        if obs is not None and obs.state.name == "GAME_OVER":
            out.append(f"defaite({t}).")
        spr = [s for s in env._game.current_level.get_sprites() if s.is_visible]
        ids = {id(s): stable.setdefault(id(s), len(stable)) for s in spr}
        for s in spr:
            out.append(f"pos({ids[id(s)]}, {int(s.x)}, {int(s.y)}, {t}).")
            if s.is_collidable and getattr(s.interaction, "name", "") == "TANGIBLE" and \
                    getattr(s.blocking, "name", "NOT_BLOCKED") != "NOT_BLOCKED":  # « solide » = bloque (BlockingMode)
                out.append(f"tangible({ids[id(s)]}, {t}).")
            out.append(f'nom({ids[id(s)]}, "{str(s.name)[:20]}", {t}).')
        col = [s for s in spr if s.is_collidable]
        for s1, s2 in combinations(col, 2):
            try:
                if s1.collides_with(s2):
                    a1, a2 = sorted((ids[id(s1)], ids[id(s2)]))
                    out.append(f"chevauche({a1}, {a2}, {t}).")
            except Exception:  # noqa: BLE001, S112 — test de collision indisponible pour ce couple
                continue
        if t >= pas_max:
            break
    return out, t


def faits_programme(f, pas_max):
    """Même chose dans le PROGRAMME exact du jeu (T3.1/regles), sur les mêmes actions : positions des sprites de la scène
    du programme (identité = rang dans la scène, stable tant que la scène n'est pas reprise) et issue du programme."""
    from arcengine.enums import GameAction
    from fidelite import NUM, evenements
    from mesure_exhaustivite import _resync, action_de, arcade, charger_step
    jeu = Path(f).name[:4]
    step, _ = charger_step(jeu)
    cv = bool(getattr(step, "canevas", False))
    env = arcade().make(Path(f).name.split("_p")[0])
    env.reset()
    sc, t, out, niv = _resync(env, None, cv), 0, [], env._game._current_level_index
    for e in evenements(f):
        if "board" not in e or e.get("type") == "initial" or e.get("action_name", "") not in NUM:
            continue
        a, nom = action_de(e), e["action_name"]
        env.step(GameAction.from_id(NUM[nom]), data={"x": a[2], "y": a[1]}) if NUM[nom] == 6 else \
            env.step(GameAction.from_id(NUM[nom]))
        t += 1
        if a[0] != "RESET":
            step(sc, a)
            for i, o in enumerate(sc.sprites):
                if o.get("visible", True):
                    out.append(f"pos(s{i}, {int(o['x'])}, {int(o['y'])}, {t}).")
            iss = getattr(sc, "issue", None)
            if iss in ("niveau", "victoire"):
                out.append(f"fin_niveau({t}).")
            if iss == "defaite":
                out.append(f"defaite({t}).")
        if a[0] == "RESET" or env._game._current_level_index != niv or getattr(sc, "issue", None):
            sc, niv = _resync(env, None, cv), env._game._current_level_index  # reprise, comme mesure_exhaustivite
        if t >= pas_max:
            break
    return out, t


def verifier(faits):
    import clingo
    c = clingo.Control(["--warn=none"])
    c.add("base", [], REGLES + "\n".join(faits))
    c.ground([("base", [])])
    viols = []
    c.solve(on_model=lambda m: viols.extend(str(s) for s in m.symbols(shown=True)))
    return viols


def main(a):
    pas_max = int(a[0]) if a and a[0].isdigit() else 300
    jeux = [x for x in a if not x.isdigit()]
    traces = {}
    for f in sorted((R / "runs_pod/R0").glob("*/artifacts/*_events.jsonl")):
        j = f.name[:4]
        if j in TEM or (jeux and j not in jeux) or j in traces:
            continue
        traces[j] = f
    res = {}
    for j, f in traces.items():
        try:
            faits, t = faits_trace(f, pas_max)
            v = verifier(faits)
            par = {}
            for s in v:
                cle = s.split("(")[1].split(",")[0] if s.startswith("viol") else "exemple"
                par.setdefault(cle, []).append(s)
            res[j] = {"pas": t, "violations": {k: len(x) for k, x in par.items()}, "exemples": {k: x[:3] for k, x in par.items()}}
        except Exception as e:  # noqa: BLE001 — une erreur d'émission est un résultat, comptée
            res[j] = {"erreur": f"{type(e).__name__}: {e}"}
        print(j, res[j].get("pas"), res[j].get("violations", res[j].get("erreur")), flush=True)
    (R / "experiments/meta_modele/non_contradiction.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
