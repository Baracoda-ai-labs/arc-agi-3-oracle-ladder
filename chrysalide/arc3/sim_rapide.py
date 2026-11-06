# SPDX-License-Identifier: MIT-0
"""Simulateur compilé du langage v0.1 (`langage.py`) : mêmes règles JSON, même `Scene`, mêmes images, plus vite.
1. `ProgrammeCompile(texte)` : l'arbre JSON est compilé UNE fois en fermetures Python (une par terme) ; un coup n'interprète
   plus l'arbre (plus de chaîne de `if op == …`, plus de copie de dictionnaire d'environnement : les variables ont une case
   fixe dans une liste, sauvée/restaurée autour de `pour` et des quantifieurs). Même ordre d'évaluation, mêmes erreurs
   (variable inconnue, terme inconnu) levées au même moment que l'interpréteur.
2. Primitives accélérées à résultat identique : `chevauche`/`libre` par intersection de boîtes puis de masques (au lieu
   d'ensembles de cases), `couleur` par comparaison de tableau (au lieu de `np.unique`), `a` trié après filtrage (tri stable).
3. `image(scene)` : rendu identique bit à bit à `Scene.image()` ; `cloner(scene, etat)` : copie profonde rapide qui garde
   les identités (un objet de l'état caché qui pointe un sprite pointe la copie du sprite), comme `copy.deepcopy`.
Couvre tout le vocabulaire v0.2 de `langage.py` : mode « lois » (poids, `conflits`), `au_debut`/`debut_niveau`, mots
(macros, compilées en fonctions : paramètres sur des cases sauvées/restaurées) et fonctions (bac à sable de `langage`, appelé
tel quel). Seul `pousser` délègue sa poussée en chaîne à `Programme._pousser` (même code).
Interface : `ProgrammeCompile` a la même interface que `langage.Programme` (`.etat`, `.conflits`, `.mots`, `.fonctions`,
`.step(scene, action, niveau=0)`, et `ev`/`fait` pour les tests)."""
import copy
import math
import operator

import numpy as np

from chrysalide.arc3.langage import (
    ATTRIBUT,
    EFFETS_CANEVAS,
    PROF_MAX,
    TERMES_CANEVAS,
    ErreurLangage,
    Programme,
    _alea,
    _appeler_fonction,
    _cases,
    _contact_moteur,
    _correspond_rot,
    _filtre,
    _recharger,
    _simple,
    compiler_mots,
    instantane_scene,
    restaurer_scene,
    terme_canevas,
    valeur_param,
)
from chrysalide.arc3.ontologie_exec import Scene, dessiner_canevas

_LIBRE = object()  # case de variable non liée (seulement pour `_depile`, liée dynamiquement)
_SCENE, _ACTION, _NIVEAU, _DEPILE, _DEBUT = 0, 1, 2, 3, 4
_BASE = 5  # premières cases : contexte du coup ; puis une case par nom de variable
_ARITH = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "+": operator.add,
          "-": operator.sub, "*": operator.mul, "//": operator.floordiv, "%": operator.mod}
_EFFETS_SCENE = ("deplacer", "placer", "tourner", "recolorer", "ecrire", "montrer", "calque", "creer", "retirer",
                 "remodeler", "poser_motif", "poser_bloquant", "rendre_intangible", *EFFETS_CANEVAS)
_RESERVES = {"_scene", "_action", "_niveau", "_depile", "_debut"}
_CTX = {"_scene": _SCENE, "_action": _ACTION, "_niveau": _NIVEAU, "_debut": _DEBUT}


def _leve(msg):
    def f(V):
        raise ErreurLangage(msg)
    return f


def _const(t):
    f = lambda V: t
    f.cst = (t,)  # marque : terme constant (permet de spécialiser l'opération qui l'utilise)
    return f


# opérations binaires à 2nd argument constant (même calcul, un appel de fonction en moins)
_ARITH_C = {"<": lambda f, c: lambda V: f(V) < c, "<=": lambda f, c: lambda V: f(V) <= c,
            ">": lambda f, c: lambda V: f(V) > c, ">=": lambda f, c: lambda V: f(V) >= c,
            "+": lambda f, c: lambda V: f(V) + c, "-": lambda f, c: lambda V: f(V) - c,
            "*": lambda f, c: lambda V: f(V) * c, "//": lambda f, c: lambda V: f(V) // c,
            "%": lambda f, c: lambda V: f(V) % c}


def _identique(e, x):
    return e is x if isinstance(x, dict) else e == x


# ------------------------------------------------------------------ primitives géométriques (résultat identique)
_ND = np.ndarray


def _chevauche_px(o1, o2, dx=0, dy=0):
    """Vrai si o1 décalé de (dx, dy) et o2 ont une case opaque commune — égal à `bool(_cases(o1, dx, dy) & _cases(o2))`."""
    p1, p2 = o1["pixels"], o2["pixels"]
    if type(p1) is not _ND:
        p1 = np.asarray(p1)
    if type(p2) is not _ND:
        p2 = np.asarray(p2)
    x1, y1, x2, y2 = o1["x"] + dx, o1["y"] + dy, o2["x"], o2["y"]
    if not (p1.ndim == 2 and p2.ndim == 2 and type(x1) is int and type(y1) is int and type(x2) is int
            and type(y2) is int):
        return bool(_cases(o1, dx, dy) & _cases(o2))
    h1, w1 = p1.shape
    h2, w2 = p2.shape
    xa = x1 if x1 > x2 else x2  # noqa: FURB136 (plus rapide que max/min)
    xb = x1 + w1 if x1 + w1 < x2 + w2 else x2 + w2  # noqa: FURB136 (plus rapide que max/min)
    if xa >= xb:
        return False
    ya = y1 if y1 > y2 else y2  # noqa: FURB136
    yb = y1 + h1 if y1 + h1 < y2 + h2 else y2 + h2  # noqa: FURB136
    if ya >= yb:
        return False
    return bool(((p1[ya - y1:yb - y1, xa - x1:xb - x1] >= 0) & (p2[ya - y2:yb - y2, xa - x2:xb - x2] >= 0)).any())


