# SPDX-License-Identifier: MIT-0
"""Banc des niveaux ratés par Franzen (CW-260, A). Pour chaque jeu public non témoin que Franzen R0 ne finit pas, le
niveau FRONTIÈRE k = 1er niveau raté : Franzen l'a atteint, donc son historique existe (préfixe de R0 jusqu'au début de k,
`plafonds.prefixe`). Les niveaux au-delà ne sont jamais atteints par Franzen (aucun historique, aucune solution publique).
Par niveau :
  1. plafond à règles exactes : P0 (`but` puis `paliers`) depuis le début du niveau ;
  2. moteur réel : la Branche rejoue l'historique Franzen comme observations, puis le moteur seul joue le niveau k ;
  3. classe de la 1re défaillance : S (même à règles exactes, pas de plan) ; puis, pour le moteur réel, M (« ne rejoue pas »
     dominant ou plans démentis), G (« pas de but » dominant), sinon « autre » ; « gagné » si le moteur finit le niveau.
Usage : uv run python experiments/instrument/banc_rates.py <jeu> <sortie.json> [minutes=10] [noeuds=200000] [secondes=300]"""
import json
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]

R0 = {"bp35": (1, 9), "dc22": (3, 6), "g50t": (0, 7), "ka59": (3, 7), "lf52": (2, 10), "ls20": (3, 7), "m0r0": (5, 6),
      "re86": (4, 8), "sc25": (4, 6), "sk48": (1, 8), "sp80": (3, 6), "su15": (3, 9), "tr87": (5, 6)}  # summary.txt R0


def version_programmes():
    """Version des programmes exacts lus (B, CCM-237-B : empreinte du contenu de `T3.1/regles`, budget et défaite ou non)."""
    try:
        sys.path.insert(0, str(RACINE / "experiments/T3.10"))
        from dynamique_exacte import version_programmes as v
        return v()
    except Exception as e:  # noqa: BLE001 — la version est une étiquette, pas une condition du banc
        return {"erreur": f"{type(e).__name__}: {e}"[:120]}


def classe(p0, mot):
    if mot.get("niveaux_coup_final_moteur"):
        return "gagné"
    if not p0.get("gagne"):
        return "S"
    ref = mot.get("refus") or {}
    n_rejoue = sum(v for k, v in ref.items() if k.startswith("ne rejoue pas"))
    n_but = sum(v for k, v in ref.items() if k.startswith("pas de but"))
    b = mot.get("bilan") or {}
    if b.get("moteur_plans") and b.get("moteur_divergences", 0) >= b["moteur_plans"] / 2:
        return "M"
    if n_rejoue >= n_but and n_rejoue:
        return "M"
    return "G" if n_but else "autre"


def entonnoir(mot):
    """CW-315 : dernier maillon atteint par le moteur réel sur le niveau, lu dans son bilan (0 = rien).
    1 états perçus (« perçus » non mesuré ici : compté atteint dès qu'il y a eu des appels du moteur) ; 2 règles compatibles
    (porte 1 passée) ; 3 prédictions nouvelles exactes (porte 2 passée) ; 4 but exploitable (pas de refus « pas de but »
    majoritaire) ; 5 plan trouvé ; 6 plan exécuté ; 7 victoire réelle."""
    b, ref = mot.get("bilan") or {}, mot.get("refus") or {}
    n_but = sum(v for k, v in ref.items() if k.startswith("pas de but"))
    etapes = [bool(b.get("moteur_appels")), bool(b.get("moteur_porte1_ok")), bool(b.get("moteur_porte2_ok")),
              bool(b.get("moteur_porte2_ok")) and n_but < max(1, b.get("moteur_appels", 0)) / 2,
              bool(b.get("moteur_plans")), bool(b.get("moteur_coups_plan")), bool(mot.get("niveaux_coup_final_moteur"))]
    dernier = 0
    for i, ok in enumerate(etapes, 1):
        if not ok:
            break
        dernier = i
    if etapes[-1]:  # victoire réelle du moteur : maillon 7 même si un compteur intermédiaire manque (ft09 N3, banc k+1)
        dernier = 7
    noms = ["rien", "perçus", "règles compatibles", "prédictions exactes", "but exploitable", "plan trouvé", "plan exécuté",
            "victoire réelle"]
    return {"maillon": dernier, "nom": noms[dernier], "cpu_moteur_s": b.get("moteur_cpu_s"),
            "divergences": b.get("moteur_divergences")}


