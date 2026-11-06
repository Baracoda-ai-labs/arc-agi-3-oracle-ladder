# SPDX-License-Identifier: MIT-0
"""Bloc P (CW-031, CW-040) : perception adaptative dans le harnais de Franzen, PAR PARTIE (les jeux tournent en fils
d'exécution : une variable d'environnement globale ne convient pas). Le patch (scripts/arc3/patcher_perception.py)
remplace, dans ToolAgent._build_user_message, `current_grid_image_part(current_frame)` par
`image_tour(self, current_frame, current_grid_image_part)`.
- CHRYS_PERCEPTION absent ou ≠ 1 : renvoie exactement `defaut(frame)` (règle F-C2 : Franzen inchangé, aucun fichier).
- CHRYS_PERCEPTION=1 : perception.Routeur décide, au début de chaque tour, 'haute' (image telle que Franzen la produit,
  ×MULTIMODAL_UPSCALE = 10) ou 'compacte' : l'image courante ET les images de diff/animation en attente sont réduites
  à ×CHRYS_PERC_BASSE (4 par défaut ; plus proche voisin, exact case par case). Signaux du routeur : niveau (frame.level),
  surprise = game over au tour précédent (images de game over en attente), état neuf (hachage graphe.etat, bord 4).
  Journal : $CHRYS_DOSSIER/perception.jsonl (un enregistrement par tour : partie, niveau, mode, cause)."""
import base64
import io
import json
import os
import threading
import time
from pathlib import Path

try:
    from chrysalide.arc3.graphe import etat
    from chrysalide.arc3.perception import Routeur
except ImportError:  # copie dans le harnais de Franzen (inference/chrysalide_arc3/)
    from inference.chrysalide_arc3.graphe import etat
    from inference.chrysalide_arc3.perception import Routeur

_VERROU = threading.Lock()


def actif():
    return os.environ.get("CHRYS_PERCEPTION", "") == "1"


def _ent(nom, defaut):
    try:
        return int(os.environ.get(nom, "") or defaut)
    except ValueError:
        return defaut


def reduire_url(url, haute, basse):
    """Réduit une image PNG (data URL) agrandie ×haute en ×basse, au plus proche voisin (exact pour une grille de cases)."""
    from PIL import Image
    tete, b64 = url.split(",", 1)
    im = Image.open(io.BytesIO(base64.b64decode(b64)))
    w, h = im.size
    im = im.resize((w * basse // haute, h * basse // haute), Image.Resampling.NEAREST)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return tete + "," + base64.b64encode(buf.getvalue()).decode("ascii")


def reduire_part(part, haute, basse):
    if not isinstance(part, dict) or "image_url" not in part:
        return part
    return {**part, "image_url": {**part["image_url"], "url": reduire_url(part["image_url"]["url"], haute, basse)}}


class Perception:
    def __init__(self):
        self.rt = Routeur(calme=_ent("CHRYS_PERC_CALME", 2), stagnation=_ent("CHRYS_PERC_STAGNATION", 5))
        self.vus = set()

    def choisir(self, frame, mort):
        s = etat([list(r) for r in frame.grid], frame.level)
        neuf = s not in self.vus
        self.vus.add(s)
        return self.rt.tour(frame.level, surprise=mort, etat_neuf=neuf)


def _journal(agent, frame, mode, cause):
    d = Path(os.environ.get("CHRYS_DOSSIER", "chrysalide_runs"))
    d.mkdir(parents=True, exist_ok=True)
    e = {"t": round(time.time(), 3), "partie": id(agent), "jeu": str(getattr(agent, "game_id", "")),
         "niveau": frame.level, "pas": frame.step, "mode": mode, "cause": cause}
    with _VERROU, (d / "perception.jsonl").open("a") as f:
        f.write(json.dumps(e) + "\n")


def image_tour(agent, frame, defaut):
    if not actif() or frame is None:
        return defaut(frame)
    p = agent.__dict__.setdefault("_chrys_perc", Perception())
    mode, cause = p.choisir(frame, mort=bool(getattr(agent, "_pending_gameover_images", None)))
    _journal(agent, frame, mode, cause)
    part = defaut(frame)
    if mode == "compacte":
        haute, basse = _ent("MULTIMODAL_UPSCALE", 16), _ent("CHRYS_PERC_BASSE", 4)
        if basse < haute:
            part = reduire_part(part, haute, basse)
            for nom in ("_pending_diff_image", "_pending_animation_image"):
                if getattr(agent, nom, None) is not None:
                    setattr(agent, nom, reduire_part(getattr(agent, nom), haute, basse))
    return part