_COULEURS = {}  # id(pixels) → (tableau, couleurs présentes) ; sûr : les pixels d'un sprite sont copiés avant toute écriture


def _couleurs(px):
    """Couleurs présentes dans un tableau de pixels (CW-254 : le filtre « couleur » ne refait plus `== v` à chaque appel)."""
    g = _COULEURS.get(id(px))
    if g is None or g[0] is not px:
        if len(_COULEURS) > 200000:
            _COULEURS.clear()
        g = _COULEURS[id(px)] = (px, frozenset(np.unique(np.asarray(px)).tolist()))
    return g[1]


def _predicat(f):
    """Filtre `objets`/`libre` précompilé ; même résultat que `langage._filtre(s, f)`."""
    tests = []
    for k, v in f.items():
        if k == "tag":
            tests.append(lambda s, v=v: v in s.get("tags", ()))
        elif k == "nom":
            tests.append(lambda s, v=v: s.get("nom") == v)
        elif k == "visible":
            tests.append(lambda s, v=bool(v): bool(s.get("visible", True)) == v)
    if "couleur" in f:  # en dernier (le plus cher) : l'ordre ne change rien, les tests sont purs
        v = f["couleur"]
        if type(v) in (int, float, bool):
            tests.append(lambda s, v=v: v in _couleurs(s["pixels"]))
        else:
            tests.append(lambda s, f={"couleur": v}: _filtre(s, f))
    if not tests:
        return lambda s: True
    if len(tests) == 1:
        return tests[0]
    if len(tests) == 2:
        t0, t1 = tests
        return lambda s: t0(s) and t1(s)
    if len(tests) == 3:
        t0, t1, t2 = tests
        return lambda s: t0(s) and t1(s) and t2(s)
    return lambda s: all(t(s) for t in tests)


def _par_tag(sc, tag):
    """Sprites portant `tag`, dans l'ordre de `sc.sprites`. Index gardé sur la scène, refait quand la liste change
    (`retirer` la remplace, `creer` l'allonge ; aucun effet ne modifie les tags)."""
    c = sc.__dict__.get("_index_tags")
    sp = sc.sprites
    if c is None or c[0] is not sp or c[1] != len(sp):
        idx = {}
        for s in sp:
            for t in s.get("tags", ()):
                lst = idx.setdefault(t, [])
                if not lst or lst[-1] is not s:
                    lst.append(s)
        c = sc._index_tags = (sp, len(sp), idx)
    return c[2].get(tag, ())


def _a(sc, x, y):
    """= `Scene.a` : sprites visibles couvrant (x, y), calque haut d'abord (tri stable après filtrage = même ordre)."""
    out = []
    for s in sc.sprites:
        if s["visible"]:
            px = s["pixels"]
            dy, dx = y - s["y"], x - s["x"]
            if 0 <= dy < px.shape[0] and 0 <= dx < px.shape[1] and px[dy, dx] >= 0:
                out.append(s)
    out.sort(key=lambda s: -s["couche"])
    return out


