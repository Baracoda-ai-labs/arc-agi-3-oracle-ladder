# SPDX-License-Identifier: MIT-0
"""CW-031 (idée de Thomas) : perception adaptative. Haute résolution (image agrandie) tant qu'on découvre ; représentation
COMPACTE (texte : fond + objets, puis seulement le diff d'objets depuis le tour précédent) une fois le niveau calme ;
retour automatique à la haute résolution sur nouveau niveau, surprise (issue ≠ prévision du graphe) ou stagnation.
La description compacte est SANS PERTE : `decompacter(compacter(g)) == g` (contrôle du banc). Un objet = composante
connexe d'une couleur (duck.segmentation) ; rectangle plein -> « c r,c HxW », sinon on ajoute son masque ligne par ligne."""
from collections import Counter

from chrysalide.arc3.duck import segmentation


def objets_texte(g):
    """Fond, taille et une ligne par objet, triées par position (ordre stable d'un tour à l'autre)."""
    h, w = len(g), len(g[0])
    fond = Counter(v for r in g for v in r).most_common(1)[0][0]
    lignes = []
    for o in sorted(segmentation(g), key=lambda o: (o["bbox"][0], o["bbox"][1], o["color"])):
        r0, c0, r1, c1 = o["bbox"]
        hh, ww = r1 - r0 + 1, c1 - c0 + 1
        txt = f"{o['color']:x} {r0},{c0} {hh}x{ww}"
        if o["size"] != hh * ww:
            cel = set(o["cells"])
            txt += " " + "/".join("".join("#" if (r, c) in cel else "." for c in range(c0, c1 + 1))
                                  for r in range(r0, r1 + 1))
        lignes.append(txt)
    return f"fond {fond:x} {h}x{w}", lignes


def compacter(g):
    tete, lignes = objets_texte(g)
    return "\n".join([tete, *lignes])


def decompacter(txt):
    tete, *lignes = txt.split("\n")
    _, fond, dims = tete.split(" ")
    h, w = (int(x) for x in dims.split("x"))
    g = [[int(fond, 16)] * w for _ in range(h)]
    for ligne in lignes:
        morceaux = ligne.split(" ")
        c = int(morceaux[0], 16)
        r0, c0 = (int(x) for x in morceaux[1].split(","))
        hh, ww = (int(x) for x in morceaux[2].split("x"))
        masque = morceaux[3].split("/") if len(morceaux) > 3 else ["#" * ww] * hh
        for i, rang in enumerate(masque):
            for j, ch in enumerate(rang):
                if ch == "#":
                    g[r0 + i][c0 + j] = c
    return g


def diff(avant, apres):
    """Diff d'objets entre deux descriptions compactes : « - ligne » disparus, « + ligne » apparus (ou complet si le fond change)."""
    ta, la = avant.split("\n", 1)[0], set(avant.split("\n")[1:])
    tb, lb = apres.split("\n", 1)[0], apres.split("\n")[1:]
    if ta != tb:
        return apres
    sb = set(lb)
    return "\n".join([f"- {x}" for x in sorted(la - sb)] + [f"+ {x}" for x in lb if x not in la])


def appliquer(avant, d):
    """Reconstruit la description compacte d'après à partir de celle d'avant et du diff (contrôle sans perte)."""
    if d.startswith("fond "):
        return d
    tete, *lignes = avant.split("\n")
    moins = {x[2:] for x in d.split("\n") if x.startswith("- ")}
    plus = [x[2:] for x in d.split("\n") if x.startswith("+ ")]
    garde = [x for x in lignes if x not in moins] + plus
    # même ordre que objets_texte : position puis couleur
    def rang(x):
        m = x.split(" ")
        r, c = (int(v) for v in m[1].split(","))
        return (r, c, int(m[0], 16))
    return "\n".join([tete, *sorted(garde, key=rang)])


class Routeur:
    """Choisit la perception du tour : 'haute' (découverte) ou 'compacte'. Haute au premier tour, sur nouveau niveau,
    après une surprise, ou après `stagnation` tours sans état nouveau ; compacte après `calme` tours haute sans surprise."""

    def __init__(self, calme=2, stagnation=5):
        self.calme, self.stagnation = calme, stagnation
        self.niveau, self.tours_calmes, self.sans_neuf, self.mode = None, 0, 0, "haute"

    def tour(self, niveau, surprise=False, etat_neuf=True):
        """Appelé au début de chaque tour avec ce que le tour précédent a produit. Rend (mode, cause)."""
        self.sans_neuf = 0 if etat_neuf else self.sans_neuf + 1
        cause = None
        if niveau != self.niveau:
            cause = "debut" if self.niveau is None else "niveau"
        elif surprise:
            cause = "surprise"
        elif self.sans_neuf >= self.stagnation:
            cause, self.sans_neuf = "stagnation", 0
        self.niveau = niveau
        if cause:
            self.mode, self.tours_calmes = "haute", 0
        elif self.mode == "haute":
            self.tours_calmes += 1
            if self.tours_calmes >= self.calme:
                self.mode = "compacte"
        return self.mode, cause
