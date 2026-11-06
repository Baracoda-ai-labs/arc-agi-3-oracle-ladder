# SPDX-License-Identifier: MIT-0
"""F (CW-452, « il faut un gain Kaggle ») : où le moteur v2 (paquet du gel : P1 + films + nouveauté, 2 graines,
`experiments/films_p1/combo/fg_g*`) peut-il ajouter des points à Franzen (passages R du pod, Franzen pur) ?
Tableau par niveau : (a) v2 gagne, Franzen perd ; (b) les deux gagnent (coups v2 contre Franzen) ; (c) aucun.
Gain : chaque passage R est rejoué en remplaçant, AU DÉBUT des niveaux choisis, le jeu de Franzen par celui de v2.
  - v2 gagne → coups du niveau = coups de v2, puis Franzen reprend au niveau suivant tel qu'il était dans ce passage
    (s'il avait perdu ce niveau, on suppose PRUDEMMENT qu'il perd le suivant : rien n'est compté au-delà) ;
  - v2 perd → ses coups sont gaspillés (s'ajoutent à ceux de Franzen), Franzen reprend tel qu'il était.
Score officiel (taaf/arc_agi) : par niveau min(115, (h/a)² × 100), pondéré 1..n, plafonné par les niveaux gagnés.
Vérifié : reproduit 180/180 scores des passages R5–R13 (CCM-040-F).
Usage : uv run python experiments/oracle/prise_de_main.py <dossier des benchmark R*.json> → tableau + gains"""
import glob
import json
import statistics
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
V2 = [R / "experiments/films_p1/combo/fg_g0", R / "experiments/films_p1/combo/fg_g1"]


def score(apl, base, gagnes, n):
    tw = mw = 0
    ts = 0.0
    for i in range(n):
        w = i + 1
        tw += w
        a = apl[i] if i < len(apl) else 0
        s = min(115.0, (base[i] / a) ** 2 * 100) if i < gagnes and a > 0 else 0.0
        if s > 0:
            mw += w
        ts += s * w
    return min(ts / tw, mw / tw * 100) if tw else 0.0


def v2():
    """(jeu, niveau) → liste par graine de (gagné, coups)."""
    out = {}
    for d in V2:
        for f in d.glob("*/resultat.json"):
            for x in json.loads(f.read_text()):
                out.setdefault((x["jeu"][:4], x["niveau"]), []).append((bool(x["victoire"]), int(x["coups"])))
    return out


def rejouer(run, choix, graine_v2):
    """Score d'un jeu dans un passage R, avec v2 au début des niveaux de `choix`."""
    g, n, base = run["game_id"][:4], run["number_of_levels"], run["base_actions_per_level"]
    apl, gagnes = list(run["actions_per_level"]), run["levels_completed"]
    nouv_apl, nouv_g = [], 0
    for k in range(1, n + 1):
        if k > gagnes + 1:
            break  # Franzen n'a jamais atteint ce niveau dans ce passage
        franzen_gagne, af = k <= gagnes, apl[k - 1] if k - 1 < len(apl) else 0
        if (g, k) in choix and graine_v2.get((g, k)):
            gv, av = graine_v2[(g, k)]
            if gv:
                nouv_apl.append(av)
                nouv_g = k
                if not franzen_gagne:
                    break  # prudence : Franzen n'avait pas atteint k + 1 ; rien compté au-delà
                continue
            af += av  # coups de v2 gaspillés
        if not franzen_gagne:
            break
        nouv_apl.append(af)
        nouv_g = k
    return score(nouv_apl, base, nouv_g, n)