def sous_buts(plafonds, gid, k, noeuds, secondes):
    """Planificateur générique du défi 6 (`plan_langage.planifier_langage(recherche="generique")`, sans macros) depuis la
    scène exacte du début du niveau ; plan rejoué dans le VRAI jeu (même préfixe), comme `plafonds.verifier_plan`."""
    from mesure_exhaustivite import _resync

    from chrysalide.arc3.langage import utilise_canevas
    from chrysalide.arc3.logique.plan_langage import planifier_langage
    texte = json.loads((RACINE / "experiments/T3.1/regles" / f"{gid}.json").read_text())
    env, fr = plafonds.env_au_niveau(gid, k)
    if env is None:
        return {"raison": "niveau non atteint par le préfixe"}
    sc = _resync(env, None, utilise_canevas(texte))
    dispo = [a for a in fr.available_actions if a != 6 and a in plafonds.NOMS]
    coups = [(plafonds.NOMS[a], None, None) for a in dispo]
    if 6 in fr.available_actions:
        coups += [("CLICK", c[1], c[2]) for c in plafonds.clics(fr.frame[-1])]
    t = time.time()
    plan, st = planifier_langage(texte, sc, coups, recherche="generique", noeuds=noeuds, secondes=secondes)
    r = {"recherche": "sous_buts", "secondes": round(time.time() - t, 1), "plan": None if not plan else len(plan),
         "raison": (st or {}).get("raison")}
    if not plan:
        return r
    inv = {v: kk for kk, v in plafonds.NOMS.items()}
    return plafonds.verifier_plan(r, gid, k, [(6, a[1], a[2]) if a[0] == "CLICK" else (inv[a[0]], None, None) for a in plan])


def _banc_moteur_seul():
    """experiments/moteur_seul/banc.py, chargé par son chemin (experiments/T3.0/banc.py de C porte le même nom)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("banc_moteur_seul", RACINE / "experiments/moteur_seul/banc.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(gid, sortie, minutes=10, noeuds=200000, secondes=300):
    import plafonds
    banc = _banc_moteur_seul()
    os.environ["CHRYS_MOTEUR"] = "1"
    w, n = R0[gid]
    k = w + 1
    out = {"jeu": gid, "niveau": k, "franzen_r0": f"{w}/{n}", "programmes": version_programmes()}
    pre = plafonds.prefixe(gid, k)
    f_r0 = RACINE / "experiments/instrument/prefixes_r0.json"  # CW-275 : préfixes régénérés et vérifiés, prioritaires
    if f_r0.exists() and str(k) in json.loads(f_r0.read_text()).get(gid, {}):
        pre = [tuple(c) for c in json.loads(f_r0.read_text())[gid][str(k)]]
        out["prefixe_source"] = "prefixes_r0.json"

        def env_au_niveau(g, kk, _pre=pre, _orig=plafonds.env_au_niveau):  # P0 depuis le même préfixe (RESET compris)
            if (g, kk) != (gid, k):
                return _orig(g, kk)
            from arcengine.enums import GameAction
            from mesure_exhaustivite import arcade
            env = arcade().make(g)
            f = env.reset()
            for c in _pre:
                f = env.step(GameAction.RESET) if c[0] == 0 else plafonds.jouer(env, c)
                if f is not None and f.state.name == "GAME_OVER":
                    f = env.step(GameAction.RESET)
            return (env, f) if f is not None and f.levels_completed == kk - 1 else (None, None)
        plafonds.env_au_niveau = env_au_niveau
    out["prefixe_franzen"] = None if pre is None else len(pre)
    if pre is None:
        out["raison"] = "pas d'historique Franzen jusqu'à ce niveau"
    else:
        t = time.time()
        p0 = {}
        if os.environ.get("CHRYS_SOUSBUTS") == "1":  # CW-278 : sous-buts lus dans le programme (défi 6), vérifiés en jeu
            p0 = sous_buts(plafonds, gid, k, int(noeuds), float(secondes))
            out["sous_buts"] = {x: p0.get(x) for x in ("plan", "gagne", "raison", "secondes")}
        # CCM-014-G : la recherche du MOTEUR (`planifier_langage`, clé compilée) gagne ls20 N4 que `but` de plafonds rate
        for rech in () if p0.get("gagne") else ("langage_but", "but", "paliers"):
            p0 = plafonds.p0(gid, k, int(noeuds), float(secondes), rech)
            out[f"plafond_{rech}"] = {x: p0.get(x) for x in ("noeuds", "etats", "plan", "gagne", "raison")}  # chaque recherche
            if p0.get("gagne"):
                break
        out["plafond_exact"] = {x: p0.get(x) for x in ("recherche", "noeuds", "etats", "plan", "gagne", "raison")}
        out["plafond_s"] = round(time.time() - t, 1)
        mot = banc.jouer(gid, "rates", float(minutes), 0, Path(sortie).parent / "traces", prefixe=pre)
        out["moteur"] = {x: mot.get(x) for x in ("niveau_depart", "niveaux", "niveaux_coup_final_moteur", "coups", "refus",
                                                  "duree_s")}
        out["moteur"]["bilan"] = {x: v for x, v in (mot.get("bilan") or {}).items() if isinstance(v, (int, float))}
        out["classe"] = classe(p0, mot)
        out["entonnoir"] = entonnoir(out["moteur"])
    Path(sortie).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({x: out.get(x) for x in ("jeu", "niveau", "prefixe_franzen", "classe")}))


if __name__ == "__main__":
    main(*sys.argv[1:])
