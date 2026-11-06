# SPDX-License-Identifier: MIT-0
"""F (CW-448, C6 classe S) : sonde de 30 min sur les 7 niveaux que « tout exact » (P0, 600 s) ne gagne pas. Budget ou
heuristique ? Sur le programme EXACT compilé (comme plafonds.p0), depuis le début du niveau :
  1. largeur : recherche en largeur par couches (clé complète, états dédoublonnés), 120 s → états distincts par
     profondeur et facteur de branchement effectif ;
  2. chemin gagnant connu : la partie du préfixe enregistré (R0) qui finit le niveau, rejouée dans le programme exact
     (après le dernier RESET) → longueur L et fidélité (le programme dit-il « niveau » au bout ?) ;
  3. heuristique : `distance_but` (celle de la recherche « but ») le long de ce chemin : départ, minimum, nombre de pas
     où elle baisse, monte ou reste plate.
Référence humaine h : base_actions_per_level (benchmark R12).
Usage : uv run python experiments/oracle/sonde_s.py [jeu:k,…] [sortie.json] → experiments/oracle/sonde_s.json"""
import glob
import itertools
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
import plafonds

NIVEAUX = [("bp35", 1), ("sb26", 1), ("sc25", 1), ("sk48", 1), ("r11l", 2), ("tn36", 2), ("ar25", 3)]
LARGEUR_S = 120


def humain():
    f = glob.glob(str(RACINE / "runs_pod/passages/R12/*/benchmark.json"))[0]
    return {x["game_id"][:4]: x["base_actions_per_level"] for x in json.loads(Path(f).read_text())["game_runs"]}


def sonde(gid, k, h):
    from mesure_exhaustivite import _resync

    from chrysalide.arc3.langage import Programme, utilise_canevas
    from chrysalide.arc3.logique.plan_langage import cle_complete, distance_but, regle_victoire
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    texte = json.loads((plafonds.REGLES / f"{gid}.json").read_text())
    env, fr = plafonds.env_au_niveau(gid, k)
    sc0 = _resync(env, None, utilise_canevas(texte))
    prog = ProgrammeCompile(texte)
    e0 = prog.etat
    dispo = [a for a in fr.available_actions if a != 6 and a in plafonds.NOMS]
    coups = [(a, None, None) for a in dispo] + (plafonds.clics(fr.frame[-1]) if 6 in fr.available_actions else [])

    def nom(c):
        return ("CLICK", c[1], c[2]) if c[0] == 6 else (plafonds.NOMS[c[0]], None, None)

    def pas(sc, etat, c):
        sc2, etat2 = cloner(sc, etat)
        prog.etat = etat2
        prog.step(sc2, nom(c))
        return sc2, prog.etat

    out = {"jeu": gid, "niveau": k, "actions": len(coups), "humain": h[k - 1] if h and len(h) >= k else None}
    # 1. largeur par couches
    t0, couche, vus, par_prof, gagne_a = time.time(), [(sc0, e0)], {cle_complete(sc0, e0)}, [], None
    while couche and time.time() - t0 < LARGEUR_S:
        suivante = []
        for sc, etat in couche:
            for c in coups:
                if time.time() - t0 > LARGEUR_S:
                    break
                try:
                    sc2, etat2 = pas(sc, etat, c)
                except Exception:  # noqa: BLE001, S112
                    continue
                if sc2.issue in ("niveau", "victoire"):
                    gagne_a = gagne_a or len(par_prof) + 1
                    continue
                if sc2.issue is not None:
                    continue
                kk = cle_complete(sc2, etat2)
                if kk not in vus:
                    vus.add(kk)
                    suivante.append((sc2, etat2))
        if time.time() - t0 > LARGEUR_S and suivante:
            par_prof.append(len(suivante))  # couche incomplète : borne basse
            out["derniere_couche_incomplete"] = True
            break
        par_prof.append(len(suivante))
        couche = suivante
    out.update(etats_par_profondeur=par_prof, profondeur_atteinte=len(par_prof), gagne_en_largeur_a=gagne_a,
               etats=len(vus))
    b = [par_prof[i] / par_prof[i - 1] for i in range(1, len(par_prof)) if par_prof[i - 1] > 0]
    out["branchement_effectif"] = round((b[-3:] and (sum(b[-3:]) / len(b[-3:])) or 0), 2)
    # 2. chemin gagnant connu (préfixe du niveau k + 1)
    pk, pk1 = plafonds.prefixe(gid, k), plafonds.prefixe(gid, k + 1)
    if pk is None or pk1 is None:
        out["chemin"] = None
        return out
    seg = pk1[len(pk):]
    dernier_reset = max([i for i, c in enumerate(seg) if c[0] == 0], default=-1)
    seg = [c for c in seg[dernier_reset + 1:] if c[0] != 0]
    interp, regle = Programme(texte), regle_victoire(texte)
    sc, etat, hs, fin = sc0, e0, [], None
    if regle is not None:
        hs.append(distance_but(interp, regle, sc0, e0))
    for c in seg:
        try:
            sc, etat = pas(sc, etat, c)
        except Exception as ex:  # noqa: BLE001
            fin = f"plantage {type(ex).__name__}"
            break
        if sc.issue is not None:
            fin = sc.issue
            break
        if regle is not None:
            hs.append(distance_but(interp, regle, sc, etat))
    d = [b - a for a, b in itertools.pairwise(hs)]
    out["chemin"] = {"longueur": len(seg), "resets_avant": dernier_reset + 1 > 0, "fin_programme": fin,
                     "h_depart": hs[0] if hs else None, "h_min": min(hs) if hs else None,
                     "h_baisse": sum(x < 0 for x in d), "h_plat": sum(x == 0 for x in d), "h_monte": sum(x > 0 for x in d)}
    return out


def main():
    sel = [(x.split(":")[0], int(x.split(":")[1])) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else NIVEAUX
    hu, res = humain(), {}
    sortie = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "sonde_s.json"
    if sortie.exists():
        res = json.loads(sortie.read_text())
    for gid, k in sel:
        try:
            r = sonde(gid, k, hu.get(gid))
        except Exception as e:  # noqa: BLE001
            import traceback
            r = {"jeu": gid, "niveau": k, "plantage": f"{type(e).__name__}: {e}", "pile": traceback.format_exc()[-600:]}
        res[f"{gid}:{k}"] = r
        print(json.dumps({x: r.get(x) for x in ("jeu", "niveau", "actions", "humain", "etats_par_profondeur",
                                                 "branchement_effectif", "gagne_en_largeur_a", "chemin", "plantage")},
                         ensure_ascii=False), flush=True)
        sortie.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
