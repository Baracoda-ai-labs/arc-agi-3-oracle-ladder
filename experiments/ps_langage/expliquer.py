# SPDX-License-Identifier: MIT-0
"""CW-245 [session E] : brique d'exécution de l'« éveil » (chantier Dream). API :
    expliquer(jeu, trajectoire, regles=None, niveau=0, moteur="langage") -> {"taux", "n", "exactes", "divergences", "erreur"}
- jeu : identifiant du banc PuzzleScript ("p000"…"p176", `experiments/banc_ps/environment_files/`) ;
- trajectoire : actions depuis le début du niveau ("up"/"down"/"left"/"right"/"action" ou 1…5 comme ACTION1…5) ;
- regles : théorie candidate = texte de la section RULES PuzzleScript (None = les vraies règles du jeu ; "" = aucune règle) ;
- niveau : indice du niveau dans le banc (0 = premier niveau gardé) ;
- moteur : "langage" (interpréteur écrit dans le langage, critère au sprite près) ou "compile" (CW-256 : mêmes règles
  compilées en grilles de bits, `ps_compile.py`, ≈ ×250 plus rapide, 0 écart sur le banc ; critère : objets de chaque case
  et fin de niveau).
Une transition est EXPLIQUÉE si l'interpréteur PuzzleScript ÉCRIT DANS LE LANGAGE (`interpreteur_ps.json`), partant de l'état
vrai (rejeu RECALÉ, même définition que `moteur.porte_partielle` de C), prédit exactement les sprites dessinés (nom, position,
calque, pixels) et la fin de niveau. Vérité : `psmoteur.Partie` avec les vraies règles (sans moteur ARC).
Ligne de commande : uv run python experiments/ps_langage/expliquer.py p000 [niveau] [--sans-regles]"""
import copy
import json
import re
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2]
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(R / "experiments/banc_ps"))
sys.path.insert(0, str(R))
sys.path.insert(0, str(ICI))
import psmoteur  # noqa: E402

from chrysalide.arc3.langage import Programme  # noqa: E402
from chrysalide.arc3.ontologie_exec import Scene  # noqa: E402

ENV = R / "experiments/banc_ps/environment_files"
NOMS_PS = {1: "up", 2: "down", 3: "left", 4: "right", 5: "action"}
VERS_LANGAGE = {"up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT", "action": "SPACE"}


def _module(jeu):
    return next((ENV / jeu).glob(f"*/{jeu}.py"))


def remplacer_regles(source, regles):
    """Source PuzzleScript dont la section RULES est remplacée par `regles` (texte)."""
    lignes, out, dans = source.split("\n"), [], False
    for l in lignes:
        s = l.strip().lower()
        if s in psmoteur.SECTIONS:
            if dans:
                out.append(regles)
            dans = s == "rules"
            out.append(l)
            continue
        if not dans:
            out.append(l)
    return "\n".join(out)


