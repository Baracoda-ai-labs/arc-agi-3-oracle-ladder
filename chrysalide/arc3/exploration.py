# SPDX-License-Identifier: MIT-0
"""Exploration ciblée (CW-226 pari 1, CW-234) : le coup joué quand le moteur n'a pas de plan, à la place du hasard.
Deux étages, sans aucun identifiant de jeu :
  1. NOUVEAUTÉ (pris chez Franzen : ordre d'essai et coups sans effet) : dans l'image exacte courante, on préfère une action
     jamais essayée ici ; une action déjà vue SANS EFFET dans cette image n'est plus rejouée ; les clics visent le centre
     des objets (composantes), pas des pixels au hasard.
  2. DÉPARTAGE (si `departage`) : tous les `periode` coups, l'induction rend jusqu'à k théories aussi cohérentes que la
     meilleure (`induire_k`) ; on joue l'action dont les prédictions DIFFÈRENT le plus entre théories (le coup qui
     départage : case franchissable, objet poussable, interaction, cible ou décor). À égalité : nouveauté, puis hasard.
  3. GROUPE (si `groupe`, v2 d'après OPINE-World, arXiv 2607.01531) : les coups passés sont rangés par groupe
     j = (classe visée, action, contexte) — flèche : (classe du mobile, action, classe de la case visée ou « fond »/« bord ») ;
     clic : (classe de l'objet cliqué, « clic », None) — avec l'issue observée (déplacé, bloqué, autre, rien). Priorité d'un
     groupe = 1 − (effectif de l'issue la plus fréquente) / (1 + n_j) ; on joue l'action de plus forte priorité.
Un coup = dict d'action de l'agent ({"action": "UP"} ou {"action": "MOUSE", "row", "col"})."""
import random
import time
from collections import Counter

import numpy as np

NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE"}
DIRS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}


def cibles_clic(g):
    """Centre (case la plus centrale) de chaque composante hors fond : (ligne, colonne) en pixels."""
    from chrysalide.arc3.rendu import sprites
    g = np.asarray(g)
    fond = int(np.bincount(g.ravel()).argmax())
    out = set()
    for s in sprites(g, fond):
        cases = [(s[4] + a, s[3] + b) for a, b in s[2]]
        my, mx = sum(y for y, _ in cases) / len(cases), sum(x for _, x in cases) / len(cases)
        out.add(min(cases, key=lambda p: (p[0] - my) ** 2 + (p[1] - mx) ** 2))
    return sorted(out)