# ------------------------------------------------------------------ compilation
class ProgrammeCompile:
    def __init__(self, texte):
        self.p = texte
        self.etat = copy.deepcopy(texte.get("etat", {}))
        self.conflits = []  # mode « lois » : (loi écartée, effet, poids gagnant, poids écarté), comme Programme
        self.mots, self.fonctions = compiler_mots(texte)  # mêmes refus à la définition que l'interpréteur
        self._prof = 0
        self.instantanes = {}  # instantane(n) : nom -> (sprites, etat) copiés en profondeur, comme Programme
        self.replis = []  # nœuds délégués à l'interpréteur (mal formés) : (sorte, mot)
        self._ref = Programme.__new__(Programme)  # interpréteur de repli (nœuds mal formés, poussée en chaîne)
        self._ref.p, self._ref.mots, self._ref.fonctions, self._ref.conflits, self._ref._prof = \
            texte, self.mots, self.fonctions, self.conflits, 0
        self._ref.instantanes = self.instantanes
        self._cases = {}  # nom de variable -> indice dans la liste V
        self._corps = {}  # mot -> corps compilé (pas de récursion : compilation finie)
        self._au_debut = tuple(self.e(x, {}) for x in texte.get("au_debut", []))
        self._lois = texte.get("mode") == "lois"
        self._regles = [self._regle(r) for r in texte.get("regles", [])]
        self._V = [None] * (_BASE + len(self._cases))

    def distance(self, regle):
        """= `plan_langage.distance_but` COMPILÉE (CW-254, vitesse) : même lecture de la condition de victoire (« vide »
        compte, « et » additionne, « ou » prend le min, « tous » compte les éléments faux, « = » écart ou éléments
        différents, sinon 0/1 ; toute erreur → 1 ; liaisons en échec → None). → fonction (scène, état caché) → distance."""
        from chrysalide.arc3.logique.plan_langage import _gel
        portee, soit = {}, []
        for v, t in (regle.get("soit") or {}).items():
            f = self.c(t, portee)
            portee = {**portee, v: self._case(v)}
            soit.append((portee[v], f))

        def sur(f):
            def g(V):
                try:
                    return f(V)
                except Exception:  # noqa: BLE001 — comme distance_but : une sous-distance qui plante vaut 1
                    return 1
            return g

        def h(t, P):
            if isinstance(t, list) and t and isinstance(t[0], str):
                op, a = t[0], t[1:]
                if op == "vide":
                    f0 = self.c(a[0], P)
                    return sur(lambda V: len(f0(V) or []))
                if op == "et":
                    fs = [h(x, P) for x in a]
                    return sur(lambda V: sum(f(V) for f in fs))
                if op == "ou":
                    fs = [h(x, P) for x in a]
                    return sur(lambda V: min(f(V) for f in fs))
                if op == "tous" and len(a) == 3:
                    k = self._case(a[0].lstrip("$"))
                    fl, fc = self.c(a[1], P), self.c(a[2], {**P, a[0].lstrip("$"): k})

                    def tous(V):
                        ancien, n = V[k], 0
                        try:
                            for x in fl(V) or []:
                                V[k] = x
                                n += 0 if fc(V) else 1
                        finally:
                            V[k] = ancien
                        return n
                    return sur(tous)
                if op == "=" and len(a) == 2:
                    fx, fy, fe = self.c(a[0], P), self.c(a[1], P), self.c(t, P)

                    def egal(V):
                        x, y = fx(V), fy(V)
                        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
                            return abs(x - y)
                        if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
                            return sum(1 for u, v in zip(x, y, strict=False) if _gel(u) != _gel(v)) + abs(len(x) - len(y))
                        return 0 if fe(V) else 1
                    return sur(egal)
            f = self.c(t, P)
            return sur(lambda V: 0 if f(V) else 1)

        corps = h(regle.get("quand", True), portee)
        self._V.extend([None] * (_BASE + len(self._cases) - len(self._V)))

        def distance(scene, etat):
            V = self._V
            V[_SCENE], V[_ACTION], V[_NIVEAU], V[_DEBUT], V[_DEPILE] = scene, None, 0, False, _LIBRE
            self.etat = etat
            for k, f in soit:
                try:
                    V[k] = f(V)
                except Exception:  # noqa: BLE001 — liaison qui dépend de l'action : None, comme distance_but
                    V[k] = None
            return corps(V)
        return distance

    def _case(self, nom):
        if nom in _RESERVES:
            raise NotImplementedError(f"variable réservée liée par le programme : {nom}")
        return self._cases.setdefault(nom, _BASE + len(self._cases))

    def _regle(self, r):
        portee, soit = {}, []
        for v, t in (r.get("soit") or {}).items():
            f = self.c(t, portee)  # la liaison ne voit que les liaisons précédentes
            portee = {**portee, v: self._case(v)}
            soit.append((portee[v], f))
        quand = self.c(r.get("quand", True), portee)
        alors = tuple(self.e(x, portee) for x in r.get("alors", []))
        if self._lois:  # (effet, clé de conflit, nom de l'effet) ; poids, nom de la loi
            alors = (tuple((f, self._cle(x, portee), x[0]) for f, x in zip(alors, r.get("alors", []), strict=True)),
                     r.get("poids", 1), r.get("nom"), r.get("phase", 0))
        return tuple(soit), quand, alors, r.get("puis", "stop") == "stop"

    def _cle(self, e, P):
        """= `Programme._cle_effet` compilé : (objet, attribut) touché par un effet simple, ou None."""
        try:
            op = e[0] if isinstance(e, list) and e else None
            if op in ATTRIBUT:
                f1, at = self.c(e[1], P), ATTRIBUT[op]
                return lambda V: (id(f1(V)), at)
            if op in ("poser", "empiler", "depiler", "consommer", "recharger"):
                n = e[1]
                return lambda V: ("etat", n)
            if op == "poser_attr":
                f1, f2 = self.c(e[1], P), self.c(e[2], P)
                return lambda V: (id(f1(V)), ("attr", f2(V)))
            return None
        except (IndexError, KeyError, TypeError):
            self.replis.append(("cle", str(e)[:40]))
            return lambda V: self._ref._cle_effet(e, self._env(V, P))

    # -------------------------------------------------------------- repli : terme mal formé -> interpréteur de référence
    def _env(self, V, P):
        env = {"_scene": V[_SCENE], "_action": V[_ACTION], "_niveau": V[_NIVEAU], "_debut": V[_DEBUT],
               **{n: V[k] for n, k in P.items()}}
        if V[_DEPILE] is not _LIBRE:
            env["_depile"] = V[_DEPILE]
        self._ref.etat, self._ref._prof = self.etat, self._prof
        return env

    # -------------------------------------------------------------- compatibilité Programme.ev / fait (tests)
    def _V_de(self, env, P):
        V = [None] * (_BASE + len(self._cases))
        V[_SCENE], V[_ACTION], V[_NIVEAU] = env.get("_scene"), env.get("_action"), env.get("_niveau", 0)
        V[_DEPILE], V[_DEBUT] = env.get("_depile", _LIBRE), env.get("_debut", False)
        for n, k in P.items():
            V[k] = env[n]
        return V

    def ev(self, t, env):
        P = {n: self._case(n) for n in env if n not in _RESERVES}
        f = self.c(t, P)
        return f(self._V_de(env, P))

    def fait(self, e, env):
        P = {n: self._case(n) for n in env if n not in _RESERVES}
        f = self.e(e, P)
        V = self._V_de(env, P)
        f(V)
        if V[_DEPILE] is not _LIBRE:
            env["_depile"] = V[_DEPILE]

    # -------------------------------------------------------------- mots définis (macros) et fonctions
    def _appel(self, op, a, P, sorte):
        """= `Programme._appel` : arguments évalués dans l'appelant, corps avec les seuls paramètres liés."""
        prog = self
        if op in self.fonctions:
            fd = self.fonctions[op]
            if sorte != "terme":
                return _leve(f"la fonction {op!r} est un terme, employée comme effet")
            if len(a) != len(fd["params"]):
                return _leve(f"fonction {op!r} : arité {len(fd['params'])}, {len(a)} argument(s) donné(s)")
            fs = tuple(self.c(x, P) for x in a)
            return lambda V: _appeler_fonction(fd, [_simple(g(V)) for g in fs], op)
        d = self.mots[op]
        ps, s = d.get("params", []), d.get("sorte", "terme")
        if s != sorte:
            return _leve(f"le mot {op!r} est un {s}, employé comme {sorte}")
        if len(a) != len(ps):
            return _leve(f"mot {op!r} : arité {len(ps)}, {len(a)} argument(s) donné(s)")
        fs = tuple(self.c(x, P) for x in a)
        ks = tuple(self._case(p[1:]) for p in ps)
        if op not in self._corps:
            Pm = dict(zip((p[1:] for p in ps), ks, strict=True))
            self._corps[op] = self.c(d["corps"], Pm) if sorte == "terme" else tuple(self.e(x, Pm) for x in d["corps"])
        corps, terme = self._corps[op], sorte == "terme"

        def appel(V):
            if prog._prof >= PROF_MAX:
                raise ErreurLangage(f"mot {op!r} : profondeur d'appel > {PROF_MAX}")
            vals = [g(V) for g in fs]
            anciens, dep = [V[k] for k in ks], V[_DEPILE]
            for k, v in zip(ks, vals, strict=True):
                V[k] = v
            prog._prof += 1
            try:
                if terme:
                    return corps(V)
                for f in corps:
                    f(V)
                return None
            finally:
                prog._prof -= 1
                for k, v in zip(ks, anciens, strict=True):
                    V[k] = v
                V[_DEPILE] = dep  # un depiler du corps reste dans l'environnement du corps
        return appel

    def c(self, t, P):
        """Terme compilé ; un terme mal formé (argument manquant…) est délégué à l'interpréteur, qui lèvera la même erreur
        au même moment (ou pas, si la branche n'est jamais évaluée)."""
        try:
            return self._c(t, P)
        except (IndexError, KeyError, TypeError, AttributeError, ValueError):
            self.replis.append(("terme", t[0] if isinstance(t, list) and t else t))
            return lambda V: self._ref.ev(t, self._env(V, P))

    def e(self, x, P):
        try:
            return self._e(x, P)
        except (IndexError, KeyError, TypeError, AttributeError, ValueError):
            self.replis.append(("effet", x[0] if isinstance(x, list) and x else x))
            def repli(V):
                env = self._env(V, P)
                try:
                    self._ref.fait(x, env)
                finally:
                    self.etat = self._ref.etat  # restaurer remplace l'état
                    if "_depile" in env:
                        V[_DEPILE] = env["_depile"]
            return repli

    # -------------------------------------------------------------- termes v0.2
    def _c_v02(self, op, a, P, cc):
        if op == "div":
            f0, f1 = cc(a[0]), cc(a[1])
            return lambda V: float(f0(V)) / float(f1(V))
        if op == "racine":
            f0 = cc(a[0])
            return lambda V: float(f0(V)) ** 0.5
        if op == "arrondi":
            f0 = cc(a[0])
            return lambda V: round(float(f0(V)))
        if op == "plancher":
            f0 = cc(a[0])
            return lambda V: math.floor(f0(V))
        if op == "alea":
            f0, f1 = cc(a[0]), cc(a[1])
            f2 = cc(a[2]) if len(a) > 2 else None
            return lambda V: _alea(int(f0(V)), int(f1(V)), int(f2(V)) if f2 is not None else 0)
        if op == "intervalle":
            f0, f1 = cc(a[0]), cc(a[1])
            return lambda V: list(range(f0(V), f1(V)))
        if op in ("trier", "trier_desc"):
            fl, nv = cc(a[0]), a[1].lstrip("$")
            k = self._case(nv)
            fk, inv = self.c(a[2], {**P, nv: k}), op == "trier_desc"

            def trier(V):
                liste, ancien = fl(V) or [], V[k]

                def cle(e):
                    V[k] = e
                    return fk(V)
                try:
                    return sorted(liste, key=cle, reverse=inv)
                finally:
                    V[k] = ancien
            return trier
        if op == "composantes":
            na, nb = a[0].lstrip("$"), a[1].lstrip("$")
            ka, kb = self._case(na), self._case(nb)
            fl, fr = cc(a[2]), self.c(a[3], {**P, na: ka, nb: kb})

            def composantes(V):
                liste = list(fl(V) or [])
                parent = list(range(len(liste)))

                def racine(i):
                    while parent[i] != i:
                        i = parent[i]
                    return i
                sa, sb = V[ka], V[kb]
                try:
                    for i in range(len(liste)):
                        for j in range(i + 1, len(liste)):
                            V[ka] = liste[i]
                            V[kb] = liste[j]
                            if fr(V):
                                ri, rj = racine(i), racine(j)
                                if ri != rj:
                                    parent[rj] = ri
                finally:
                    V[ka] = sa
                    V[kb] = sb
                groupes = {}
                for i, e in enumerate(liste):
                    groupes.setdefault(racine(i), []).append(e)
                return list(groupes.values())
            return composantes
        if op in ("visible", "bloquant"):
            f0 = cc(a[0])

            def vis(V):
                o = f0(V)
                return o is not None and bool(o.get(op, True))
            return vis
        if op == "a_tag":
            f0, f1 = cc(a[0]), cc(a[1])

            def a_tag(V):
                o, t = f0(V), f1(V)
                return o is not None and t in o.get("tags", ())
            return a_tag
        if op == "calque":
            if len(a) != 1:
                return _leve("terme calque(o) : 1 argument (l'effet calque(o, c) n'est pas un terme)")
            f0 = cc(a[0])

            def calque(V):
                o = f0(V)
                return None if o is None else o["couche"]
            return calque
        if op == "debut_niveau":
            return lambda V: bool(V[_DEBUT])
        if op in ("argmin", "argmax"):
            nv = a[0].lstrip("$")
            k = self._case(nv)
            fl, fk, mini = cc(a[1]), self.c(a[2], {**P, nv: k}), op == "argmin"

            def argm(V):
                meilleur = cle = None
                ancien = V[k]
                try:
                    for e in fl(V) or []:
                        V[k] = e
                        x = fk(V)
                        if cle is None or (x < cle if mini else x > cle):
                            meilleur, cle = e, x
                finally:
                    V[k] = ancien
                return meilleur
            return argm
        if op == "tags":
            f0 = cc(a[0])

            def tags(V):
                o = f0(V)
                return [] if o is None else list(o.get("tags", ()))
            return tags
        if op == "prefixe":
            f0, f1 = cc(a[0]), cc(a[1])

            def prefixe(V):
                c = f0(V)
                return None if c is None else str(c)[:f1(V)]
            return prefixe
        if op == "segment":
            f0, f1, f2 = cc(a[0]), cc(a[1]), cc(a[2])

            def segment(V):
                c, sep, i = f0(V), f1(V), f2(V)
                m = [] if c is None else str(c).split(sep)
                return m[i] if -len(m) <= i < len(m) else None
            return segment
        if op == "param":  # = Programme : section « niveau » du programme, repli sur "*"
            f0, texte = cc(a[0]), self.p

            def param(V):
                n = getattr(V[_SCENE], "niveau", None)
                return valeur_param(texte, V[_NIVEAU] if n is None else n, f0(V))
            return param
        if op == "donnees_de_niveau":
            f0 = cc(a[0])
            return lambda V: copy.deepcopy(getattr(V[_SCENE], "donnees", {}).get(f0(V)))
        if op == "attr_cache":
            f0, f1 = cc(a[0]), cc(a[1])

            def attr_cache(V):
                o = f0(V)
                return None if o is None else o.get("cache", {}).get(f1(V))
            return attr_cache
        if op == "forme_modele":
            f0 = cc(a[0])

            def forme_modele(V):
                m = getattr(V[_SCENE], "modeles", {}).get(f0(V))
                return None if m is None else np.asarray(m).tolist()
            return forme_modele
        if op == "dernier_niveau":
            def dernier(V):
                d = getattr(V[_SCENE], "dernier_niveau", None)
                return bool(d()) if callable(d) else False
            return dernier
        if op == "echelle":
            f0 = cc(a[0])
            return lambda V: f0(V).get("echelle", 1)
        if op == "contact_moteur":
            f0, f1 = cc(a[0]), cc(a[1])
            return lambda V: _contact_moteur(f0(V), f1(V))
        if op == "correspond":
            f0, f1 = cc(a[0]), cc(a[1])
            return lambda V: _correspond_rot(f0(V), f1(V)) is not None
        if op == "correspond_rot":
            f0, f1 = cc(a[0]), cc(a[1])
            return lambda V: _correspond_rot(f0(V), f1(V))
        if op == "epuise":
            n, f1, prog = a[0], (cc(a[1]) if len(a) > 1 else _const(0)), self
            return lambda V: (prog.etat.get(n) or 0) <= f1(V)
        if op == "utilise":
            f0 = cc(a[0])

            def utilise(V):
                o = f0(V)
                return o is not None and bool(o.get("attrs", {}).get("utilise"))
            return utilise
        return None

    # -------------------------------------------------------------- termes
    def _c(self, t, P):
        if isinstance(t, str) and t.startswith("$"):
            n = t[1:]
            if n in P:
                return operator.itemgetter(P[n])
            if n in _CTX:
                return operator.itemgetter(_CTX[n])
            if n == "_depile":
                def dep(V):
                    v = V[_DEPILE]
                    if v is _LIBRE:
                        raise ErreurLangage(f"variable inconnue {t}")
                    return v
                return dep
            return _leve(f"variable inconnue {t}")
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            return _const(t)
        op, a = t[0], t[1:]
        if op in self.mots or op in self.fonctions:
            return self._appel(op, a, P, "terme")
        prog = self
        cc = lambda x: self.c(x, P)
        f = self._c_v02(op, a, P, cc)
        if f is not None:
            return f
        if op in ("et", "ou"):
            fs = [cc(x) for x in a]
            if op == "et":
                if len(fs) == 2:
                    f0, f1 = fs
                    return lambda V: bool(f0(V) and f1(V))

                def et(V):
                    for f in fs:
                        if not f(V):
                            return False
                    return True
                return et
            if len(fs) == 2:
                f0, f1 = fs
                return lambda V: bool(f0(V) or f1(V))

            def ou(V):
                for f in fs:
                    if f(V):
                        return True
                return False
            return ou
        if op == "non":
            f0 = cc(a[0])
            return lambda V: not f0(V)
        if op in ("=", "!="):
            f0, f1 = cc(a[0]), cc(a[1])
            if hasattr(f1, "cst") and not isinstance(f1.cst[0], dict):
                c = f1.cst[0]
                if op == "=":
                    def eg_c(V):
                        x = f0(V)
                        return (x is c) if isinstance(x, dict) else (x == c)
                    return eg_c

                def ne_c(V):
                    x = f0(V)
                    return not ((x is c) if isinstance(x, dict) else (x == c))
                return ne_c
            if op == "=":
                def eg(V):
                    x, y = f0(V), f1(V)
                    return (x is y) if isinstance(x, dict) or isinstance(y, dict) else (x == y)
                return eg

            def ne(V):
                x, y = f0(V), f1(V)
                return not ((x is y) if isinstance(x, dict) or isinstance(y, dict) else (x == y))
            return ne
        if op in _ARITH:
            f0, f1, o = cc(a[0]), cc(a[1]), _ARITH[op]
            if hasattr(f1, "cst"):
                return _ARITH_C[op](f0, f1.cst[0])
            return lambda V: o(f0(V), f1(V))
        if op == "si":
            f0, f1, f2 = cc(a[0]), cc(a[1]), cc(a[2])
            return lambda V: f1(V) if f0(V) else f2(V)
        if op == "liste":
            fs = [cc(x) for x in a]
            return lambda V: [f(V) for f in fs]
        if op == "longueur":
            f0 = cc(a[0])
            return lambda V: len(f0(V))
        if op == "elem":
            f0, f1 = cc(a[0]), cc(a[1])

            def elem(V):
                v = f0(V)
                return v[f1(V)] if v is not None else None
            return elem
        if op == "premier":
            f0 = cc(a[0])

            def premier(V):
                v = f0(V)
                return v[0] if v else None
            return premier
        if op == "vide":
            f0 = cc(a[0])
            return lambda V: not f0(V)
        if op == "contient":
            f0, f1 = cc(a[0]), cc(a[1])

            def contient(V):
                v, x = f0(V), f1(V)
                return any(e is x for e in v) if isinstance(x, dict) else x in v
            return contient
        if op in ("indice", "suivant"):
            f0, f1 = cc(a[0]), cc(a[1])
            suiv = op == "suivant"

            def indice(V):
                v, x = f0(V), f1(V)
                i = next((i for i, e in enumerate(v) if _identique(e, x)), None)
                if not suiv:
                    return i
                return None if i is None or not v else v[(i + 1) % len(v)]
            return indice
        if op == "table":
            f0, f1 = cc(a[0]), cc(a[1])
            f2 = cc(a[2]) if len(a) > 2 else _const(None)
            return lambda V: f0(V).get(str(f1(V)), f2(V))
        if op in ("tous", "existe", "premier_tel_que", "filtrer"):
            k = self._case(a[0].lstrip("$"))
            fl, fc = cc(a[1]), self.c(a[2], {**P, a[0].lstrip("$"): k})

            def quant(V):
                liste = fl(V) or []
                ancien, ok = V[k], []
                try:
                    for e in liste:  # tous les éléments sont évalués, comme l'interpréteur (pas de court-circuit)
                        V[k] = e
                        if fc(V):
                            ok.append(e)
                finally:
                    V[k] = ancien
                if op == "tous":
                    return len(ok) == len(liste)
                if op == "existe":
                    return bool(ok)
                if op == "premier_tel_que":
                    return ok[0] if ok else None
                return ok
            return quant
        if op == "action":
            return lambda V: V[_ACTION][0]
        if op == "case_clic":
            def case_clic(V):
                _, r, c = V[_ACTION]
                return None if r is None or c is None else Programme._clic_vers_case(V[_SCENE], r, c)
            return case_clic
        if op == "niveau":
            def niveau(V):
                n = getattr(V[_SCENE], "niveau", None)
                return V[_NIVEAU] if n is None else n
            return niveau
        if op == "vue":
            return lambda V: [V[_SCENE].vue[1], V[_SCENE].vue[0]]
        if op == "nom":
            f0 = cc(a[0])
            return lambda V: f0(V).get("nom")
        if op == "pixel":
            f0, f1, f2 = cc(a[0]), cc(a[1]), cc(a[2])

            def pixel(V):
                o, dx, dy = f0(V), f1(V), f2(V)
                px = np.asarray(o["pixels"])
                return int(px[dy, dx]) if 0 <= dy < px.shape[0] and 0 <= dx < px.shape[1] else None
            return pixel
        if op == "etat":
            n = a[0]
            return lambda V: prog.etat.get(n)
        if op == "objets":
            f = a[0] if a else {}
            tag = f.get("tag") if isinstance(f, dict) else None
            if isinstance(tag, str):  # index par tag : sous-suite de sc.sprites dans le même ordre
                pr = _predicat({k: v for k, v in f.items() if k != "tag"})
                return lambda V: [s for s in _par_tag(V[_SCENE], tag) if pr(s)]
            pr = _predicat(f)
            return lambda V: [s for s in V[_SCENE].sprites if pr(s)]
        if op == "a":
            f0, f1 = cc(a[0]), cc(a[1])
            return lambda V: _a(V[_SCENE], f0(V), f1(V))
        if op == "objets_dans_boite":
            fs = [cc(t) for t in a[:4]]
            return lambda V: V[_SCENE].dans_boite(*(f(V) for f in fs))
        if op in ("x", "y"):
            f0 = cc(a[0])
            return lambda V: f0(V)[op]
        if op in ("largeur", "hauteur"):
            f0, d = cc(a[0]), (1 if op == "largeur" else 0)
            return lambda V: np.asarray(f0(V)["pixels"]).shape[d]
        if op == "attr":
            f0, f1 = cc(a[0]), cc(a[1])
            return lambda V: f0(V).get("attrs", {}).get(f1(V))
        if op == "chevauche":
            f0, f1 = cc(a[0]), cc(a[1])

            def chev(V):
                o1, o2 = f0(V), f1(V)
                return o1 is not o2 and _chevauche_px(o1, o2)
            return chev
        if op == "libre":
            f0, f1, f2 = cc(a[0]), cc(a[1]), cc(a[2])
            f = a[3] if len(a) > 3 else {}
            tag = f.get("tag") if isinstance(f, dict) else None
            pr = _predicat({k: v for k, v in f.items() if k != "tag"} if isinstance(tag, str) else f)

            def libre(V):
                o, dx, dy = f0(V), f1(V), f2(V)
                for s in (_par_tag(V[_SCENE], tag) if isinstance(tag, str) else V[_SCENE].sprites):
                    if s is not o and s.get("visible", True) and pr(s) and _chevauche_px(o, s, dx, dy):
                        return False
                return True
            return libre
        if op in TERMES_CANEVAS:  # même code que l'interpréteur (langage.terme_canevas), arguments compilés
            fs = tuple(cc(x) for x in a)
            return lambda V: terme_canevas(V[_SCENE], op, [f(V) for f in fs], V[_ACTION])
        return _leve(f"terme inconnu : {op}")

    # -------------------------------------------------------------- effets
    def _e(self, x, P):
        if not isinstance(x, list) or not x:
            return _leve(f"effet inconnu : {x!r}")
        op, a = x[0], x[1:]
        if op in self.mots or op in self.fonctions:
            return self._appel(op, a, P, "effet")
        prog = self
        if op == "tant_que":
            fc = self.c(a[0], P)
            corps = tuple(self.e(f, P) for f in a[1])
            fm = self.c(a[2], P) if len(a) > 2 else None

            def tant_que(V):
                for _ in range(fm(V) if fm is not None else 64):
                    if not fc(V):
                        break
                    for f in corps:
                        f(V)
            return tant_que
        if op == "refleter":
            fl, axe, fc = self.c(a[0], P), a[1], self.c(a[2], P)

            def refleter(V):
                liste, c = fl(V), fc(V)
                sc = V[_SCENE]
                for o in list(liste if isinstance(liste, list) else [liste]):
                    px = np.asarray(o["pixels"])
                    if axe == "x":
                        sc.creer(dict(o, pixels=np.fliplr(px)), 2 * c - o["x"] - px.shape[1], o["y"])
                    else:
                        sc.creer(dict(o, pixels=np.flipud(px)), o["x"], 2 * c - o["y"] - px.shape[0])
            return refleter
        if op == "soit_creer":
            nv = a[0].lstrip("$")
            k = self._case(nv)
            fm, fx, fy = self.c(a[1], P), self.c(a[2], P), self.c(a[3], P)
            corps = tuple(self.e(f, {**P, nv: k}) for f in (a[4] if len(a) > 4 else []))

            def soit_creer(V):
                modele, x, y = fm(V), fx(V), fy(V)
                if modele is None:
                    return
                n = V[_SCENE].creer(modele, x, y)
                ancien, dep = V[k], V[_DEPILE]
                try:
                    for f in corps:  # chaque effet a sa copie de l'environnement, comme `pour`
                        V[k], V[_DEPILE] = n, dep
                        f(V)
                finally:
                    V[k], V[_DEPILE] = ancien, dep
            return soit_creer
        if op == "instantane":
            f0 = self.c(a[0], P)

            def instantane(V):
                prog.instantanes[f0(V)] = instantane_scene(V[_SCENE], prog.etat)
            return instantane
        if op == "restaurer":
            f0 = self.c(a[0], P)

            def restaurer(V):
                n = f0(V)
                if n in prog.instantanes:
                    prog.etat = restaurer_scene(V[_SCENE], prog.instantanes[n])
            return restaurer
        if op == "pousser":
            f0, f1, f2 = self.c(a[0], P), self.c(a[1], P), self.c(a[2], P)
            n_bl = len(a)

            def pousser(V):
                o, dx, dy = f0(V), f1(V), f2(V)
                bloque = o is not None and prog._ref._pousser(V[_SCENE], o, dx, dy, a[3], a[4] if n_bl > 4 else {})
                if n_bl > 5:
                    prog.etat[a[5]] = bool(bloque)
            return pousser
        if op == "si_alors":
            fc = self.c(a[0], P)
            oui = tuple(self.e(f, P) for f in a[1])
            non = tuple(self.e(f, P) for f in (a[2] if len(a) > 2 else []))

            def si_alors(V):
                for f in (oui if fc(V) else non):
                    f(V)
            return si_alors
        if op == "pour":
            k = self._case(a[0].lstrip("$"))
            fl = self.c(a[1], P)
            corps = tuple(self.e(f, {**P, a[0].lstrip("$"): k}) for f in a[2])

            def pour(V):
                ancien, dep = V[k], V[_DEPILE]
                try:
                    for v in list(fl(V) or []):
                        for f in corps:  # l'interpréteur donne à CHAQUE effet du corps sa copie de l'environnement
                            V[k], V[_DEPILE] = v, dep
                            f(V)
                finally:
                    V[k], V[_DEPILE] = ancien, dep
            return pour
        if op == "poser":
            n, f0 = a[0], self.c(a[1], P)

            def poser(V):
                prog.etat[n] = f0(V)
            return poser
        if op == "empiler":
            n, f0 = a[0], self.c(a[1], P)

            def empiler(V):
                prog.etat.setdefault(n, []).append(copy.deepcopy(f0(V)))
            return empiler
        if op == "depiler":
            n = a[0]

            def depiler(V):
                pile = prog.etat.get(n) or []
                V[_DEPILE] = pile.pop() if pile else None
            return depiler
        if op == "consommer":
            n, f0 = a[0], self.c(a[1], P)

            def consommer(V):
                prog.etat[n] = (prog.etat.get(n) or 0) - f0(V)
            return consommer
        if op == "recharger":
            n, f0, f1 = a[0], self.c(a[1], P), self.c(a[2], P)

            def recharger(V):
                v = f0(V)
                _recharger(prog.etat, n, v, f1(V))
            return recharger
        if op == "poser_attr":
            f0, f1, f2 = (self.c(t, P) for t in a[:3])

            def poser_attr(V):
                f0(V).setdefault("attrs", {})[f1(V)] = f2(V)  # même ordre d'évaluation (valeur d'abord)
            return poser_attr
        if op in ("niveau_suivant", "gagner", "perdre"):
            return lambda V: getattr(V[_SCENE], op)()
        if op in _EFFETS_SCENE:
            fs = tuple(self.c(t, P) for t in a)
            if op == "deplacer" and len(fs) == 3:
                f0, f1, f2 = fs

                def deplacer(V):
                    s, dx, dy = f0(V), f1(V), f2(V)
                    if s is not None:
                        s["x"], s["y"] = s["x"] + dx, s["y"] + dy
                return deplacer
            if op == "ecrire" and len(fs) == 4:
                f0, f1, f2, f3 = fs

                def ecrire(V):
                    s, dy, dx, c = f0(V), f1(V), f2(V), f3(V)
                    if s is not None:
                        s["pixels"] = s["pixels"].copy()  # copie à l'écriture : `cloner` partage les pixels
                        s["pixels"][dy, dx] = c
                return ecrire
            if op == "montrer" and len(fs) == 2:
                f0, f1 = fs

                def montrer(V):
                    s, b = f0(V), f1(V)
                    if s is not None:
                        s["visible"] = b
                return montrer

            def effet(V):
                args = [f(V) for f in fs]
                if args and args[0] is None:
                    return
                getattr(V[_SCENE], op)(*args)
            return effet
        return _leve(f"effet inconnu : {op}")

    # -------------------------------------------------------------- un coup
    def step(self, scene, action, niveau=0):
        debut = bool(getattr(scene, "debut", False))
        scene.debut = False
        V = self._V
        V[_SCENE], V[_ACTION], V[_NIVEAU], V[_DEBUT] = scene, action, niveau, debut
        if debut:  # section au_debut : chaque effet avec sa copie de l'environnement de départ
            for f in self._au_debut:
                V[_DEPILE] = _LIBRE
                f(V)
        if not self._lois:
            for soit, quand, alors, stop in self._regles:
                V[_DEPILE] = _LIBRE
                for k, f in soit:
                    V[k] = f(V)
                if not quand(V):
                    continue
                for f in alors:
                    f(V)
                if stop:
                    break
            return
        for ph in sorted({r[2][3] for r in self._regles}):  # = Programme.step : phases croissantes
            a_faire = []  # mode « lois » : conditions jugées sur l'état laissé par les phases précédentes
            for soit, quand, alors, _ in self._regles:
                if alors[3] != ph:
                    continue
                V[_DEPILE] = _LIBRE
                for k, f in soit:
                    V[k] = f(V)
                if quand(V):
                    a_faire.append((alors, V[:]))
            pris = {}
            for (effets, w, nom, _ph), Vr in sorted(a_faire, key=lambda x: -x[0][1]):
                for f, cle, op in effets:
                    k = cle(Vr) if cle is not None else None
                    if k is not None and pris.get(k, w) > w:
                        self.conflits.append((nom, op, pris[k], w))
                        continue
                    if k is not None:
                        pris[k] = max(w, pris.get(k, w))
                    f(Vr)


