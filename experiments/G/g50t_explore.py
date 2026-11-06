"""[G] g50t N1, victoire déf. 2 (depuis les observations) avec C : exploration ciblée en partie RÉELLE, puis plan.
Le programme exact n'est jamais lu. Tous les coups réels sont comptés (exploration comprise), dans UNE partie.
1. Théorie induite sur la 1re vie de Franzen (drapeaux de C, `CHRYS_TENUE=1`), exportée dans le langage.
2. Dans la théorie, depuis le début du niveau : plus court chemin (flèches) qui pose l'objet piloté sur un objet qu'il n'a
   JAMAIS recouvert pendant la trace de Franzen (rejouée dans la théorie) ; on le joue dans le vrai jeu, plus un pas
   pour en sortir (ouverture puis fermeture visibles).
3. Réinduction sur les deux trajectoires (Franzen + exploration), export, puis `macro_g` depuis l'état courant (scène
   perçue sur l'image courante, état caché de la théorie après rejeu des coups d'exploration).
4. Le plan est joué à la suite dans la même partie ; victoire si le niveau est franchi.
Usage : CHRYS_RETOUR=1 CHRYS_FANTOME=1 CHRYS_AMODAL=2 CHRYS_POURSUITE_UTILE=1 CHRYS_TENUE=1 PYTHONPATH=. \
        .venv/bin/python experiments/G/g50t_explore.py"""
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1"), str(RACINE / "experiments/G")]
from g50t_def2 import theorie

from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import induire
from chrysalide.arc3.logique.theorie import cells
from chrysalide.arc3.moteur import _sprite
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile, _chevauche_px, cloner

CODE = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5}
INVERSE = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}
FLECHES = ("UP", "DOWN", "LEFT", "RIGHT")


def signature(o):
    """(nom, tags, couleurs) : les objets perçus n'ont ni nom ni tags, leur identité est leur couleur (classe)."""
    px = np.asarray(o["pixels"])
    return o.get("nom"), tuple(o.get("tags") or ()), tuple(sorted(set(px[px >= 0].ravel().tolist())))


def pilotes(prog, sc0):
    sig = set()
    for a in FLECHES:
        s2, e2 = cloner(sc0, prog.etat)
        prog.etat = e2
        try:
            prog.step(s2, (a, None, None))
        except Exception:  # noqa: BLE001, S112
            continue
        if len(s2.sprites) == len(sc0.sprites):
            sig |= {signature(a0) for a0, b in zip(sc0.sprites, s2.sprites, strict=True) if (a0["x"], a0["y"]) != (b["x"], b["y"])}
    return sig


def recouverts(sc, sig):
    """Signatures des objets visibles (non pilotés) qu'un objet piloté recouvre."""
    pil = [o for o in sc.sprites if signature(o) in sig and o.get("visible", True)]
    return {signature(o) for o in sc.sprites if signature(o) not in sig and o.get("visible", True)
            and any(_chevauche_px(p, o) for p in pil)}


def exploration(prog, sc0, etat0, actions_franzen, sig):
    """Plus court chemin de flèches (dans la théorie) vers un objet jamais recouvert pendant la trace → (chemin, cible)."""
    vus_trace, s, e = set(), *cloner(sc0, etat0)
    for a in actions_franzen:  # objets recouverts pendant la trace de Franzen, rejouée dans la théorie
        prog.etat = e
        try:
            prog.step(s, (a, None, None))
        except Exception:  # noqa: BLE001
            break
        e = prog.etat
        vus_trace |= recouverts(s, sig)
        if s.issue is not None:
            break
    deja = {tuple(sorted((o["x"], o["y"]) for o in sc0.sprites if signature(o) in sig))}
    file, pas_appris, bloques = deque([(sc0, etat0, [])]), {}, []
    while file:
        s, e, ch = file.popleft()
        for a in FLECHES:
            s2, e2 = cloner(s, e)
            prog.etat = e2
            try:
                prog.step(s2, (a, None, None))
            except Exception:  # noqa: BLE001, S112
                continue
            if s2.issue is not None:
                continue
            avant = [(o["x"], o["y"]) for o in s.sprites if signature(o) in sig]
            p = tuple(sorted((o["x"], o["y"]) for o in s2.sprites if signature(o) in sig))
            if p != tuple(sorted(avant)) and len(p) == len(avant) == 1:
                pas_appris.setdefault(a, (p[0][0] - avant[0][0], p[0][1] - avant[0][1]))
            elif len(avant) == 1:
                bloques.append((s, ch, a))  # la théorie croit ce coup sans effet
            if p in deja:
                continue
            deja.add(p)
            neufs = recouverts(s2, sig) - vus_trace
            if neufs:
                return [*ch, a], sorted(map(str, neufs))
            file.append((s2, prog.etat, [*ch, a]))
    # aucun objet neuf atteignable : un coup que la théorie croit BLOQUÉ, vers un objet jamais recouvert, est l'expérience
    for s, ch, a in bloques:
        if a not in pas_appris:
            continue
        dx, dy = pas_appris[a]
        pil = [dict(o, x=o["x"] + dx, y=o["y"] + dy) for o in s.sprites if signature(o) in sig]
        neufs = {signature(o) for o in s.sprites if signature(o) not in sig and o.get("visible", True)
                 and any(_chevauche_px(q, o) for q in pil)} - vus_trace
        if neufs:
            return [*ch, a], sorted(map(str, neufs)) + ["(coup cru bloqué)"]
    return None, None