def main():
    runs = [json.loads(Path(f).read_text())["game_runs"] for f in sorted(glob.glob(str(Path(sys.argv[1]) / "R*.json")))]
    V = v2()
    jeux = sorted({r["game_id"][:4] for p in runs for r in p})
    # tableau par niveau
    lignes, cas = [], {"a": [], "b": [], "c": []}
    for g in jeux:
        n = next(r["number_of_levels"] for p in runs for r in p if r["game_id"][:4] == g)
        for k in range(1, n + 1):
            atteint = [r for p in runs for r in p if r["game_id"][:4] == g and r["levels_completed"] + 1 >= k]
            fg = [r for r in atteint if r["levels_completed"] >= k]
            vv = V.get((g, k), [])
            v_gagne = sum(x[0] for x in vv)
            if not atteint and not v_gagne:
                continue
            af = statistics.median(r["actions_per_level"][k - 1] for r in fg) if fg else None
            av = statistics.median(x[1] for x in vv if x[0]) if v_gagne else None
            h = next(r["base_actions_per_level"][k - 1] for p in runs for r in p if r["game_id"][:4] == g)
            c = "a" if v_gagne and len(fg) < len(atteint) / 2 else "b" if v_gagne else "c"
            if c in "ab" or (atteint and len(fg) < len(atteint)):
                cas[c].append((g, k))
                lignes.append(f"| {g} N{k} | {c} | {v_gagne}/2 | {av if av is not None else '—'} | {len(fg)}/{len(atteint)} "
                              f"| {af if af is not None else '—'} | {h} |")
    print("| niveau | cas | v2 gagne (graines) | coups v2 | Franzen gagne / atteint | coups Franzen (méd.) | h |")
    print("|---|---|---|---|---|---|---|")
    print("\n".join(l for l in lignes if "| c |" not in l))
    print(f"\n(c) niveaux atteints par Franzen et perdus par les deux : {len(cas['c'])}")
    # gains selon la politique
    base = statistics.mean(statistics.mean(score(r["actions_per_level"], r["base_actions_per_level"],
                                                 r["levels_completed"], r["number_of_levels"]) for r in p) for p in runs)
    print(f"\nScore moyen Franzen (20 jeux, {len(runs)} passages) : {base:.2f}")
    graines = [{key: vals[i] for key, vals in V.items() if len(vals) > i} for i in range(2)]

    def gain(choix):
        s = [statistics.mean(rejouer(r, choix, gv) for r in p) for p in runs for gv in graines]
        return statistics.mean(s) - base
    sur = {key for key, vals in V.items() if len(vals) == 2 and all(x[0] for x in vals)}  # v2 gagne aux 2 graines
    for nom, choix in [
        ("(a) seulement", set(cas["a"]) & sur),
        ("(b) seulement, là où v2 joue moins que Franzen (médiane)", {k for k in set(cas["b"]) & sur}),
        ("(a) + (b) où v2 gagne aux 2 graines", (set(cas["a"]) | set(cas["b"])) & sur),
    ]:
        if "moins" in nom:
            choix = {k for k in choix if _moins(k, V, runs)}
        print(f"- {nom} : {len(choix)} niveaux {sorted(choix)} → gain {gain(choix):+.2f} point")


def _moins(key, V, runs):
    g, k = key
    fg = [r["actions_per_level"][k - 1] for p in runs for r in p if r["game_id"][:4] == g and r["levels_completed"] >= k]
    av = statistics.median(x[1] for x in V[key] if x[0])
    return bool(fg) and av < statistics.median(fg)


if __name__ == "__main__":
    main()


def politique_en_ligne(run, v2_jeu, K):
    """Règle décidable sans connaître le jeu : le moteur joue d'abord (au plus K coups par niveau) ; tant qu'il gagne,
    il garde la main ; au premier échec, ses K coups sont gaspillés et Franzen reprend ce niveau tel qu'il était dans
    le passage (prudence : si Franzen n'avait pas atteint ce niveau, rien n'est compté au-delà)."""
    n, base = run["number_of_levels"], run["base_actions_per_level"]
    apl, gagnes = list(run["actions_per_level"]), run["levels_completed"]
    out, ng = [], 0
    for k in range(1, n + 1):
        gv, av = v2_jeu.get(k, (False, 150))
        if gv and av <= K:
            out.append(av)
            ng = k
            continue
        if k > gagnes:  # Franzen n'a pas gagné ce niveau (ou ne l'avait pas atteint) : fin
            break
        out.append(apl[k - 1] + min(K, av) + 1)  # coups du moteur gaspillés + RESET, puis Franzen
        ng = k
        for k2 in range(k + 1, gagnes + 1):  # Franzen garde la main jusqu'au bout, tel qu'il était
            out.append(apl[k2 - 1])
            ng = k2
        break
    return score(out, base, ng, n)


def lire_v4(dossier):
    """Par jeu et niveau : (gagné par un agent v4, coups) ; si non, les coups joués par la v4 avant l'exploration (sonde)."""
    d = {}
    for f in sorted(Path(dossier).glob("*/resultat.json")):
        for x in json.loads(f.read_text()):
            p = f.parent / f"N{x['niveau']}" / "partie.json"
            rows = json.loads(p.read_text()).get("rows", []) if p.exists() else []
            m = sum(1 for w in rows if not str(w.get("purpose", "")).startswith("generique"))
            v4 = bool(x["victoire"]) and str(x["gagnant"]).startswith("v4")
            d.setdefault(x["jeu"][:4], {})[x["niveau"]] = (v4, int(x["coups"]) if v4 else m)
    return d


def porte_v4(run, vj, sonde_def=2):
    """Règle « porte v4 », décidable en direct : à chaque début de niveau, la v4 du moteur regarde la scène ; si elle la
    reconnaît et gagne, elle garde la main ; à la première fois qu'elle ne gagne pas, ses coups de sonde (0 à 4, ou plus
    si elle a joué) s'ajoutent à ceux de Franzen, qui garde la main jusqu'à la fin du jeu, tel qu'il était dans le passage."""
    n, base = run["number_of_levels"], run["base_actions_per_level"]
    apl, gag = list(run["actions_per_level"]), run["levels_completed"]
    out, ng, franzen = [], 0, False
    for k in range(1, n + 1):
        if not franzen:
            v4, c = vj.get(k, (False, sonde_def))
            if v4:
                out.append(c)
                ng = k
                continue
            franzen = True
            if k > gag:
                break
            out.append(apl[k - 1] + c)
            ng = k
            continue
        if k > gag:
            break
        out.append(apl[k - 1])
        ng = k
    return score(out, base, ng, n)
