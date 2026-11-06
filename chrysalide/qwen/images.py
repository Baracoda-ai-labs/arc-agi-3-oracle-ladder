# SPDX-License-Identifier: MIT-0
"""D (CCM-024-H) : images d'un coup pour `demander_qwen(..., images=…)`, en octets PNG.
`images_coup(avant, apres, predit=None, scene=None)` → [brute, annotée] :
- brute : AVANT | APRÈS côte à côte, couleurs ARC, agrandies (≈ ×10 pour 64 × 64), rien d'autre ;
- annotée : les mêmes panneaux (plus PRÉDIT si donné), coordonnées des cases en marge (x en haut, y à gauche, comme les
  `cases_fausses_x_y_predit_observe` des symptômes), zones qui ont CHANGÉ entourées en jaune (sur APRÈS), zones où la
  prédiction est FAUSSE entourées en rouge (sur APRÈS et PRÉDIT), étiquettes des objets neutres (o1…) de la scène de E
  sur AVANT. Aucune vérité cachée : seulement les images jouées et ce que le moteur prédit.
`images_transition(th, tr, t, scene=None)` : même chose pour le coup t d'une trajectoire et d'une théorie."""
import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PAL = np.array([[255, 255, 255], [204, 204, 204], [153, 153, 153], [102, 102, 102], [51, 51, 51], [0, 0, 0],
                [229, 58, 163], [255, 123, 204], [249, 60, 49], [30, 147, 255], [136, 216, 241], [255, 220, 0],
                [255, 133, 27], [146, 18, 49], [79, 204, 48], [163, 86, 214]], np.uint8)
CHANGE, FAUX = (255, 200, 0), (230, 0, 0)


def _police(t):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", t)
    except OSError:
        return ImageFont.load_default()


def _png(im):
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def _zones(d, x0, y0, k, masque, coul, ep):
    """Un cadre autour de chaque zone (8-connexe) de cases marquées, un peu à l'extérieur : le contenu reste visible."""
    from scipy.ndimage import find_objects, label
    lab, _ = label(masque, structure=np.ones((3, 3)))
    for sl in find_objects(lab):
        d.rectangle([x0 + sl[1].start * k - ep - 1, y0 + sl[0].start * k - ep - 1,
                     x0 + sl[1].stop * k + ep, y0 + sl[0].stop * k + ep], outline=coul, width=ep)


def images_coup(avant, apres, predit=None, scene=None, cible=640):
    a, b = np.asarray(avant) % 16, np.asarray(apres) % 16
    h, w = a.shape
    k = max(1, cible // max(h, w))
    titres = ["AVANT", "APRÈS (observé)"] + (["PRÉDIT (moteur)"] if predit is not None else [])
    grilles = [a, b] + ([np.asarray(predit) % 16] if predit is not None else [])
    ecart = 16
    brute = Image.new("RGB", (2 * w * k + ecart, h * k), (255, 255, 255))
    for i, g in enumerate(grilles[:2]):
        brute.paste(Image.fromarray(PAL[g]).resize((w * k, h * k), Image.NEAREST), (i * (w * k + ecart), 0))
    marge, haut = 28, 26
    pas = 1 if w <= 16 else (4 if w <= 64 else 8)
    W = len(grilles) * (marge + w * k + ecart)
    an = Image.new("RGB", (W, haut + marge + h * k), (255, 255, 255))
    d, pt, pg = ImageDraw.Draw(an), _police(11), _police(16)
    ch = a != b
    faux = (np.asarray(predit) % 16 != b) if predit is not None else np.zeros_like(ch)
    ep = max(2, k // 4)
    for i, (g, titre) in enumerate(zip(grilles, titres, strict=True)):
        x0, y0 = i * (marge + w * k + ecart) + marge, haut + marge
        d.text((x0, 2), titre, fill=(0, 0, 0), font=pg)
        an.paste(Image.fromarray(PAL[g]).resize((w * k, h * k), Image.NEAREST), (x0, y0))
        for x in range(0, w, pas):
            d.text((x0 + x * k + 1, y0 - 14), str(x), fill=(80, 80, 80), font=pt)
        for y in range(0, h, pas):
            d.text((x0 - marge + 2, y0 + y * k), str(y), fill=(80, 80, 80), font=pt)
        if i == 1:
            _zones(d, x0, y0, k, ch & ~faux, CHANGE, ep)
        if i >= 1:
            _zones(d, x0, y0, k, faux, FAUX, ep)
        if i == 0:
            for o in scene or []:
                bx, by, bl, bh = o["boite"]
                d.rectangle([x0 + bx * k, y0 + by * k, x0 + (bx + bl) * k - 1, y0 + (by + bh) * k - 1],
                            outline=(0, 0, 0), width=1)
                d.text((x0 + bx * k + 2, y0 + by * k + 1), str(o["id"]), fill=(0, 0, 0), font=pt,
                       stroke_width=2, stroke_fill=(255, 255, 255))
    return [_png(brute), _png(an)]


def images_transition(th, tr, t, scene=None, cible=640):
    """Coup t de la trajectoire tr : avant / après observés (cases du moteur) et prédiction de la théorie th."""
    predit = None
    if th is not None:
        monde, _ = th.pas(tr.etats[t], tr.actions[t], tr.taille)
        predit = th.rendu(monde, tr.taille, tr.fond)
    return images_coup(tr.cases[t], tr.cases[t + 1], predit, scene, cible)
