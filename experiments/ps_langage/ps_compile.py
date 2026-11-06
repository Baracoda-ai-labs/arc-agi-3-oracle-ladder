# SPDX-License-Identifier: MIT-0
"""CW-256 [session E] : COMPILÉ des règles PuzzleScript en grilles de bits (numpy), une fois par jeu.
État : objets[couche, y, x] (indice d'objet, -1 = vide) et mouv[couche, y, x] (0 = aucun, 1-4 = up/down/left/right,
5 = action). Le filtrage d'un motif est vectorisé : masque par terme (présence ET mouvement), décalé par cellule, ET logique ;
l'application reste scalaire, sur les seules correspondances, dans l'ordre de `psmoteur.Partie` (sémantique identique,
cellule par cellule). Les règles lues sont celles de `psmoteur.Jeu`, la donnée même que lit l'interpréteur du langage
(`interpreteur_ps.json`), qui rejoue psmoteur sans écart sur les 177 jeux du banc.
Interface : PartieCompilee(jeu, k) → .tour(action), .gagne, .objets() (même format que psmoteur.Partie.objets()).
Contrôle et vitesse : uv run python experiments/ps_langage/ps_compile.py [tous|p000,p001] [--hasard 30]"""
import itertools
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parents[1] / "experiments/banc_ps"))
import psmoteur as P  # noqa: E402

CODE = {None: 0, "up": 1, "down": 2, "left": 3, "right": 4, "action": 5}
NOM = {v: k for k, v in CODE.items()}
DXY = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}


def _decale(m, sx, sy):
    """A[y, x] = m[y + sy, x + sx], False hors grille."""
    h, w = m.shape
    a = np.zeros_like(m)
    ys, yd = (slice(sy, h), slice(0, h - sy)) if sy >= 0 else (slice(0, h + sy), slice(-sy, h))
    xs, xd = (slice(sx, w), slice(0, w - sx)) if sx >= 0 else (slice(0, w + sx), slice(-sx, w))
    a[yd, xd] = m[ys, xs]
    return a


class JeuCompile:
    """Une fois par jeu : objets numérotés, couches, règles en termes numériques."""

    def __init__(self, jeu):
        self.j = jeu
        self.noms = sorted(jeu.objets)
        self.id = {o: i for i, o in enumerate(self.noms)}
        self.couche = np.array([jeu.couche[o] for o in self.noms])
        self.L = len(jeu.couches)
        self.joueurs = np.array(sorted(self.id[o] for o in jeu.joueurs), dtype=int)
        self.regles = [self._regle(r) for r in jeu.regles]
        self.vict = [(q, self._ids(X), None if Y is None else self._ids(Y)) for q, X, Y in jeu.victoire]

    def _ids(self, ens):
        return np.array(sorted(self.id[o] for o in ens), dtype=int)

    def _terme(self, t):
        ids = self._ids(t["ens"])
        tab = np.zeros(len(self.noms) + 1, dtype=bool)  # tab[o + 1] : l'objet o (−1 = vide) est-il dans l'ensemble ?
        tab[ids + 1] = True
        return {"nom": t["nom"], "ens": ids, "set": frozenset(ids.tolist()), "neg": t["neg"], "mod": t["mod"], "tab": tab,
                "couches": sorted({int(self.couche[o]) for o in ids})}

    def _regle(self, r):
        return {"groupe": r["groupe"], "late": r["late"], "dirs": r["dirs"], "cmds": r["cmds"],
                "g": [[[self._terme(t) for t in c] for c in p] for p in r["g"]],
                "d": [[[self._terme(t) for t in c] for c in p] for p in r["d"]]}


def _abs(mod, d):
    return P.REL[d].get(mod, mod) if mod is not None else None


def _mod_ok(a, m):
    """a : modificateur absolu ; m : code de mouvement (scalaire ou tableau)."""
    if a is None:
        return True
    if a == "moving":
        return m != 0
    if a == "stationary":
        return m == 0
    return m == CODE[a]


