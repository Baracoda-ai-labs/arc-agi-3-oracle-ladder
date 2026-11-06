# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — perception TEMPORELLE de A (`objets_temps.Pisteur`, CCM-073-A) comme 4ᵉ découpage, SANS oracle :
objet = composantes qui ont déjà bougé ensemble ; classe = ensemble de ses couleurs (mobiles) ou (couleur, forme)
(statiques) ; forme et position en pixels 64 (ou en cases de la vraie grille).
La jauge (masque « barres seules » de B, appris sur la trajectoire) est retirée. Juge : égalité des ensembles d'objets.
Complétion amodale (sans regard vers le futur) : une case masquée par un objet déjà vu bouger garde la dernière couleur
statique vue ; le décor statique est redécoupé en composantes par couleur (le sol ne « change » plus sous le joueur)."""
import os

import numpy as np
from arcengine.enums import GameAction, GameState

from chrysalide.arc3.logique.faits import apparier, echelle, masque_cases, objets
from chrysalide.arc3.logique.jeux import en_pixels, environnement, jouer_action
from chrysalide.arc3.logique.theorie import cle_objet
from chrysalide.arc3.objets_temps import Pisteur

CLASSES = {}


def etat_temps(objets, g, hud):
    g = np.asarray(g)
    out = []
    for px in objets.values():
        px = {(y, x) for y, x in px if (y, x) not in hud}
        if not px:
            continue
        coul = tuple(sorted({int(g[y, x]) for y, x in px}))
        c = CLASSES.setdefault(coul, len(CLASSES) + 200)
        y0, x0 = min(y for y, _ in px), min(x for _, x in px)
        out.append((c, frozenset((x - x0, y - y0) for y, x in px), x0, y0))
    return tuple(sorted(out, key=cle_objet))


def masque_jauge(grilles):
    """Masque de B (barres de jauge), mais une ligne ou colonne n'est gardée que si elle se comporte comme une jauge
    (monotone, CW-141.3) : ls20 niveau 3, le couloir du joueur (colonne 1 de la grille) était pris pour une barre."""
    m = masque_cases(grilles, 1, 0, 0)
    if not m:
        return m
    g = np.asarray(grilles)
    out = set()
    for axe in (0, 1):
        lignes = {}
        for r, c in m:
            lignes.setdefault(r if axe == 0 else c, set()).add((r, c))
        for i, cs in lignes.items():
            seq = g[:, i, :] if axe == 0 else g[:, :, i]
            if len(cs) >= (g.shape[2] if axe == 0 else g.shape[1]) and monotone(seq, min_var=5):  # une jauge
                # varie souvent ; un couloir où passe le joueur ne change de compte qu'à l'entrée et à la sortie
                out |= cs
    reste = {rc for rc in m if not any(rc[0] == r for r, _ in out) and not any(rc[1] == c for _, c in out)}
    lignes_entieres = {r for r, _ in m} | {c for _, c in m}
    return frozenset(out | (reste if len(lignes_entieres) == 0 else set()))


class TrajTemps:
    """Même interface que faits.Trajectoire, en pixels 64 (s = 1)."""

    def __init__(self, objets_pis, grilles, actions, s=1, ox=0, oy=0):
        h, w = np.asarray(grilles[0]).shape
        self.s, self.ox, self.oy, self.taille, self.fond = s, ox, oy, (w, h), -1
        self.exclues = frozenset(etendre_barres(masque_jauge(grilles) | bande_jauge(grilles, actions=actions), grilles)
                                 if len(grilles) > 1 else ())
        self.atomiques = frozenset()
        bruts = [etat_temps(o, g, self.exclues) for o, g in zip(objets_pis, grilles, strict=True)]
        self.etats = completer(bruts, grilles, self.exclues)
        self.cases = [np.asarray(g) for g in grilles]
        self.actions = [self.action_cases(a) for a in actions]

    def action_cases(self, a):
        if isinstance(a, tuple) and a[0] == "clic" and self.s > 1:
            return ("clic", (a[1] - self.ox) // self.s, (a[2] - self.oy) // self.s)
        return a


def monotone(seq, part=0.8, min_var=1):
    """Une suite de vecteurs (ligne ou colonne au fil des coups) se comporte comme une jauge : le nombre de pixels
    d'au moins une couleur varie toujours dans le même sens (≥ `part` des variations ; les remises à zéro sont tolérées)."""
    seq = np.asarray(seq)
    for v in np.unique(seq):
        n = (seq == v).sum(axis=1)
        dn = np.sign(np.diff(n))
        dn = dn[dn != 0]
        if len(dn) >= min_var and max((dn > 0).mean(), (dn < 0).mean()) >= part:
            return True
    return False