class Explorateur:
    def __init__(self, graine=0, departage=False, periode=8, k=6, limite_s=10.0, groupe=False):
        self.groupe, self.issues, self.bouge = groupe, {}, Counter()  # issues[j] = Counter(issue) ; bouge = classes mobiles
        self.rnd, self.departage, self.periode, self.k, self.limite_s = random.Random(graine), departage, periode, k, limite_s
        self.essais = Counter()  # (image, action) → nombre d'essais
        self.sans_effet = set()  # (image, action) déjà vus sans effet
        self.n, self.ths, self.m = 0, [], Counter()

    def noter(self, g0, coup, g1):
        """À appeler après CHAQUE coup joué (par n'importe quel joueur) : mémoire des essais et des coups sans effet."""
        cle = (np.asarray(g0).tobytes(), self._cle(coup))
        self.essais[cle] += 1
        if np.array_equal(np.asarray(g0), np.asarray(g1)):
            self.sans_effet.add(cle)
        if self.groupe:
            try:
                self._noter_groupe(g0, coup, g1)
            except Exception:  # noqa: BLE001 — perception impossible : le coup ne compte pas dans les groupes
                self.m["groupe_erreur"] += 1

    @staticmethod
    def _cle(c):
        return (c["action"], c.get("row"), c.get("col"))

    def candidats(self, g, dispo):
        ids = {int(getattr(a, "value", a)) for a in dispo} or {1, 2, 3, 4}
        out = [{"action": NOMS[i]} for i in sorted(ids) if i in NOMS]
        if 6 in ids:
            out += [{"action": "MOUSE", "row": int(y), "col": int(x)} for y, x in cibles_clic(g)]
        return out or [{"action": "UP"}]

    def coup(self, g, dispo, hist=None):
        """g = image courante ; dispo = actions disponibles ; hist = {"grilles", "lots"} du niveau courant (départage)."""
        self.n += 1
        im = np.asarray(g).tobytes()
        cands = [c for c in self.candidats(g, dispo) if (im, self._cle(c)) not in self.sans_effet] or self.candidats(g, dispo)
        if self.departage and hist and len(hist.get("lots", [])) >= 5:
            c = self._departager(cands, hist)
            if c is not None:
                self.m["departage"] += 1
                return c
        if self.groupe:
            c = self._par_groupe(g, cands)
            if c is not None:
                return c
        peu = min(self.essais[(im, self._cle(c))] for c in cands)
        self.m["nouveaute" if peu == 0 else "reprise"] += 1
        return self.rnd.choice([c for c in cands if self.essais[(im, self._cle(c))] == peu])

    def _departager(self, cands, hist):
        from chrysalide.arc3.logique.faits import Trajectoire
        from chrysalide.arc3.logique.induction import induire_k
        from chrysalide.arc3.moteur import _code_c
        acts = [_code_c(lot["actions"][0]) if len(lot["actions"]) == 1 else None for lot in hist["lots"]]
        if any(a is None for a in acts):
            return None
        try:
            tr = Trajectoire(hist["grilles"], acts)
            if not self.ths or self.n % self.periode == 0:
                t0 = time.process_time()
                self.ths = [th for th, _ in induire_k([(tr, None, None)], k=self.k, limite_s=self.limite_s)]
                self.m["cpu_departage_s"] += round(time.process_time() - t0, 2)
            if len(self.ths) < 2:
                return None
            monde, meilleur, score = tr.etats[-1], None, 1
            for c in cands:
                a = _code_c(c)
                if a is None or isinstance(a, tuple) and not all(th.motif for th in self.ths):
                    continue
                preds = {frozenset(th.pas(monde, a, tr.taille)[0]) for th in self.ths}
                if len(preds) > score:
                    meilleur, score = c, len(preds)
            return meilleur
        except Exception:  # noqa: BLE001 — induction impossible : on retombe sur la nouveauté
            self.m["departage_erreur"] += 1
            return None


    # ---------------------------------------------------------------- v2 : priorité par groupe (OPINE-World)
    DIRS = DIRS

    def _etats(self, g0, g1=None):
        from chrysalide.arc3.logique.faits import Trajectoire
        gs = [np.asarray(g0).tolist()] + ([np.asarray(g1).tolist()] if g1 is not None else [])
        tr = Trajectoire(gs, [1] * (len(gs) - 1))
        return tr

    def _groupe(self, tr, etat, coup):
        from chrysalide.arc3.logique.theorie import cells
        a = coup["action"]
        if a == "MOUSE":
            x, y = (coup["col"] - tr.ox) // tr.s, (coup["row"] - tr.oy) // tr.s
            vise = next((o[0] for o in etat if (x, y) in set(cells(o))), "fond")
            return (vise, "clic", None)
        mob = self.bouge.most_common(1)[0][0] if self.bouge else None
        if a not in self.DIRS or mob is None:
            return (mob, a, None)
        dx, dy = self.DIRS[a]
        occ = {c: o[0] for o in etat for c in cells(o)}
        w, h = tr.taille
        ctx = set()
        for o in etat:
            if o[0] != mob:
                continue
            for (cx, cy) in cells(o):
                n = (cx + dx, cy + dy)
                if not (0 <= n[0] < w and 0 <= n[1] < h):
                    ctx.add("bord")
                elif occ.get(n, "fond") != mob:
                    ctx.add(occ.get(n, "fond"))
        return (mob, a, tuple(sorted(map(str, ctx))))

    def _noter_groupe(self, g0, coup, g1):
        from chrysalide.arc3.logique.faits import apparier
        tr = self._etats(g0, g1)
        e0, e1 = tr.etats
        paires, nouveaux = apparier(e0, e1)
        bouges = {e0[i][0] for i, j in paires if j is not None and (e1[j][2], e1[j][3]) != (e0[i][2], e0[i][3])}
        if coup["action"] in self.DIRS:
            self.bouge.update(bouges)
        j = self._groupe(tr, e0, coup)
        autre = bool(nouveaux) or any(j2 is None or e1[j2][0] != e0[i][0] for i, j2 in paires)
        issue = "autre" if autre else ("deplace" if bouges else "rien")
        self.issues.setdefault(j, Counter())[issue] += 1

    def _par_groupe(self, g, cands):
        tr = self._etats(g)
        etat = tr.etats[0]
        prio = []
        for c in cands:
            j = self._groupe(tr, etat, c)
            cnt = self.issues.get(j, Counter())
            n = sum(cnt.values())
            prio.append((1 - (max(cnt.values()) if cnt else 0) / (1 + n), c))
        haut = max(p for p, _ in prio)
        meilleurs = [c for p, c in prio if p == haut]
        self.m["groupe"] += 1
        self.m["groupe_prio_1"] += haut == 1
        return self.rnd.choice(meilleurs)


def consensus(hist, coup, k=4, limite_s=10.0):
    """CW-251 AGIR / APPRENDRE / RÉVISER : `induire_k` rend jusqu'à k théories aussi cohérentes que la meilleure ; on compare
    leurs prédictions du coup `coup` (dict d'action de l'agent) depuis l'état courant. → ("agir" | "apprendre" | "reviser"
    | "inconnu", nombre de prédictions distinctes, nombre de théories). « réviser » : aucune théorie ne rejoue la dernière
    transition observée ; « inconnu » : induction impossible (le plan est alors joué comme avant)."""
    from chrysalide.arc3.logique.faits import Trajectoire
    from chrysalide.arc3.logique.induction import induire_k
    from chrysalide.arc3.logique.theorie import rejeu
    from chrysalide.arc3.moteur import _code_c
    try:
        acts = [_code_c(lot["actions"][0]) if len(lot["actions"]) == 1 else None for lot in hist["lots"]]
        a = _code_c(coup)
        if not acts or a is None or any(x is None for x in acts):
            return "inconnu", 0, 0
        tr = Trajectoire(hist["grilles"], acts)
        ths = [th for th, _ in induire_k([(tr, None, None)], k=k, limite_s=limite_s)]
        if not ths:
            return "inconnu", 0, 0
        if not any(rejeu(th, tr, debut=len(acts) - 1, libre=False)[0] for th in ths):
            return "reviser", 0, len(ths)
        preds = {frozenset(th.pas(tr.etats[-1], a, tr.taille)[0]) for th in ths}
        return ("agir" if len(preds) == 1 else "apprendre"), len(preds), len(ths)
    except Exception:  # noqa: BLE001 — induction impossible : sans avis
        return "inconnu", 0, 0