def _scene(partie, k, cst, debut):
    """Scène dessinée comme runtime_ps._dessiner (un sprite par objet non-fond et par case)."""
    import juge_ps
    j, c = partie.j, max(1, min(5, 64 // max(partie.w, partie.h)))
    ox, oy = (64 - c * partie.w) // 2, (64 - c * partie.h) // 2
    sprites = []
    for i, cell in enumerate(partie.g):
        for kk, (o, _) in cell.items():
            if o != j.fond:
                sprites.append({"nom": o, "tags": ["type:" + o, "couche:%d" % kk], "x": ox + (i % partie.w) * c,
                                "y": oy + (i // partie.w) * c, "couche": kk,
                                "pixels": juge_ps._pixels(cst["COULEURS"][o], cst["SPRITES"][o], c)})
    sc = Scene((64, 64), cst["FOND"], cst["FOND"], sprites, donnees={"k": k}, n_niveaux=1, niveau=0)
    sc.debut = debut
    return sc


def _cles(sc):
    return sorted((s["nom"], int(s["x"]), int(s["y"]), int(s["couche"]), np.asarray(s["pixels"], dtype=np.int16).tobytes())
                  for s in sc.sprites if s.get("visible", True))


def expliquer(jeu, trajectoire, regles=None, niveau=0, moteur="langage"):
    import juge_ps
    if moteur == "compile":
        return _expliquer_compile(jeu, trajectoire, regles, niveau)
    f = _module(jeu)
    cst = juge_ps.constantes_module(f)
    cst["FOND"] = int(re.search(r"^FOND = (\d+)$", f.read_text(), re.MULTILINE).group(1))
    k = cst["NIVEAUX_PS"][niveau]
    vrai = psmoteur.Partie(psmoteur.Jeu(cst["SOURCE_PS"]), k)
    out = {"taux": 0.0, "n": 0, "exactes": 0, "divergences": [], "erreur": None}
    try:
        source = cst["SOURCE_PS"] if regles is None else remplacer_regles(cst["SOURCE_PS"], regles)
        texte = json.loads((ICI / "interpreteur_ps.json").read_text())
        texte["niveau"] = juge_ps.donnees(f, source=source, niveaux=[k])
        prog = Programme(texte)
    except Exception as ex:  # noqa: BLE001 — théorie qui ne s'analyse pas : rien d'expliqué
        out["erreur"] = f"{type(ex).__name__}: {str(ex)[:150]}"
        return out
    for t, a in enumerate(trajectoire):
        a = NOMS_PS.get(a, a)
        sc = _scene(vrai, k, cst, debut=t == 0)
        try:
            prog.step(sc, (VERS_LANGAGE[a], None, None), 0)
            erreur = None
        except Exception as ex:  # noqa: BLE001 — transition qui plante = non expliquée
            erreur = f"{type(ex).__name__}: {str(ex)[:100]}"
        vrai.tour(a)
        ok = erreur is None and _cles(sc) == _cles(_scene(vrai, k, cst, False)) and (sc.issue is not None) == vrai.gagne
        out["n"] += 1
        out["exactes"] += ok
        if not ok:
            out["divergences"].append({"t": t, "action": a, **({"erreur": erreur} if erreur else {})})
        if vrai.gagne:
            break
    out["taux"] = out["exactes"] / out["n"] if out["n"] else 0.0
    return out


def _expliquer_compile(jeu, trajectoire, regles, niveau):
    import juge_ps
    import ps_compile
    f = _module(jeu)
    cst = juge_ps.constantes_module(f)
    k = cst["NIVEAUX_PS"][niveau]
    vrai_jeu = psmoteur.Jeu(cst["SOURCE_PS"])
    vrai = psmoteur.Partie(vrai_jeu, k)
    depart = copy.deepcopy(vrai)
    out = {"taux": 0.0, "n": 0, "exactes": 0, "divergences": [], "erreur": None}
    try:
        theorie = psmoteur.Jeu(cst["SOURCE_PS"] if regles is None else remplacer_regles(cst["SOURCE_PS"], regles))
        jc = ps_compile.JeuCompile(theorie)
        pred = ps_compile.PartieCompilee(theorie, k, jc)
    except Exception as ex:  # noqa: BLE001 — théorie qui ne s'analyse pas : rien d'expliqué
        out["erreur"] = f"{type(ex).__name__}: {str(ex)[:150]}"
        return out
    for t, a in enumerate(trajectoire):
        a = NOMS_PS.get(a, a)
        pred.charger(vrai, depart)
        try:
            pred.tour(a)
            erreur = None
        except Exception as ex:  # noqa: BLE001 — transition qui plante = non expliquée
            erreur = f"{type(ex).__name__}: {str(ex)[:100]}"
        vrai.tour(a)
        ok = erreur is None and pred.objets() == vrai.objets() and pred.gagne == vrai.gagne
        out["n"] += 1
        out["exactes"] += ok
        if not ok:
            out["divergences"].append({"t": t, "action": a, **({"erreur": erreur} if erreur else {})})
        if vrai.gagne:
            break
    out["taux"] = out["exactes"] / out["n"] if out["n"] else 0.0
    return out


if __name__ == "__main__":
    jeu = sys.argv[1]
    niv = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0
    sol = json.loads(next((ENV / jeu).glob("*/verite.json")).read_text())["niveaux"][niv]["solution"]
    r = expliquer(jeu, sol, regles="" if "--sans-regles" in sys.argv else None, niveau=niv,
                  moteur="compile" if "--compile" in sys.argv else "langage")
    print(jeu, "niveau", niv, f"{r['exactes']}/{r['n']} transitions expliquées", r["erreur"] or "", r["divergences"][:5])
