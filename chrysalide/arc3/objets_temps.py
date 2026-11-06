# SPDX-License-Identifier: MIT-0
"""CW-082 : perception TEMPORELLE sans oracle. Un objet = union des composantes (couleur, 4-connexité, image 64×64) qui
ont DÉJÀ bougé ensemble (même déplacement, contiguës) à un moment de la partie ; les composantes jamais déplacées restent
des objets statiques. Identité suivie d'un coup à l'autre (`rendu.suivre`) ; union RÉVISABLE (défaite à la séparation).
Évaluation (bancs seulement) : distance à la perception ORACLE du moteur (sprites visibles), par IoU de pixels."""
from collections import Counter

import numpy as np

from chrysalide.arc3.rendu import sprites, suivre


class Pisteur:
    """revisable=True (défaut, correctif demandé par C sur ar25) : une union est DÉFAITE dès que ses membres présents
    bougent différemment (déplacements distincts au même coup) ; ils repartent chacun dans son groupe. revisable=False :
    union définitive (première version, gardée pour comparaison)."""

    def __init__(self, revisable=True, contact=False, part_max=0.02, englobe=False, part_bord=0.75, chevauche=False):
        self.groupe, self.prec, self.n, self.revisable, self.separes = {}, None, 0, revisable, set()
        # contact=True (C, CW-165, correction 1) : deux composantes contiguës JAMAIS vues séparées = un même objet
        # (sprite multicolore immobile), tant que l'objet reste petit (≤ part_max de l'image) ; révisable.
        self.contact, self.part_max, self.colles, self.apart = contact, part_max, set(), set()
        # englobe=True (C, correction 1 bis) : une composante entourée (≥ part_bord de son pourtour) par une autre fait
        # partie du même objet (anneau + cœur, sc25), tant que l'objet reste petit ; recalculé à chaque image.
        self.englobe, self.part_bord, self.entoure = englobe, part_bord, set()
        # chevauche=True (C, identité, CW-165 n° 3) : une composante non appariée (forme changée : animation, rotation,
        # occultation) reprend la piste d'une composante disparue de MÊME couleur qui la chevauche ou la touche.
        self.chevauche = chevauche

    def _racine(self, p):
        return self.groupe[p]

    def _neuve(self):
        self.n += 1
        self.groupe[self.n] = self.n
        return self.n

    def _scinder(self, depl):
        """depl : {piste: (dy, dx)} des pistes appariées à ce coup. Un groupe dont les membres présents ont des
        déplacements différents est scindé selon le déplacement."""
        par_groupe = {}
        for p, d in depl.items():
            par_groupe.setdefault(self.groupe[p], {}).setdefault(d, []).append(p)
        # contre-preuve : deux pistes qui bougent différemment au même coup ne seront plus jamais réunies
        items = list(depl.items())
        for i, (p, d) in enumerate(items):
            for q, e in items[i + 1:]:
                if d != e and self.groupe[p] == self.groupe[q]:
                    self.separes.add(frozenset((p, q)))
        for parts in par_groupe.values():
            if len(parts) <= 1:
                continue
            for k, (_d, membres) in enumerate(sorted(parts.items())):
                if k == 0:
                    continue  # la première part garde l'identifiant du groupe
                self.n += 1
                for q in membres:
                    self.groupe[q] = self.n

    def observer(self, g):
        g = np.asarray(g)
        fond = Counter(g.ravel().tolist()).most_common(1)[0][0]
        r = {"sprites": sprites(g, fond)}
        pistes = {}
        if self.prec is None:
            for s in r["sprites"]:
                pistes[s[0]] = self._neuve()
        else:
            m = suivre(self.prec[0], r)
            depl = {}
            for i0, (i1, dy, dx) in m["appariement"].items():
                pistes[i1] = self.prec[1][i0]
                depl[pistes[i1]] = (dy, dx)
            if self.chevauche:
                self._reprendre(self.prec, r, pistes, m)
            for s in r["sprites"]:
                if s[0] not in pistes:
                    pistes[s[0]] = self._neuve()
            if self.revisable:
                self._scinder(depl)
            for groupe in m["objets"]:  # composantes déplacées ensemble et contiguës : même objet (révisable)
                ids = [pistes[i] for i, _ in groupe]
                cible = self.groupe[ids[0]]
                for p in ids[1:]:
                    gp = self.groupe[p]
                    if gp == cible:
                        continue
                    membres_c = [q for q, gq in self.groupe.items() if gq == cible]
                    membres_p = [q for q, gq in self.groupe.items() if gq == gp]
                    if self.revisable and any(frozenset((a, b)) in self.separes for a in membres_c for b in membres_p):
                        continue  # déjà vus se séparer : pas de nouvelle union
                    for q in membres_p:
                        self.groupe[q] = cible
        if self.contact or self.englobe:
            self._contacts(r, pistes, g.shape)
        self.prec = (r, pistes)
        return self.objets()

    @staticmethod
    def _reprendre(prec, r, pistes, m):
        """Apparie les composantes nouvelles aux disparues de même couleur, par chevauchement (ou contact) de pixels."""
        r0, p0 = prec
        disp = [s for s in r0["sprites"] if s[0] in set(m["disparus"])]
        px0 = {s[0]: {(s[4] + a, s[3] + b) for a, b in s[2]} for s in disp}
        pris = set()
        for s in sorted((s for s in r["sprites"] if s[0] not in pistes), key=lambda s: -len(s[2])):
            px = {(s[4] + a, s[3] + b) for a, b in s[2]}
            autour = px | {(y + dy, x + dx) for y, x in px for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))}
            cands = [(len(px & px0[d[0]]), len(autour & px0[d[0]]), d[0]) for d in disp
                     if d[1] == s[1] and d[0] not in pris and autour & px0[d[0]]]
            if cands:
                _, _, d = max(cands)
                pris.add(d)
                pistes[s[0]] = p0[d]

    def _contacts(self, r, pistes, forme):
        """Met à jour les paires de pistes collées depuis qu'on les voit ensemble (`colles`) et celles déjà vues séparées."""
        ou = {}
        for s in r["sprites"]:
            for a, b in s[2]:
                ou[(s[4] + a, s[3] + b)] = pistes[s[0]]
        adj, bord = set(), {}
        h, w = forme
        for (y, x), p in ou.items():
            for q in (ou.get((y + 1, x)), ou.get((y, x + 1))):
                if q is not None and q != p:
                    adj.add(frozenset((p, q)))
            for v in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                q = ou.get(v) if 0 <= v[0] < h and 0 <= v[1] < w else None
                if q != p:
                    bord.setdefault(p, Counter())[q] += 1  # None : fond ou bord de l'image
        self.entoure = set()
        for p, c in bord.items():
            q, n = max(((q, n) for q, n in c.items() if q is not None), key=lambda x: x[1], default=(None, 0))
            if q is not None and n >= self.part_bord * sum(c.values()):
                self.entoure.add((p, q))
        presents = set(pistes.values())
        avant = set(self.prec[1].values()) if self.prec else set()
        for paire in list(self.colles):
            if paire <= presents and paire not in adj:
                self.colles.discard(paire)
                self.apart.add(paire)
        for paire in adj - self.colles - self.apart:
            if paire <= avant:  # présentes toutes deux avant, et pas collées : elles étaient séparées
                self.apart.add(paire)
            else:
                self.colles.add(paire)
        self.taille_image = forme[0] * forme[1]

    def objets(self):
        """Objets courants : {groupe: set((y, x))} en pixels 64."""
        r, pistes = self.prec
        out = {}
        for s in r["sprites"]:
            out.setdefault(self._racine(pistes[s[0]]), set()).update((s[4] + a, s[3] + b) for a, b in s[2])
        if not (self.contact or self.englobe):
            return out
        presents = set(pistes.values())
        parent = {g: g for g in out}

        def rac(g):
            while parent[g] != g:
                g = parent[g]
            return g
        cap = self.part_max * self.taille_image
        paires = (list(self.colles) if self.contact else []) + ([frozenset(e) for e in self.entoure] if self.englobe else [])
        for paire in paires:
            if not paire <= presents:
                continue
            p, q = (rac(self._racine(x)) for x in paire)
            if p != q and len(out[p]) + len(out[q]) <= cap:
                parent[q] = p
                out[p] = out[p] | out.pop(q)
        return out