def main():
    import plafonds as pf
    from banc_p0 import _init
    k, tr, th, prog_t, non, sc0 = theorie()
    assert not non, non
    _init()  # (change de répertoire ; les chemins suivants sont absolus)
    import macro_g
    from divergences_traces import trajectoire

    from chrysalide.arc3.moteur import _codes_c
    _, _, lots = trajectoire("g50t", 600, str(RACINE / "experiments/T3.10/diag_ref/traces/g50t_ref/g50t_trace.jsonl"))
    noms = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 7: "UNDO"}
    actions_franzen = [noms.get(c, "?") for c in _codes_c(lots) or []]
    prog = ProgrammeCompile(prog_t)
    sig = pilotes(prog, sc0)
    prog = ProgrammeCompile(prog_t)
    chemin, cible = exploration(prog, sc0, prog.etat, [a for a in actions_franzen if a in CODE], sig)
    print(json.dumps({"pilotes": sorted(map(str, sig)), "exploration": chemin, "cible": cible}), flush=True)
    if not chemin:
        return
    explo = [*chemin, INVERSE[chemin[-1]]]
    env, fr = pf.env_au_niveau("g50t", k)
    grilles, joues = [np.asarray(fr.frame[-1])], []
    for a in explo:
        f = pf.jouer(env, (CODE[a], None, None))
        joues.append(a)
        grilles.append(np.asarray(f.frame[-1]))
    # réinduction : trajectoire de Franzen + trajectoire d'exploration (actions dans le code de C : mêmes noms)
    tr2 = Trajectoire([g.tolist() for g in grilles], [{"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5}[a] for a in joues])
    tr2.exclues = frozenset(tr2.exclues) | {(y, x) for e in tr2.etats for o in e if o[0] == 297 for x, y in cells(o)}
    th2 = induire([(tr, None, None), (tr2, None, None)], limite_s=90)[0]
    th2.hors_jeu = tr.exclues | tr2.exclues
    prog2, non2 = exporter(th2, tr.taille)
    print(json.dumps({"coups_exploration": len(joues), "non_exportes": non2,
                      "regles": [r.get("nom") for r in prog2.get("regles", [])]}, ensure_ascii=False), flush=True)
    if non2:
        return
    # état courant dans la théorie : scène perçue au début du niveau, coups d'exploration rejoués
    p2 = ProgrammeCompile(prog2)
    s = Scene((tr.taille[1], tr.taille[0]), tr.fond, tr.fond, [_sprite(o) for o in tr2.etats[0]])
    for a in joues:
        p2.step(s, (a, None, None))
    r = macro_g.chercher("g50t", k, 20000, 300, texte=prog2, scene=s, etat=p2.etat)
    print(json.dumps({x: r.get(x) for x in ("programme", "arret", "plan", "coups", "cpu")}), flush=True)
    if not r.get("coups"):
        return
    fin = None
    for a in r["coups"]:  # suite de la MÊME partie
        fin = pf.jouer(env, (CODE[a], None, None))
        if fin.levels_completed >= k or fin.state.name in ("WIN", "GAME_OVER"):
            break
    gagne = bool(fin is not None and (fin.levels_completed >= k or fin.state.name == "WIN"))
    print(json.dumps({"victoire_def2": gagne, "coups_reels_total": len(joues) + len(r["coups"]),
                      "etat_final": fin.state.name if fin else None}), flush=True)


if __name__ == "__main__":
    main()