def clic_dans(actions, grilles, r=None, c=None):
    """Un clic tombe sur la ligne r (ou la colonne c) et la change : la zone répond aux actions."""
    for t, a in enumerate(actions):
        if isinstance(a, tuple) and a[0] == "clic" and t + 1 < len(grilles):
            x, y = a[1], a[2]
            if (r is not None and abs(y - r) <= 1 and (grilles[t][r] != grilles[t + 1][r]).any()) or \
               (c is not None and abs(x - c) <= 1 and (grilles[t][:, c] != grilles[t + 1][:, c]).any()):
                return True
    return False


def bande_jauge(grilles, bande=None, freq=0.3, actions=None):
    """Jauge : ligne ou colonne de la bande de bord qui change à au moins `freq` des coups (25/25 jeux en ont une).
    Avec `actions` (règle CW-141.3) : n'est masquée que si elle se comporte comme une jauge (monotone) et ne répond pas
    à un clic ; sinon c'est un canevas actif (lf52, bp35 : monde dessiné dans l'interface) et il reste perçu."""
    g = np.asarray(grilles)
    d = g[1:] != g[:-1]
    h, w = g.shape[1], g.shape[2]
    bande = bande or max(1, min(h, w) // 16)  # 4 pixels sur 64
    lignes = [r for r in range(h) if (r < bande or r >= h - bande) and d[:, r, :].any(axis=1).mean() >= freq]
    cols = [c for c in range(w) if (c < bande or c >= w - bande) and d[:, :, c].any(axis=1).mean() >= freq]
    if actions is not None:
        lignes = [r for r in lignes if monotone(g[:, r, :]) and not clic_dans(actions, g, r=r)]
        cols = [c for c in cols if monotone(g[:, :, c]) and not clic_dans(actions, g, c=c)]
    return {(r, j) for r in lignes for j in range(w)} | {(j, c) for c in cols for j in range(h)}


def canevas_actifs(grilles, actions, bande=None, freq=0.3):
    """Lignes/colonnes d'interface qui changent souvent mais ne sont PAS des jauges → à traiter comme canevas."""
    return bande_jauge(grilles, bande, freq) - bande_jauge(grilles, bande, freq, actions)


def etendre_barres(hud, grilles):
    """Une barre de jauge masquée sur des lignes (ou colonnes) entières est prolongée aux lignes voisines qui ont changé
    (barres de 3 pixels dont le masque ne retient que 2 lignes)."""
    hud = set(hud)
    g = np.asarray(grilles)
    change = (g[1:] != g[:-1]).any(axis=0)
    for axe in (0, 1):
        n = g.shape[1 + axe]  # axe 0 : lignes (hauteur), axe 1 : colonnes (largeur)
        pleines = {i for i in range(n) if all(((i, j) if axe == 0 else (j, i)) in hud for j in range(g.shape[2 - axe]))}
        a_voir = sorted({i + d for i in pleines for d in (-1, 1)} - pleines)
        while a_voir:
            i = a_voir.pop()
            if 0 <= i < n and (change[i, :] if axe == 0 else change[:, i]).any():
                hud |= {(i, j) if axe == 0 else (j, i) for j in range(g.shape[2 - axe])}
                pleines.add(i)
                a_voir += [k for k in (i - 1, i + 1) if k not in pleines]
    return hud


def completer(bruts, grilles, hud):
    """Objets mobiles (classes déjà vues bouger, d'après le passé seulement) gardés tels quels ; décor = composantes par
    couleur d'une image où chaque case masquée par un mobile reprend la dernière couleur statique vue."""
    mobiles, mem, out = set(), {}, []
    for t, (e, g) in enumerate(zip(bruts, grilles, strict=True)):
        if t > 0:
            paires, _ = apparier(bruts[t - 1], e)
            mobiles |= {bruts[t - 1][i][0] for i, j in paires
                        if j is not None and (e[j][2], e[j][3]) != (bruts[t - 1][i][2], bruts[t - 1][i][3])}
        g = np.asarray(g)
        mob = [o for o in e if o[0] in mobiles]
        px_mob = {(o[3] + dy, o[2] + dx) for o in mob for dx, dy in o[1]}
        decor = np.full(g.shape, -1, dtype=int)
        for y in range(g.shape[0]):
            for x in range(g.shape[1]):
                if (y, x) in hud:
                    continue
                if (y, x) in px_mob:
                    decor[y, x] = mem.get((y, x), -1)
                else:
                    decor[y, x] = mem[(y, x)] = int(g[y, x])
        fond = int(np.bincount(decor[decor >= 0].ravel()).argmax()) if (decor >= 0).any() else -1
        # statiques : classe = (couleur, forme normalisée) — la porte n'est pas un mur (CCM-077-A) ; tuiles répétées = 1 classe
        stat = [(CLASSES.setdefault(("statique", o[0], o[1]), len(CLASSES) + 200), o[1], o[2], o[3]) for o in objets(decor, fond)
                if o[0] >= 0]
        out.append(tuple(sorted(mob + stat, key=cle_objet)))
    return out


MOTIFS = {}


def cases_motifs(g, s, ox, oy):
    """Vraie grille SANS perte d'identité : chaque case = sa couleur si le bloc s×s est uni, sinon l'identifiant (≥ 100)
    de son motif de pixels. Un petit sprite à motif (modificateur de ls20) ne se confond plus avec le sol qui l'entoure."""
    g = np.asarray(g)
    ny, nx = (64 - oy) // s, (64 - ox) // s
    b = g[oy:oy + ny * s, ox:ox + nx * s].reshape(ny, s, nx, s).transpose(0, 2, 1, 3)
    out = np.empty((ny, nx), dtype=int)
    for r in range(ny):
        for c in range(nx):
            blk = b[r, c]
            out[r, c] = int(blk[0, 0]) if (blk == blk[0, 0]).all() else MOTIFS.setdefault(blk.tobytes(), len(MOTIFS) + 100)
    return out


def traj_temps(grilles, actions, grille=False, **opts):
    """TrajTemps depuis des images déjà jouées (format de jeux.segments) : le Pisteur les lit dans l'ordre (passé seul).
    `opts` : options du Pisteur (`englobe`, `contact` : découpages concurrents, CCM-047-C)."""
    e = echelle([grilles[0]]) if grille else (1, 0, 0)
    vues = [cases_motifs(g, *e) if grille else np.asarray(g) for g in grilles]
    if os.environ.get("CHRYS_CHEVAUCHE", "1") == "1":  # identité par chevauchement, défaut de C (CCM-053-C, accord A
        opts = {"chevauche": True, **opts}  # CCM-146-A) ; CHRYS_CHEVAUCHE=0 = contrôle F-C2 (Pisteur seul)
    pis = Pisteur(**opts)
    return TrajTemps([pis.observer(v) for v in vues], vues, list(actions), *e)


def segments_temps(gid, dossier, actions, grille=False):
    """Comme jeux.segments, avec la perception temporelle ; le Pisteur est remis à zéro à chaque niveau ou vie.
    grille=True : le Pisteur travaille sur la vraie grille (échelle détectée sur la 1ʳᵉ image du segment), pas en pixels."""
    env = environnement(gid, dossier)
    f = env.reset()

    def debut(g0):
        e = echelle([g0]) if grille else (1, 0, 0)
        return Pisteur(), e

    def vue(g, e):
        return cases_motifs(g, *e) if grille else np.asarray(g)

    pis, ech = debut(f.frame[-1])
    g = vue(f.frame[-1], ech)
    objs, gs, acts, segs = [pis.observer(g)], [g], [], []
    for a in map(en_pixels, actions):
        n0 = f.levels_completed
        f = jouer_action(env, a)
        issue = ("gagne" if f.state == GameState.WIN else "perdu" if f.state == GameState.GAME_OVER
                 else "niveau" if f.levels_completed > n0 else None)
        if issue:
            segs.append({"traj": TrajTemps(objs, gs, acts, *ech), "finale": a, "issue": issue, "niveau": n0})
            if issue == "gagne":
                return segs
            if issue == "perdu":
                f = env.step(GameAction.RESET)
            pis, ech = debut(f.frame[-1])
            g = vue(f.frame[-1], ech)
            objs, gs, acts = [pis.observer(g)], [g], []
        else:
            g = vue(f.frame[-1], ech)
            objs.append(pis.observer(g))
            gs.append(g)
            acts.append(a)
    segs.append({"traj": TrajTemps(objs, gs, acts, *ech), "finale": None, "issue": None, "niveau": f.levels_completed})
    return segs