class PartieCompilee:
    def __init__(self, jeu, k, jc=None):
        self.jc = jc or JeuCompile(jeu)
        N = jeu.niveaux[k]
        self.w, self.h = N["w"], N["h"]
        self.ob = np.full((self.jc.L, self.h, self.w), -1, dtype=np.int16)
        self.mv = np.zeros((self.jc.L, self.h, self.w), dtype=np.int8)
        for i, cell in enumerate(N["grille"]):
            for kk, (o, _) in cell.items():
                self.ob[kk, i // self.w, i % self.w] = self.jc.id[o]
        self.gagne = False
        self._cache = {}  # (id du terme, direction) → masque ; vidé par _modif() à chaque écriture de l'état
        if "run_rules_on_level_start" in jeu.prelude:
            self.tour(None)
        self.depart = (self.ob.copy(), self.mv.copy())

    def _modif(self):
        self._cache = {}

    def charger(self, partie, depart=None):
        """État pris dans une psmoteur.Partie (rejeu recalé) ; `depart` : Partie dont l'état sert à `restart`."""
        self._modif()
        self.ob[:], self.mv[:] = -1, 0
        for i, cell in enumerate(partie.g):
            for kk, (o, m) in cell.items():
                self.ob[kk, i // self.w, i % self.w], self.mv[kk, i // self.w, i % self.w] = self.jc.id[o], CODE[m]
        self.gagne = False
        if depart is not None:
            d = PartieCompilee.__new__(PartieCompilee)
            d.jc, d.w, d.h = self.jc, self.w, self.h
            d.ob, d.mv, d._cache = self.ob.copy(), self.mv.copy(), {}
            d.charger(depart)
            self.depart = (d.ob.copy(), d.mv.copy())
        return self

    def objets(self):
        out = []
        for y in range(self.h):
            for x in range(self.w):
                out.append(sorted(self.jc.noms[o] for o in self.ob[:, y, x] if o >= 0))
        return out

    # ---------------------------------------------------------------- filtrage vectorisé
    def _masque_terme(self, t, d):
        cle = (id(t), d if t["mod"] is not None else None)
        c = self._cache.get(cle)
        if c is not None:
            return c
        c = self._cache[cle] = self._masque_terme_calcul(t, d)
        return c

    def _masque_terme_calcul(self, t, d):
        a, m = _abs(t["mod"], d), np.zeros((self.h, self.w), dtype=bool)
        for k in t["couches"]:
            m |= t["tab"][self.ob[k] + 1] if a is None else t["tab"][self.ob[k] + 1] & _mod_ok(a, self.mv[k])
        return ~m if t["neg"] else m

    def _masque_cellule(self, cp, d):
        m = np.ones((self.h, self.w), dtype=bool)
        for t in cp:
            m &= self._masque_terme(t, d)
            if not m.any():
                break
        return m

    def _correspondances(self, p, d):
        dx, dy = P.DIRS[d]
        m = np.ones((self.h, self.w), dtype=bool)
        for n, cp in enumerate(p):
            m &= _decale(self._masque_cellule(cp, d), dx * n, dy * n)
            if not m.any():
                return []
        return [(int(x), int(y)) for y, x in np.argwhere(m)]

    # ---------------------------------------------------------------- application scalaire (psmoteur.Partie)
    def _trouve(self, x, y, t, d):
        a = _abs(t["mod"], d)
        for k in range(self.jc.L):  # ordre des couches (psmoteur : ordre d'insertion du dict de la case)
            o = int(self.ob[k, y, x])
            if o >= 0 and o in t["set"] and _mod_ok(a, self.mv[k, y, x]):
                return o
        return None

    def _cell_ok(self, x, y, cp, d):
        liens = []
        for t in cp:
            o = self._trouve(x, y, t, d)
            if t["neg"]:
                if o is not None:
                    return None
                liens.append(None)
            else:
                if o is None:
                    return None
                liens.append(o)
        return liens

    def _en(self, p, d, x, y):
        dx, dy = P.DIRS[d]
        if not (0 <= x + dx * (len(p) - 1) < self.w and 0 <= y + dy * (len(p) - 1) < self.h):
            return None
        liens = []
        for n, cp in enumerate(p):
            li = self._cell_ok(x + dx * n, y + dy * n, cp, d)
            if li is None:
                return None
            liens.append(li)
        return liens

    def _remplacer(self, x, y, gp, dp, liens, d):
        cou = self.jc.couche
        avant = (self.ob[:, y, x].copy(), self.mv[:, y, x].copy())
        noms_d = {t["nom"] for t in dp if not t["neg"]}
        for t, o in zip(gp, liens):
            if not t["neg"] and t["nom"] not in noms_d:
                k = cou[o]
                if self.ob[k, y, x] == o:
                    self.ob[k, y, x], self.mv[k, y, x] = -1, 0
        lies = {t["nom"]: (o, t) for t, o in zip(gp, liens) if not t["neg"]}
        for t in dp:
            if t["neg"]:
                for k in range(self.jc.L):
                    if self.ob[k, y, x] in t["set"]:
                        self.ob[k, y, x], self.mv[k, y, x] = -1, 0
                continue
            if t["nom"] in lies:
                o, tg = lies[t["nom"]]
            elif len(t["ens"]) == 1:
                o, tg = int(t["ens"][0]), None
            else:
                raise P.Refus(f"propriété créée sans lien : {t['nom']}")
            k = cou[o]
            m = int(self.mv[k, y, x]) if self.ob[k, y, x] == o else 0
            if t["mod"] is not None:
                a = _abs(t["mod"], d)
                if a == "stationary":
                    m = 0
                elif a != "moving":
                    m = CODE[a]
            elif tg is not None and tg["mod"] is not None:
                m = 0
            self.ob[k, y, x], self.mv[k, y, x] = o, m
        ch = not (np.array_equal(avant[0], self.ob[:, y, x]) and np.array_equal(avant[1], self.mv[:, y, x]))
        if ch:
            self._modif()
        return ch

    # ---------------------------------------------------------------- règle d'UNE cellule : application vectorisée
    def _liens_vec(self, t, d):
        """Objet lié au terme dans chaque case (-1 sinon) : 1ʳᵉ couche, dans l'ordre croissant, qui le satisfait (= _trouve)."""
        a, li = _abs(t["mod"], d), np.full((self.h, self.w), -1, dtype=np.int16)
        for k in reversed(t["couches"]):
            ok = t["tab"][self.ob[k] + 1] & _mod_ok(a, self.mv[k])
            li[ok] = self.ob[k][ok]
        return li

    def _appliquer_1case(self, r, d, M):
        """psmoteur._remplacer sur toutes les cases M à la fois : exact car un motif d'une cellule ne lit ni n'écrit que sa
        case, et l'ordre des correspondances n'importe pas."""
        gp, dp, cou = r["g"][0][0], r["d"][0][0], self.jc.couche
        avant = (self.ob.copy(), self.mv.copy())
        liens = [self._liens_vec(t, d) if not t["neg"] else None for t in gp]
        noms_d = {t["nom"] for t in dp if not t["neg"]}
        for t, li in zip(gp, liens):
            if not t["neg"] and t["nom"] not in noms_d:
                for k in range(self.jc.L):
                    z = M & (li >= 0) & (cou[np.maximum(li, 0)] == k) & (self.ob[k] == li)
                    self.ob[k][z], self.mv[k][z] = -1, 0
        lies = {t["nom"]: (li, t) for t, li in zip(gp, liens) if not t["neg"]}
        for t in dp:
            if t["neg"]:
                for k in t["couches"]:
                    z = M & t["tab"][self.ob[k] + 1]
                    self.ob[k][z], self.mv[k][z] = -1, 0
                continue
            if t["nom"] in lies:
                o, tg = lies[t["nom"]]
            elif len(t["ens"]) == 1:
                o, tg = np.full((self.h, self.w), int(t["ens"][0]), dtype=np.int16), None
            else:
                raise P.Refus(f"propriété créée sans lien : {t['nom']}")
            for k in np.unique(cou[o[M]]) if M.any() else []:
                z = M & (cou[np.maximum(o, 0)] == k)
                m = np.where(self.ob[k] == o, self.mv[k], 0)
                if t["mod"] is not None:
                    a = _abs(t["mod"], d)
                    if a == "stationary":
                        m = np.zeros_like(m)
                    elif a != "moving":
                        m = np.full_like(m, CODE[a])
                elif tg is not None and tg["mod"] is not None:
                    m = np.zeros_like(m)
                self.ob[k][z], self.mv[k][z] = o[z], m[z]
        ch = not self._egal(avant)
        self._modif()  # (les masques ont pu être lus pendant l'application : vidés dans tous les cas)
        return ch

    def _appliquer(self, r):
        change, cmds = False, set()
        if len(r["g"]) == 1 and len(r["g"][0]) == 1:
            for d in r["dirs"]:
                M = self._masque_cellule(r["g"][0][0], d)
                if M.any():
                    cmds |= set(r["cmds"])
                    if r["d"]:
                        change |= self._appliquer_1case(r, d, M)
            return change, cmds
        for d in r["dirs"]:
            listes = [self._correspondances(p, d) for p in r["g"]]
            if any(not li for li in listes):
                continue
            dx, dy = P.DIRS[d]
            for combo in itertools.product(*listes):
                if any(self._en(p, d, x, y) is None for p, (x, y) in zip(r["g"], combo)):
                    continue
                cmds |= set(r["cmds"])
                if not r["d"]:
                    continue
                for p, q, (x, y) in zip(r["g"], r["d"], combo):
                    liens = self._en(p, d, x, y)
                    for n, (cp, cq) in enumerate(zip(p, q)):
                        change |= self._remplacer(x + dx * n, y + dy * n, cp, cq, liens[n], d)
        return change, cmds

    def _regles(self, late):
        cmds = set()
        rs = [r for r in self.jc.regles if r["late"] == late]
        for gr in sorted({r["groupe"] for r in rs}):
            g = [r for r in rs if r["groupe"] == gr]
            for _ in range(200):
                ch = False
                for r in g:
                    c, cm = self._appliquer(r)
                    ch |= c
                    cmds |= cm
                if not ch:
                    break
        return cmds

    def _mouvements(self):
        bouge = True
        while bouge:
            bouge = False
            ks, ys, xs = np.nonzero((self.mv > 0) & (self.mv < 5))
            for i in np.lexsort((ks, xs, ys)):  # ordre de psmoteur : case (ligne par ligne), puis couche
                k, y, x = int(ks[i]), int(ys[i]), int(xs[i])
                m = int(self.mv[k, y, x])
                if m == 0 or m == 5:
                    continue
                dx, dy = DXY[m]
                if not (0 <= x + dx < self.w and 0 <= y + dy < self.h) or self.ob[k, y + dy, x + dx] >= 0:
                    continue
                self.ob[k, y + dy, x + dx], self.mv[k, y + dy, x + dx] = self.ob[k, y, x], 0
                self.ob[k, y, x], self.mv[k, y, x] = -1, 0
                bouge = True
        self.mv[:] = 0
        self._modif()

    def _pos_joueurs(self):
        m = np.isin(self.ob, self.jc.joueurs).any(axis=0)
        return np.flatnonzero(m).tolist()

    def victoire(self):
        if not self.jc.vict:
            return False
        for q, X, Y in self.jc.vict:
            cx = np.isin(self.ob, X).any(axis=0)
            sur = np.isin(self.ob, Y).any(axis=0) if Y is not None else np.ones_like(cx)
            if q == "all" and (cx & ~sur).any():
                return False
            if q == "no" and (cx & sur).any():
                return False
            if q == "some" and not (cx & sur).any():
                return False
        return True

    def tour(self, action):
        avant = (self.ob.copy(), self.mv.copy())
        for _ in range(50):
            sauve = (self.ob.copy(), self.mv.copy())
            self._modif()
            if action is not None:
                self.mv[np.isin(self.ob, self.jc.joueurs)] = CODE[action]
            pos_j = self._pos_joueurs()
            cmds = self._regles(False)
            if "cancel" in cmds:
                self.ob, self.mv = sauve
                self._modif()
                return not self._egal(avant)
            self._mouvements()
            cmds |= self._regles(True)
            if "cancel" in cmds:
                self.ob, self.mv = sauve
                self._modif()
                return not self._egal(avant)
            if "restart" in cmds:
                self.ob, self.mv = self.depart[0].copy(), self.depart[1].copy()
                self._modif()
                return True
            if action is not None and "require_player_movement" in self.jc.j.prelude and pos_j == self._pos_joueurs():
                self.ob, self.mv = sauve
                self._modif()
                return not self._egal(avant)
            if "win" in cmds or self.victoire():
                self.gagne = True
                return True
            if "again" not in cmds or self._egal(sauve):
                break
            action = None
        return not self._egal(avant)

    def _egal(self, e):
        return np.array_equal(self.ob, e[0]) and np.array_equal(self.mv, e[1])


# ==================================================================== banc de vérité et vitesse
def comparer(jeu_id, n_hasard=30):
    """Compilé contre psmoteur (= interprété du langage, 0 écart sur le banc), mêmes trajectoires que le juge :
    30 coups au hasard (random.Random(1000 + k)) puis la solution, par niveau. → (coups, exacts, s_psmoteur, s_compile)."""
    import ast
    import json
    import random
    import re
    import time
    env = ICI.parents[1] / "experiments/banc_ps/environment_files" / jeu_id
    src = next(env.glob(f"*/{jeu_id}.py")).read_text()
    lire = lambda n: ast.literal_eval(re.search(rf"^{n} = (.*)$", src, re.MULTILINE).group(1))
    jeu, ks, acts = P.Jeu(lire("SOURCE_PS")), lire("NIVEAUX_PS"), lire("ACTIONS")
    verite = json.loads(next(env.glob("*/verite.json")).read_text())
    jc = JeuCompile(jeu)
    noms = {1: "up", 2: "down", 3: "left", 4: "right", 5: "action"}
    r = {"jeu": jeu_id, "coups": 0, "exacts": 0, "s_ref": 0.0, "s_comp": 0.0, "ecarts": []}
    for i, k in enumerate(ks):
        rng = random.Random(1000 + i)
        for seq in ([rng.choice(acts) for _ in range(n_hasard)], verite["niveaux"][i]["solution"]):
            a, b = P.Partie(jeu, k), PartieCompilee(jeu, k, jc)
            for c in seq:
                t0 = time.perf_counter()
                try:
                    a.tour(noms[c])
                    ra = None
                except P.Refus as ex:
                    ra = str(ex)
                t1 = time.perf_counter()
                try:
                    b.tour(noms[c])
                    rb = None
                except P.Refus as ex:
                    rb = str(ex)
                t2 = time.perf_counter()
                r["s_ref"] += t1 - t0
                r["s_comp"] += t2 - t1
                ok = ra == rb and a.objets() == b.objets() and a.gagne == b.gagne
                r["coups"] += 1
                r["exacts"] += ok
                if not ok:
                    r["ecarts"].append((i, c))
                    break
                if a.gagne or ra:
                    break
    return r


if __name__ == "__main__":
    import json
    import time
    cible = sys.argv[1] if len(sys.argv) > 1 else "p000"
    n = int(sys.argv[sys.argv.index("--hasard") + 1]) if "--hasard" in sys.argv else 30
    racine = ICI.parents[1] / "experiments/banc_ps/environment_files"
    jeux = sorted(d.name for d in racine.iterdir() if d.is_dir()) if cible == "tous" else cible.split(",")
    tout = []
    for g in jeux:
        try:
            r = comparer(g, n)
        except Exception as ex:  # noqa: BLE001 — échec compté
            r = {"jeu": g, "erreur": f"{type(ex).__name__}: {str(ex)[:150]}", "coups": 0, "exacts": 0, "s_ref": 0, "s_comp": 0}
        tout.append(r)
        print(g, f"{r['exacts']}/{r['coups']}", f"psmoteur {r['s_ref']:.2f} s, compilé {r['s_comp']:.2f} s",
              r.get("erreur", ""), r.get("ecarts", [])[:3], flush=True)
    c, e = sum(r["coups"] for r in tout), sum(r["exacts"] for r in tout)
    sr, sc = sum(r["s_ref"] for r in tout), sum(r["s_comp"] for r in tout)
    print(f"TOTAL {len(tout)} jeux : {e}/{c} coups identiques ; psmoteur {sr:.1f} s, compilé {sc:.1f} s (×{sr / max(sc, 1e-9):.1f})")
    (ICI / "resultats" / f"compile_{cible.replace(',', '_')}.json").write_text(json.dumps(tout, indent=1, default=str))
    _ = time
