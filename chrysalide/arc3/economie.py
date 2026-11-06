# SPDX-License-Identifier: MIT-0
"""D (CW-321 / CW-324, CHRYS_ECONOMIE) : CLASSEMENT DES INDICATEURS DE BORD DEPUIS LES PIXELS, le comportement d'abord.
On ne masque plus l'interface en bloc : chaque indicateur reçoit des étiquettes NON exclusives selon ce qui fait bouger sa
mesure, et des phrases prudentes (ce qui a été vu, jamais ce qui ne l'a pas été).
1. Zones : composantes 8-connexes des cases qui changent PENDANT une vie (transitions sans mort ni changement de niveau),
   et, dans la bande de bord (≤ 3 px), aussi au passage d'une mort ou d'un niveau (vies, progression) ; on garde les zones
   lignes (barres, rangées de pastilles) isolées de leurs voisines à 3 px.
2. Mesure : nombre de cases de LA couleur dont le compte varie le plus dans la zone (longueur de barre, pastilles allumées).
3. Étiquettes, d'après les variations de la mesure :
   - budget : MONOTONE pendant une vie (≥ 3 variations, ≥ 10 % des coups, petits pas inverses ≤ 20 % ; un grand saut
     inverse est une remise ou une recharge, pas une violation) : une barre de 64 px pour
     250 coups ne bouge qu'un coup sur quatre ;
   - recharge : en plus, un vrai saut en sens inverse (≥ 3 pas) pendant une vie ;
   - vies : varie aux morts, toujours dans le même sens (≥ 2 morts vues), presque jamais pendant une vie ;
   - progression : monotone d'un niveau au suivant (≥ 2 changements vus), presque jamais pendant une vie ;
   - autre : sinon.
   Plus « remis à la mort » / « remis au niveau » quand la mesure revient à sa valeur de départ à ces événements, et
   « à zéro : vu suivi d'une mort » seulement si la mesure a atteint son minimum juste avant une mort.
Entrées : images (h × w) et événements des transitions : evenements[t] ∈ {"coup", "mort", "niveau"} pour t → t+1 ;
effets[t] (optionnel) = le coup a-t-il changé le plateau hors indicateurs."""
import numpy as np

BORD = 3


def _composantes(m):
    h, w = m.shape
    vu, out = np.zeros_like(m, bool), []
    for y, x in zip(*np.nonzero(m), strict=True):
        if vu[y, x]:
            continue
        pile, comp = [(y, x)], []
        vu[y, x] = True
        while pile:
            a, b = pile.pop()
            comp.append((a, b))
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    c, d = a + da, b + db
                    if 0 <= c < h and 0 <= d < w and m[c, d] and not vu[c, d]:
                        vu[c, d] = True
                        pile.append((c, d))
        out.append(comp)
    return out


def _runs(idx, ecart=1):
    out, cur = [], []
    for i in idx:
        if cur and i - cur[-1] > ecart + 1:
            out.append(cur)
            cur = []
        cur.append(i)
    if cur:
        out.append(cur)
    return out


def zones(grilles, evenements):
    """Barres et rangées de pastilles : suites (trous ≤ 1) d'au moins 4 cases changées sur une rangée (ou colonne), ISOLÉES
    (les rangées à 3 px de part et d'autre changent peu sur la même étendue) ; deux lignes voisines parallèles qui se
    recouvrent sont fusionnées (barre épaisse). Changements pendant une vie, et aux morts / niveaux dans la bande de bord."""
    gs = [np.asarray(g) for g in grilles]
    h, w = gs[0].shape
    bande = np.zeros((h, w), bool)
    bande[:BORD, :] = bande[-BORD:, :] = bande[:, :BORD] = bande[:, -BORD:] = True
    ch = np.zeros((h, w), bool)
    for t, ev in enumerate(evenements):
        d = gs[t] != gs[t + 1]
        if ev == "coup":
            ch |= d
        elif ev == "mort":  # vies : ne changent qu'aux morts ; on n'en garde que la bande de bord (le niveau repart)
            ch |= d & bande
    cands = []
    for axe, m in (("rangee", ch), ("colonne", ch.T)):
        n = m.shape[0]
        for r in range(n):
            for run in _runs(list(np.nonzero(m[r])[0])):
                a, b = run[0], run[-1]
                if b - a + 1 < 4:
                    continue
                voisins = sum(int(m[q, a:b + 1].sum()) for q in (r - 3, r + 3) if 0 <= q < n)
                if r < BORD or r >= n - BORD or voisins <= 0.25 * (b - a + 1):  # au bord : la mesure tranche
                    cands.append((axe, r, a, b))
    out = []
    for axe, r, a, b in sorted(cands):
        z = next((z for z in out if z["axe"] == axe and r - z["l1"] == 1 and a <= z["b"] and b >= z["a"]), None)
        if z is not None:  # ligne voisine parallèle qui recouvre : barre épaisse
            z.update(l1=r, a=min(a, z["a"]), b=max(b, z["b"]))
            continue
        out.append({"axe": axe, "l0": r, "l1": r, "a": a, "b": b})
    res = []
    for z in out:
        cases = [(r, x) if z["axe"] == "rangee" else (x, r) for r in range(z["l0"], z["l1"] + 1) for x in range(z["a"], z["b"] + 1)]
        ys, xs = [c[0] for c in cases], [c[1] for c in cases]
        res.append({"cases": cases, "boite": (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))), "axe": z["axe"]})
    return res