# ------------------------------------------------------------------ rendu et copie d'état
def _agrandir(dest, vue, k):
    """dest (vue de h*k × w*k) ← chaque case de vue en bloc k×k : une seule copie par diffusion (= np.repeat ×2)."""
    h, w = vue.shape
    dest.reshape(h, k, w, k)[...] = vue[:, None, :, None]


def image(sc):
    """= `sc.image()` (rendu `ontologie_exec.rendre` des sprites visibles), bit à bit."""
    h, w = sc.vue
    vue = np.full((h, w), sc.fond, dtype=np.int16)
    cx, cy = sc.camera
    vis = [s for s in sc.sprites if s["visible"]]
    vis.sort(key=lambda s: s["couche"])
    for s in vis:
        px = s["pixels"]
        if not isinstance(px, np.ndarray) or px.dtype != np.int16:
            px = np.asarray(px, dtype=np.int16)
        sh, sw = px.shape
        rx, ry = s["x"] - cx, s["y"] - cy
        x0, x1, y0, y1 = max(0, rx), min(w, rx + sw), max(0, ry), min(h, ry + sh)
        if x1 <= x0 or y1 <= y0:
            continue
        reg = px[y0 - ry:y1 - ry, x0 - rx:x1 - rx]
        np.copyto(vue[y0:y1, x0:x1], reg, where=reg >= 0)
    k = min(64 // w, 64 // h)
    gy, gx = (64 - h * k) // 2, (64 - w * k) // 2
    if k == 1 and h == 64 and w == 64:
        return vue
    out = np.full((64, 64), sc.letterbox, dtype=np.int16)
    if k > 1:
        _agrandir(out[gy:gy + h * k, gx:gx + w * k], vue, k)
    else:
        out[gy:gy + h, gx:gx + w] = vue
    return out


def image_complete(sc):
    """= `sc.image_complete()` : image des sprites puis canevas par-dessus (même code de dessin)."""
    im = image(sc)
    return dessiner_canevas(im if im.dtype == np.int16 else im.astype(np.int16), getattr(sc, "canevas", None))


def _copie(v, memo):
    i = id(v)
    if i in memo:
        return memo[i]
    t = type(v)
    if t is dict:
        n = memo[i] = {}
        for k, x in v.items():
            n[k] = _copie(x, memo)
        return n
    if t is list:
        n = memo[i] = []
        n.extend(_copie(x, memo) for x in v)
        return n
    if t is np.ndarray:
        n = memo[i] = v.copy()
        return n
    if t in (int, float, str, bool, type(None)):
        return v
    n = memo[i] = copy.deepcopy(v)
    return n


def cloner(scene, etat):
    """Copie profonde de (scène, état caché) gardant les identités, comme `copy.deepcopy((scene, etat))` ; les tags
    (jamais modifiés par un effet) sont partagés, et les PIXELS aussi : tout effet qui écrit dans les pixels d'un sprite
    les recopie d'abord (copie à l'écriture : `ecrire`, `recolorer`, `Scene.ecrire`). CW-254 : la clé de recherche
    (`plan_langage._gel`, cache par identité du tableau) ne refait plus `tobytes` pour les sprites inchangés."""
    memo, sprites = {}, []
    for s in scene.sprites:
        n = dict(s)
        memo[id(s)] = n
        sprites.append(n)
    for s, n in zip(scene.sprites, sprites, strict=True):
        for k, v in s.items():
            if k not in ("pixels", "tags", "nom", "x", "y", "couche", "visible", "bloquant"):
                n[k] = _copie(v, memo)
    nouv = Scene.__new__(Scene)
    nouv.__dict__.update(scene.__dict__)
    nouv.sprites = sprites
    if "canevas" in scene.__dict__:  # canevas copiés (identités gardées : l'état caché peut désigner un canevas)
        nouv.canevas = []
        for c in scene.canevas:
            n = memo[id(c)] = dict(c, pixels=c["pixels"].copy())
            nouv.canevas.append(n)
    c = scene.__dict__.get("_index_tags")
    if c is not None and c[0] is scene.sprites and c[1] == len(sprites):  # index recopié plutôt que refait
        nouv._index_tags = (sprites, len(sprites), {t: [memo[id(s)] for s in lst] for t, lst in c[2].items()})
    else:
        nouv.__dict__.pop("_index_tags", None)
    return nouv, _copie(etat, memo)
