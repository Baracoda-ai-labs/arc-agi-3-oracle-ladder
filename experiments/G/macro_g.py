"""[G] Charte 21-30, solveur spécialisé, 1ʳᵉ brique : MACRO-ACTIONS « amener l'objet piloté sur une case », générique.
- Objet piloté = sprites dont la position change sous une flèche depuis le départ (lu dans le simulateur, pas nommé).
- Macro depuis un état s : parcours en largeur aux seules flèches, nouveauté sur la position des objets pilotés (chaque
  position gardée une fois, au plus court) → un état par case atteinte, avec son chemin de flèches.
- Recherche haute (largeur sur les états, clé `cle_complete`) : depuis chaque état, toutes les macros + chaque action
  non fléchée (SPACE, UNDO, clics) ; ALTERNANCE (coupe heuristique, déclarée) : après une macro, seulement une action
  non fléchée, puisque deux macros d'affilée atteignent les mêmes cases qu'une seule. Victoire testée à chaque pas, y compris au milieu d'une macro.
- Le plan est rejoué dans le vrai jeu (`plafonds.jouer`).
Usage : PYTHONPATH=. .venv/bin/python experiments/G/macro_g.py jeu:niveau,… [etats_hauts=20000] [secondes=600]"""
import json
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banc_p0 import _init

FLECHES = ("UP", "DOWN", "LEFT", "RIGHT")