def pixels_oracle(om, g, seulement=None):
    """Pixels 64 VISIBLES de chaque sprite du moteur (couleur égale à l'image), d'après objets_moteur()."""
    k = om["echelle"]
    y0, x0 = om["cadre"][:2]
    cx, cy = om.get("camera_xy", (0, 0))
    out = []
    for s in om["sprites"]:
        if seulement is not None and s.get("id") not in seulement:
            continue
        px = np.asarray(s["pixels"])
        cases = set()
        for a in range(px.shape[0]):
            for b in range(px.shape[1]):
                c = px[a, b]
                if c < 0:
                    continue
                for da in range(k):
                    for db in range(k):
                        y, x = y0 + (s["y"] - cy + a) * k + da, x0 + (s["x"] - cx + b) * k + db
                        if 0 <= y < 64 and 0 <= x < 64 and g[y, x] == c:
                            cases.add((y, x))
        if cases:
            out.append(cases)
    return out


def distance(objets, vrais):
    """Pour chaque sprite vrai : meilleur IoU avec un objet perçu, et nombre d'objets perçus qui le recouvrent."""
    perc = list(objets.values())
    ious, morceaux = [], []
    for v in vrais:
        best = max((len(v & o) / len(v | o) for o in perc), default=0.0)
        ious.append(best)
        morceaux.append(sum(1 for o in perc if len(v & o) >= 0.5 * len(o)))
    return {"iou_moy": float(np.mean(ious)) if ious else None, "part_iou_09": float(np.mean([x >= 0.9 for x in ious])) if ious else None,
            "morceaux_moy": float(np.mean(morceaux)) if morceaux else None, "sprites": len(vrais)}