def mesure(grilles, zone):
    ys, xs = np.array([p[0] for p in zone["cases"]]), np.array([p[1] for p in zone["cases"]])
    vals = np.array([np.asarray(g)[ys, xs] for g in grilles])  # T × n
    couleurs = np.unique(vals)
    comptes = {int(c): (vals == c).sum(1) for c in couleurs}
    c = max(comptes, key=lambda k: (comptes[k].var(), -k))
    return c, comptes[c].astype(int)


def _monotone_aux_niveaux(m, evenements):
    """Valeur de la mesure juste après chaque changement de niveau (et au départ) : strictement monotone."""
    v = [int(m[0])] + [int(m[t + 1]) for t, e in enumerate(evenements) if e == "niveau"]
    d = np.diff(v)
    return bool(len(d)) and ((d > 0).all() or (d < 0).all())


def classer(grilles, evenements, effets=None):
    """→ liste d'indicateurs {boite, couleur, mesure (série), etiquettes, phrases, stats}."""
    out = []
    for z in zones(grilles, evenements):
        c, m = mesure(grilles, z)
        d = np.diff(m)
        coup = np.array([e == "coup" for e in evenements])
        dv, dm, dn = d[coup], d[np.array([e == "mort" for e in evenements])], d[np.array([e == "niveau" for e in evenements])]
        n = max(1, len(dv))
        frac = float((dv != 0).mean()) if len(dv) else 0.0
        neg, pos = int((dv < 0).sum()), int((dv > 0).sum())
        sens = -1 if neg >= pos else 1
        pas = int(np.median(np.abs(dv[np.sign(dv) == sens]))) if (np.sign(dv) == sens).any() else 0
        petits_inverses = int(((np.sign(dv) == -sens) & (np.abs(dv) < 3 * max(1, pas))).sum())  # les grands = remises
        etq, ph = [], []
        if max(neg, pos) >= 3 and petits_inverses <= 0.2 * max(neg, pos) and max(neg, pos) >= 0.1 * n:
            etq.append("budget")
            ph.append(f"monotone pendant une vie ({'baisse' if sens < 0 else 'hausse'} de {pas} case(s) à {round(100 * frac)} % des coups)")
            if effets is not None:
                ef = np.array(effets)[coup]
                if ef.any() and (~ef).any():
                    a, b = float((dv[ef] != 0).mean()), float((dv[~ef] != 0).mean())
                    ph.append(f"varie à {round(100 * a)} % des coups avec effet, {round(100 * b)} % des coups sans effet")
            autre_sens = dv[np.sign(dv) == -sens]
            sauts = int((np.abs(autre_sens) >= 3 * max(1, pas)).sum())
            if sauts:  # recharge = vrai saut en sens inverse (≥ 3 pas), pas un tremblement d'un pixel
                etq.append("recharge")
                ph.append(f"{sauts} saut(s) dans l'autre sens pendant une vie")
        elif frac < 0.1 and len(dm) >= 2 and (dm != 0).mean() >= 0.5 and len(set(np.sign(dm[dm != 0]))) == 1:
            etq.append("vies")
            ph.append(f"varie à {round(100 * (dm != 0).mean())} % des {len(dm)} morts (même sens), {round(100 * frac)} % des coups")
        elif frac < 0.1 and len(dn) >= 2 and _monotone_aux_niveaux(m, evenements):
            etq.append("progression")
            ph.append(f"monotone d'un niveau au suivant ({len(dn)} changements), {round(100 * frac)} % des coups")
        else:
            etq.append("autre")
            ph.append(f"varie à {round(100 * frac)} % des coups")
        for ev, nom in (("mort", "remis à la mort"), ("niveau", "remis au niveau")):
            idx = [t for t, e in enumerate(evenements) if e == ev]
            if idx and all(m[t + 1] == m[0] for t in idx):
                ph.append(nom)
        morts = [t for t, e in enumerate(evenements) if e == "mort"]
        if "budget" in etq and morts and any(m[t] == m.min() for t in morts):
            ph.append("à son extrémité juste avant une mort (vu)")
        out.append({"boite": z["boite"], "couleur": int(c), "etiquettes": etq, "phrases": ph,
                    "stats": {"coups": int(n), "frac": round(frac, 2), "neg": neg, "pos": pos},
                    "mesure": m.tolist()})
    return out