def chercher(gid, k, etats_hauts=20000, secondes=600, alterner=True, empreinte=False, texte=None, scene=None, etat=None,
             reserve=None, actions=None, image=None, verifier=True, clics_scene=False):
    """`texte` : programme à utiliser (ex. la théorie INDUITE de C, exportée dans le langage) au lieu du programme exact
    de `T3.1/regles` ; `scene` / `etat` : état de départ (sinon lu dans le moteur au début du niveau k). Le plan est
    toujours rejoué dans le vrai jeu depuis le début du niveau k. `reserve` (CW-333, `CHRYS_ECONOMIE`) : coups encore
    permis par le budget du jeu ; aucun état plus profond n'est gardé, donc aucun plan plus long ne sort. Les états de
    réserves différentes ne sont pas fusionnés : la réserve est dans l'état caché quand le programme la décrit."""
    import plafonds as pf
    from mesure_exhaustivite import _resync

    from chrysalide.arc3.langage import utilise_canevas
    from chrysalide.arc3.logique.plan_langage import cle_complete
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    T, t0 = time.process_time, time.process_time()
    if reserve is None:  # F (CCM-013-F) : réserve lue par `limite()` sous CHRYS_ECONOMIE=1 (None sinon : pas de borne)
        from chrysalide.arc3.logique.economie_plan import limite
        reserve = limite()
    exact = texte is None
    texte = json.loads((pf.REGLES / f"{gid}.json").read_text()) if exact else texte
    if scene is not None and actions is not None:  # C (g50t N2) : état fourni, coups possibles fournis, pas de préfixe
        env, fr = None, None
        dispo_brut, img = list(actions), image
    else:
        env, fr = pf.env_au_niveau(gid, k)
        if env is None:
            return {"jeu": gid, "niveau": k, "arret": "niveau non atteint"}
        dispo_brut, img = list(fr.available_actions), fr.frame[-1]
    sc0 = scene if scene is not None else _resync(env, None, utilise_canevas(texte))
    prog = ProgrammeCompile(texte)
    if etat is not None:
        import copy
        prog.etat = copy.deepcopy(etat)
    dispo = [a for a in dispo_brut if a != 6 and a in pf.NOMS]
    coups = [(a, None, None) for a in dispo] + (pf.clics(img) if 6 in dispo_brut and img is not None else [])
    nom = {c: (("CLICK", c[1], c[2]) if c[0] == 6 else (pf.NOMS[c[0]], None, None)) for c in coups}
    fleches = [c for c in coups if nom[c][0] in FLECHES]
    autres = [c for c in coups if nom[c][0] not in FLECHES]
    n_sim = 0
    # clics_scene (après gel 2, CCM-043-G) : clics candidats recalculés sur la SCÈNE de chaque état haut (case visible la
    # plus centrale de chaque objet), au lieu de l'image du départ seulement : un objet déplacé (poussé) reste cliquable ;
    # clics_scene == "pilotes" : seulement les objets de même signature qu'un piloté (sélection au clic)
    sans_clic = [c for c in autres if nom[c][0] != "CLICK"]

    def clics_de(sc):
        out = []
        if 6 not in dispo_brut:
            return out
        for o in sc.sprites:
            if not o.get("visible", True) or (clics_scene == "pilotes" and sig(o) not in signatures):
                continue
            px = np.asarray(o["pixels"])
            ys, xs = np.nonzero(px >= 0)
            if not len(xs) or len(xs) > 64 * 64 // 4:
                continue
            my, mx = ys.mean(), xs.mean()
            j = int(np.argmin((ys - my) ** 2 + (xs - mx) ** 2))
            c = (6, int(o["y"] + ys[j]), int(o["x"] + xs[j]))
            if c not in nom:
                nom[c] = ("CLICK", c[1], c[2])
            if c not in out:
                out.append(c)
        return out

    def pas(sc, etat, c):
        nonlocal n_sim
        n_sim += 1
        s2, e2 = cloner(sc, etat)
        prog.etat = e2
        try:
            prog.step(s2, nom[c])
        except Exception:  # noqa: BLE001 — coup qui plante : branche abandonnée
            return None, None
        return s2, prog.etat
    # objets pilotés : ceux qu'une flèche déplace depuis le départ
    pilotes = set()
    for c in fleches:
        s2, _ = pas(sc0, prog.etat, c)
        if s2 is not None and len(s2.sprites) == len(sc0.sprites):
            pilotes |= {i for i, (a, b) in enumerate(zip(sc0.sprites, s2.sprites, strict=True))
                        if (a["x"], a["y"]) != (b["x"], b["y"])}

    emp = None
    if empreinte:  # nouveauté de la macro = (positions des pilotés, ce que lit le but) au lieu des positions seules
        from guidage import empreinte_but

        from chrysalide.arc3.logique.plan_langage import regle_victoire
        regle = regle_victoire(texte)
        if regle is not None:
            emp, _ = empreinte_but(prog, regle)
    import numpy as np

    def sig(o):  # (nom, tags, couleurs) : un objet perçu n'a ni nom ni tags, son identité est sa couleur
        px = np.asarray(o["pixels"])
        return o.get("nom"), tuple(o.get("tags") or ()), tuple(sorted(set(px[px >= 0].ravel().tolist())))
    signatures = {sig(sc0.sprites[i]) for i in pilotes}

    def pos(sc, etat=None):
        """Positions des objets de même signature (nom, tags) que les objets pilotés (survit aux créations d'objets),
        avec l'empreinte de ce que lit le but si elle est demandée."""
        p = tuple(sorted((o["x"], o["y"], bool(o.get("visible", True))) for o in sc.sprites
                         if sig(o) in signatures))
        return p if emp is None else (p, emp(sc, etat))

    def macros(sc, etat):
        """→ liste (scène, état, flèches jouées, gagné) : un état par position nouvelle des objets pilotés."""
        vus, file, out = {pos(sc, etat)}, deque([(sc, etat, [])]), []
        while file:
            s, e, ch = file.popleft()
            for c in fleches:
                s2, e2 = pas(s, e, c)
                if s2 is None:
                    continue
                if s2.issue in ("niveau", "victoire"):
                    return [(s2, e2, [*ch, c], True)]
                if s2.issue is not None:
                    continue
                p = pos(s2, e2)
                if p in vus:
                    continue
                vus.add(p)
                out.append((s2, e2, [*ch, c], False))
                file.append((s2, e2, [*ch, c]))
        return out
    plan = None
    haut, file = {cle_complete(sc0, prog.etat)}, deque([(sc0, prog.etat, [], False)])
    while file and len(haut) < etats_hauts and T() - t0 < secondes and plan is None:
        s, e, ch, apres_macro = file.popleft()
        suivants = [] if (apres_macro and alterner) else [(s2, e2, [cs], g, True) for s2, e2, cs, g in macros(s, e)]
        for c in (autres if not clics_scene else [*sans_clic, *clics_de(s)]):
            s2, e2 = pas(s, e, c)
            if s2 is not None and (s2.issue is None or s2.issue in ("niveau", "victoire")):
                suivants.append((s2, e2, [[c]], s2.issue is not None, False))
        for s2, e2, cs, gagne, est_macro in suivants:
            seq = [x for bloc in cs for x in (bloc if isinstance(bloc, list) else [bloc])]
            if reserve is not None and len(ch) + len(seq) > reserve - (0 if gagne else 1):
                continue  # convention de F (economie_plan) : position non gagnante ≤ réserve − 1, coup gagnant gratuit
            if gagne:
                plan = [*ch, *seq]
                break
            kk = cle_complete(s2, e2)
            if kk in haut:
                continue
            haut.add(kk)
            file.append((s2, e2, [*ch, *seq], est_macro))
    if plan is None and not file and alterner and T() - t0 < secondes:  # espace épuisé : on relève l'alternance
        r2 = chercher(gid, k, etats_hauts, secondes - (T() - t0), alterner=False, empreinte=empreinte,
                      texte=None if exact else texte, scene=scene, etat=etat, reserve=reserve, actions=actions,
                      image=image, verifier=verifier, clics_scene=clics_scene)
        return {**r2, "repli": "sans alternance"}
    r = {"jeu": gid, "niveau": k, "programme": "exact" if exact else "fourni", "pilotes": len(pilotes), "empreinte": emp is not None, "alterner": alterner, "etats_hauts": len(haut), "simulations": n_sim,
         "plan": None if plan is None else len(plan), "reserve": reserve, "cpu": round(T() - t0, 1),
         "arret": "plan" if plan else ("espace épuisé" if not file else "budget")}
    if plan:
        r["coups"] = [nom[c][0] if nom[c][0] != "CLICK" else f"CLICK{nom[c][1:]}" for c in plan]
    if plan and verifier and env is not None:  # sinon c'est l'appelant qui joue le plan (même partie, C)
        env2, _ = pf.env_au_niveau(gid, k)
        fin = None
        for c in plan:
            fin = pf.jouer(env2, c)
            if fin.levels_completed >= k or fin.state.name in ("WIN", "GAME_OVER"):
                break
        r["gagne"] = bool(fin is not None and (fin.levels_completed >= k or fin.state.name == "WIN"))
        r["coups"] = [nom[c][0] if nom[c][0] != "CLICK" else f"CLICK{nom[c][1:]}" for c in plan]
    return r


if __name__ == "__main__":
    _init()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    for x in sys.argv[1].split(","):
        j, k = x.split(":")
        print(json.dumps(chercher(j, int(k), *(int(a) for a in sys.argv[2:3]), *(float(a) for a in sys.argv[3:4]))),
              flush=True)
