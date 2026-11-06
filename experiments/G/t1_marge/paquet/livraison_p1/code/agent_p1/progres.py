"""Estimateurs de progrès génériques (écrits pendant le développement, documentés ; aucun nom de jeu, aucune couleur).

Ils ne décident jamais d'une victoire : ils ordonnent l'exploration (meilleur état d'abord). Deux familles de but
fréquentes dans les jeux publics (docs/BIBLIOTHEQUE.md, buts B1 « remplir les cibles / sortie » et « correspondre à un
modèle visible ») sont exprimées sans paramètre de jeu :
  forme   : un objet qui a déjà bougé dans le niveau se rapproche d'un objet immobile de même forme (score 1 = superposé) ;
  modele  : la fenêtre des pixels modifiés depuis le début du niveau ressemble à une fenêtre immobile de même taille
            ailleurs dans l'image (score = part de pixels égaux, 1 = copie exacte).
"""
import numpy as np
from .objets import composantes, forme as forme_cs


def composants(im):
    v, c = np.unique(im, return_counts=True); bg = int(v[np.argmax(c)]); out = []
    for col in v:
        if col == bg:
            continue
        for cs in composantes(im == col):
            if len(cs) < 3:
                continue
            pos, f = forme_cs(cs)
            out.append((int(col), f, pos, len(cs)))
    return out, bg


class Progres:
    def __init__(self, im0):
        self.im0 = im0.copy(); self.positions = {}; self.noter(im0)
        self.mobiles = set()

    def noter(self, im):
        comps, _ = composants(im)
        for col, f, pos, n in comps:
            s = self.positions.setdefault((col, f), set()); s.add(pos)
            if len(s) > 1:
                self.mobiles = getattr(self, 'mobiles', set()); self.mobiles.add(f)
        return comps

    def score_forme(self, comps, im=None):
        """Couleur mobile (ses pixels ont changé depuis le début du niveau) dont la forme initiale a un partenaire
        immobile de même forme et d'autre couleur : score = 1 - distance(coin de la boîte de la couleur mobile,
        coin du partenaire)/128. Robuste aux occultations partielles (on suit la couleur, pas la composante)."""
        if im is None:
            return None
        if not hasattr(self, '_paires'):
            c0, _ = composants(self.im0); self._paires = {}
            grands = {}; nb = {}
            for col, f, pos, n in c0:
                nb[col] = nb.get(col, 0) + 1
                if col not in grands or n > grands[col][2]:
                    grands[col] = (f, pos, n)
            for col, (f, pos, n) in grands.items():
                if nb[col] != 1 or n < 9:
                    continue          # couleur mobile = un objet unique, assez grand pour que sa forme soit informative
                parts = [(c2, p2) for c2, f2, p2, n2 in c0 if f2 == f and c2 != col]
                if parts:
                    self._paires[col] = parts
        best = None
        for col, parts in self._paires.items():
            m_now = im == col; m0 = self.im0 == col
            m_now[0, :] = m_now[-1, :] = False; m_now[:, 0] = m_now[:, -1] = False
            m0[0, :] = m0[-1, :] = False; m0[:, 0] = m0[:, -1] = False
            if not m_now.any():
                continue
            if not (m_now == m0).all():
                self._mob = getattr(self, '_mob', set()); self._mob.add(col)
            if col not in getattr(self, '_mob', set()):
                continue                      # couleur jamais vue bouger
            ys, xs = np.where(m_now); p1 = (int(xs.min()), int(ys.min()))
            for c2, p2 in parts:
                # partenaire immobile : ses pixels initiaux sont toujours de sa couleur (au moins en grande partie)
                d = abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])
                sc = 1.0 - min(d, 128) / 128.0
                best = sc if best is None else max(best, sc)
        return best

    def _paires_modele(self):
        """Au début du niveau : pour chaque objet initial (toile candidate), les fenêtres immobiles de même taille, à au
        moins deux couleurs, qui lui ressemblent en partie (20 à 90 %) : modèles candidats."""
        im0 = self.im0; v, c = np.unique(im0, return_counts=True); bg0 = int(v[np.argmax(c)])
        out = []
        for col in v:
            if col == bg0:
                continue
            for cs in composantes(im0 == col):
                if not (9 <= len(cs) <= 1600):
                    continue
                xs = [x for x, y in cs]; ys = [y for x, y in cs]
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys); h, w = y1 - y0 + 1, x1 - x0 + 1
                if h > 32 or w > 32 or h * w < 9:
                    continue
                C0 = im0[y0:y1 + 1, x0:x1 + 1]; cands = []
                for yy in range(1, 63 - h + 1):
                    for xx in range(1, 63 - w + 1):
                        if not (yy + h <= y0 or yy > y1 or xx + w <= x0 or xx > x1):
                            continue
                        M = im0[yy:yy + h, xx:xx + w]
                        if len(np.unique(M)) < 2:
                            continue
                        s0 = float((M == C0).mean())
                        if 0.2 <= s0 < 0.9:
                            cands.append((s0, xx, yy))
                cands.sort(reverse=True)
                for s0, xx, yy in cands[:8]:
                    out.append(((x0, y0, w, h), (xx, yy), s0))
        return out

    def score_modele(self, im, masque_bord=True):
        """Toile = objet initial dont le contenu a changé sur place ; score = ressemblance actuelle avec un modèle
        immobile de même taille (choisi au début du niveau). 1 = copie exacte."""
        if not hasattr(self, '_pm'):
            self._pm = self._paires_modele()
        best = None
        for (x0, y0, w, h), (xx, yy), s0 in self._pm:
            C = im[y0:y0 + h, x0:x0 + w]; C0 = self.im0[y0:y0 + h, x0:x0 + w]
            ch = C != C0
            if not ch.any():
                continue                                  # toile inchangée
            if not hasattr(self, '_bg0'):
                v, c = np.unique(self.im0, return_counts=True); self._bg0 = int(v[np.argmax(c)])
            if (C[ch] == self._bg0).mean() >= 0.5:
                continue                                  # l'objet est parti (déplacement), il n'a pas été peint
            M = im[yy:yy + h, xx:xx + w]
            if not (M == self.im0[yy:yy + h, xx:xx + w]).all():
                continue                                  # le modèle doit être immobile
            sc = 0.5 + (float((M == C).mean()) - s0) / 2     # gain de ressemblance depuis le début du niveau
            best = sc if best is None else max(best, sc)
        return best

    def evaluer(self, im):
        comps = None
        sf = self.score_forme(comps, im)
        sm = self.score_modele(im)
        # « forme » prime quand un mobile a un partenaire immobile de même forme (la zone modifiée est alors le mobile)
        neutre = 0.5 if getattr(self, '_pm', None) else 0.0   # toile intacte = ni progrès ni recul
        v = sf if sf is not None else (sm if sm is not None else neutre)
        return v, dict(forme=sf, modele=sm)
