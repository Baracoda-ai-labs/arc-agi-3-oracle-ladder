# SPDX-License-Identifier: MIT-0
"""[G] CW-291 — simulateur plus rapide pour la recherche, MÊMES résultats que `sim_rapide` + `plan_langage.cle_complete`.
Étape 1 (copie et clé, 42 % du temps sur g50t N1, CCM-011-E) :
- `cloner(scene, etat)` = `sim_rapide.cloner` (mêmes identités : un objet de l'état caché qui désigne un sprite ou son `cache`
  désigne la copie), sans la récursion générique : champs atomiques laissés à `dict(s)`, dict d'atomes copiés en ligne.
- `cle_complete(sc, etat)` = `plan_langage.cle_complete`, MÊME VALEUR (même tuple haché) : le gel d'un sprite est fait
  par une fonction générée une fois par jeu de clés de sprite (pas de boucle ni de tri des clés à chaque nœud).
Interrupteur : `CHRYS_BACKEND_TABLEAUX=1` puis `installer()` remplace ces deux fonctions là où la recherche les prend
(`sim_rapide.cloner`, `plan_langage.cle_complete`, et les modules déjà importés qui les ont copiées). Allumé par défaut depuis CW-304 ; `CHRYS_BACKEND_TABLEAUX=0` : rien ne change."""
import copy
import os
import sys

import numpy as np

from chrysalide.arc3 import sim_rapide as sr
from chrysalide.arc3.langage import PROF_MAX, ErreurLangage
from chrysalide.arc3.logique import plan_langage as _pl
from chrysalide.arc3.logique.plan_langage import _GELES, _TAGS, _gel
from chrysalide.arc3.ontologie_exec import Scene
from chrysalide.arc3.sim_rapide import ProgrammeCompile

NIVEAU = os.environ.get("CHRYS_BACKEND_TABLEAUX", "1")  # allumé par défaut (CW-304) ; "0" éteint ; "2" : clé plate
ACTIF = NIVEAU in ("1", "2")
_ATOMES = frozenset((int, float, str, bool, type(None)))
_PARTAGES = frozenset(("pixels", "tags", "nom", "x", "y", "couche", "visible", "bloquant"))  # = sim_rapide.cloner


# ------------------------------------------------------------------ copie
_SANS = object()


def _copie_r(v, memo):
    """= `sim_rapide._copie(v, memo)` (mêmes objets, mêmes partages) ; une liste ou un dict d'atomes est copié d'un coup."""
    t = type(v)
    if t in _ATOMES:
        return v
    i = id(v)
    m = memo.get(i, _SANS)
    if m is not _SANS:
        return m
    if t is list:
        if _ATOMES.issuperset(map(type, v)):
            m = memo[i] = v.copy()
            return m
        n = memo[i] = []
        n.extend(_copie_r(x, memo) for x in v)
        return n
    if t is dict:
        if _ATOMES.issuperset(map(type, v.values())):
            m = memo[i] = v.copy()
            return m
        n = memo[i] = {}
        for k, x in v.items():
            n[k] = _copie_r(x, memo)
        return n
    if t is np.ndarray:
        m = memo[i] = v.copy()
        return m
    m = memo[i] = copy.deepcopy(v)
    return m


def cloner(scene, etat):
    """= `sim_rapide.cloner(scene, etat)` (même graphe d'objets, mêmes partages)."""
    memo, sprites, a_copier = {}, [], []
    for s in scene.sprites:
        n = dict(s)
        memo[id(s)] = n
        sprites.append(n)
        for k, v in s.items():
            if type(v) not in _ATOMES and k not in _PARTAGES:
                a_copier.append((n, k, v))
    for n, k, v in a_copier:  # après l'enregistrement de TOUS les sprites, comme sim_rapide.cloner
        n[k] = _copie_r(v, memo)
    nouv = Scene.__new__(Scene)
    nouv.__dict__.update(scene.__dict__)
    nouv.sprites = sprites
    if "canevas" in scene.__dict__:
        nouv.canevas = []
        for c in scene.canevas:
            n = memo[id(c)] = dict(c, pixels=c["pixels"].copy())
            nouv.canevas.append(n)
    c = scene.__dict__.get("_index_tags")
    if c is not None and c[0] is scene.sprites and c[1] == len(sprites):
        nouv._index_tags = (sprites, len(sprites), {t: [memo[id(s)] for s in lst] for t, lst in c[2].items()})
    else:
        nouv.__dict__.pop("_index_tags", None)
    return nouv, _copie_r(etat, memo)


# ------------------------------------------------------------------ clé
def _gel_px(v):
    """= `_gel(tableau)` (même cache `_GELES` que plan_langage)."""
    g = _GELES.get(id(v))
    if g is None or g[0] is not v:
        if len(_GELES) > 200000:
            _GELES.clear()
        g = _GELES[id(v)] = (v, (v.shape, v.tobytes()))
    return g[1]


def _gel_tags(v):
    if type(v) is not list:
        return _gel(v)
    g = _TAGS.get(id(v))
    if g is None or g[0] is not v:
        if len(_TAGS) > 200000:
            _TAGS.clear()
        g = _TAGS[id(v)] = (v, _gel(v))
    return g[1]


_GENERES = {}  # frozenset des clés d'un sprite → (fonction de gel générée, clés toutes str)
_STR = frozenset((str,))
_AUCUN = {}


def _gel_r(v, M=_AUCUN):
    """= `_gel(v)`, même valeur ; listes et dicts d'atomes gelés d'un coup ; les sprites de la scène déjà gelés (`M` :
    id → gel) ne sont pas regelés."""
    t = type(v)
    if t in _ATOMES:
        return v
    if t is list or t is tuple:
        if _ATOMES.issuperset(map(type, v)):
            return tuple(v)
        return tuple([x if type(x) in _ATOMES else _gel_r(x, M) for x in v])
    if t is dict:
        g = M.get(id(v))
        if g is not None:
            return g
        if _STR.issuperset(map(type, v)):  # clés uniques : trier les paires = trier les clés (comme _gel)
            if _ATOMES.issuperset(map(type, v.values())):
                return tuple(sorted(v.items()))
            return tuple(sorted([(k, x if type(x) in _ATOMES else _gel_r(x, M)) for k, x in v.items()]))
        return tuple(sorted([(k if type(k) is str else str(k), _gel_r(x, M)) for k, x in v.items()]))
    return _gel(v)


def _generer(ks):
    """Fonction `o → _gel_sprite(o)` en ligne droite pour les sprites de clés `ks` (même tuple, champ par champ)."""
    if not _STR.issuperset(map(type, ks)):
        return _pl._gel_sprite
    lignes = []
    for i, k in enumerate(sorted(ks, key=str)):  # même ordre que plan_langage._gel_sprite
        lignes.append(f"    v{i} = o[{k!r}]")
        if k == "pixels":
            lignes.append(f"    v{i} = v{i} if type(v{i}) in A else (px(v{i}) if type(v{i}) is nd else gel(v{i}))")
        elif k == "tags":
            lignes.append(f"    v{i} = v{i} if type(v{i}) in A else tg(v{i})")
        else:
            lignes.append(f"    v{i} = v{i} if type(v{i}) in A else gd(v{i})")
    corps = ", ".join(f"({k!r}, v{i})" for i, k in enumerate(sorted(ks, key=str)))
    src = "def g(o):\n" + "\n".join(lignes) + f"\n    return ({corps},)\n"
    ns = {"A": _ATOMES, "px": _gel_px, "tg": _gel_tags, "gel": _gel, "gd": _gel_r, "nd": np.ndarray}
    exec(compile(src, f"<gel {sorted(ks, key=str)}>", "exec"), ns)  # noqa: S102 — source générée ici, noms de clés repr()
    return ns["g"]


def _gen(ks):
    """→ (fonction de gel, clés toutes str : alors gel du sprite = `_gel(sprite)`, réutilisable dans l'état caché)."""
    e = _GENERES.get(ks)
    if e is None:
        e = _GENERES[ks] = (_generer(ks), _STR.issuperset(map(type, ks)))
    return e


def gel_sprite(o):
    return _gen(frozenset(o))[0](o)


def cle_complete(sc, etat):
    """= `plan_langage.cle_complete(sc, etat)`, même valeur."""
    d = sc.__dict__
    cam, cv, don = d["camera"], d.get("canevas"), d.get("donnees")
    gels, M = [], {}
    for o in sc.sprites:
        f, ok = _gen(frozenset(o))
        x = f(o)
        gels.append(x)
        if ok:
            M[id(o)] = x
    return hash((tuple(sorted(gels, key=hash)),
                 cam if type(cam) in _ATOMES else _gel(cam), cv if type(cv) in _ATOMES else _gel(cv),
                 don if type(don) in _ATOMES else _gel(don), sc.issue, _gel_r(etat or {}, M)))



_PLATS = {}  # frozenset des clés d'un sprite → fonction de gel PLAT générée


def _generer_plat(ks):
    """o → (n° du jeu de clés, v1, …, vn) : un seul tuple, champs dans l'ordre des clés, gelés comme `_gel`."""
    cles = sorted(ks, key=str)
    lignes = []
    for i, k in enumerate(cles):
        lignes.append(f"    v{i} = o[{k!r}]")
        if k == "pixels":
            lignes.append(f"    v{i} = v{i} if type(v{i}) in A else (px(v{i}) if type(v{i}) is nd else gel(v{i}))")
        elif k == "tags":
            lignes.append(f"    v{i} = v{i} if type(v{i}) in A else tg(v{i})")
        else:
            lignes.append(f"    v{i} = v{i} if type(v{i}) in A else gd(v{i})")
    src = "def g(o):\n" + "\n".join(lignes) + f"\n    return ({len(_PLATS)}, {', '.join(f'v{i}' for i in range(len(cles)))})\n"
    ns = {"A": _ATOMES, "px": _gel_px, "tg": _gel_tags, "gel": _gel, "gd": _gel_r, "nd": np.ndarray}
    exec(compile(src, f"<gel plat {cles}>", "exec"), ns)  # noqa: S102
    return ns["g"]


def cle_plate(sc, etat):
    """Clé de MÊMES CLASSES que `cle_complete` (deux états ont la même clé ssi mêmes sprites à l'ordre près, même caméra,
    canevas, données, issue, état caché — aux collisions de hachage 64 bits près, comme cle_complete), mais PAS la même
    valeur : un tuple plat par sprite, haché une seule fois, hachages triés. `CHRYS_BACKEND_TABLEAUX=2` seulement."""
    d = sc.__dict__
    cam, cv, don = d["camera"], d.get("canevas"), d.get("donnees")
    hs, M = [], {}
    for o in sc.sprites:
        ks = frozenset(o)
        f = _PLATS.get(ks)
        if f is None:
            f = _PLATS[ks] = _generer_plat(ks)
        x = f(o)
        hs.append(hash(x))
        M[id(o)] = x
    hs.sort()
    return hash((tuple(hs), cam if type(cam) in _ATOMES else _gel(cam), cv if type(cv) in _ATOMES else _gel(cv),
                 don if type(don) in _ATOMES else _gel(don), sc.issue, _gel_r(etat or {}, M)))


# ------------------------------------------------------------------ règles : termes traduits en source Python
class _NonCouvert(Exception):
    pass


_ERREURS_COMPIL = (IndexError, KeyError, TypeError, AttributeError, ValueError)  # = ProgrammeCompile.c
_LIEURS = {"tous", "existe", "premier_tel_que", "filtrer", "argmin", "argmax"}
_COUVERTS = {"et", "ou", "non", "=", "!=", "<", "<=", ">", ">=", "+", "-", "*", "//", "%", "si", "liste", "longueur", "elem",
             "premier", "vide", "contient", "etat", "action", "x", "y", "largeur", "hauteur", "attr", "objets", "nom",
             "chevauche", "a", "a_tag", "visible", "bloquant", "calque", "tags", "attr_cache", "echelle", "debut_niveau",
             "intervalle", "epuise", "utilise", "pixel", *_LIEURS}  # tous PURS : un terme ne modifie ni scène ni état
_CHERS = {"objets", "a", "intervalle", "pixel", *_LIEURS}
_JAMAIS_DICT = {"et", "ou", "non", "vide", "=", "!=", "<", "<=", ">", ">=", "+", "-", "*", "//", "%", "longueur", "contient",
                "tous", "existe", "filtrer", "liste", "intervalle", "objets", "a", "largeur", "hauteur", "pixel", "a_tag",
                "visible", "bloquant", "utilise", "debut_niveau", "epuise", "chevauche", "tags"}  # bool, nombre ou liste
_PROF_DEF = 25  # au-delà, le sous-terme devient sa propre fonction (limite d'imbrication du compilateur Python)
_EFFETS_COUVERTS = {"si_alors", "pour", "poser", "consommer", "empiler", "depiler", "poser_attr", "niveau_suivant", "gagner",
                    "perdre", *sr._EFFETS_SCENE}
_BLOCS_MAX = 14  # Python refuse plus de 20 blocs imbriqués
_U = object()  # valeur sortie de boucle pas encore calculée


def _contient(v, x):
    return any(e is x for e in v) if isinstance(x, dict) else x in v


def _a_tag(o, t):
    return o is not None and t in o.get("tags", ())


_LISTES = {}  # id(pixels) → (tableau, lignes en listes Python, h, w) ; sûr pour la même raison que sim_rapide._COULEURS


def _pixel(o, dx, dy):
    """= `pixel` de sim_rapide ; tableau 2-D entier : lecture dans sa copie en listes (cache par identité)."""
    px = o["pixels"]
    g = _LISTES.get(id(px))
    if g is None or g[0] is not px or type(dx) is not int or type(dy) is not int:
        if type(px) is not np.ndarray or px.ndim != 2 or px.dtype.kind not in "iu" or type(dx) is not int \
                or type(dy) is not int:
            px = np.asarray(px)
            return int(px[dy, dx]) if 0 <= dy < px.shape[0] and 0 <= dx < px.shape[1] else None
        if len(_LISTES) > 200000:
            _LISTES.clear()
        g = _LISTES[id(px)] = (px, px.tolist(), px.shape[0], px.shape[1])
    return g[1][dy][dx] if 0 <= dy < g[2] and 0 <= dx < g[3] else None


class ProgrammeGenere(ProgrammeCompile):
    """= `ProgrammeCompile` (même interface, mêmes effets, même ordre d'évaluation), mais chaque terme couvert est traduit
    en UNE expression Python (variables = cases de V, comme sim_rapide) compilée par `compile` : plus d'appel de fermeture
    par sous-terme. Terme non couvert, mot, fonction, constante ou nœud mal formé → fermeture de `ProgrammeCompile`,
    appelée depuis le code généré.
    Sortie de boucle : dans le corps d'un quantificateur, un sous-terme coûteux qui ne lit pas la variable de boucle est
    calculé à sa PREMIÈRE utilisation puis gardé pour les éléments suivants (les termes sont purs et la scène ne change pas
    pendant un terme : même valeur ; même exception, levée au même moment). `self.genere` = termes traduits,
    `self.sorties` = sous-termes sortis de boucle, `self.sources` = sources (diagnostic)."""

    def __init__(self, texte):
        self._ns = {"np": np, "nd": np.ndarray, "_par_tag": sr._par_tag, "_couleurs": sr._couleurs,
                    "_filtre": sr._filtre, "_chev": sr._chevauche_px, "_a": sr._a, "_contient": _contient,
                    "_a_tag": _a_tag, "_pixel": _pixel, "_VIDE": {}, "_U": _U, "ErreurLangage": ErreurLangage, "copy": copy}
        self._n, self.genere, self.sorties, self.sources = 0, 0, 0, []
        self._ns["prog"] = self
        self._M = self._ns["_M"] = {}
        super().__init__(texte)

    def _nom(self, prefixe, objet):
        self._n += 1
        n = f"{prefixe}{self._n}"
        self._ns[n] = objet
        return n

    def _tmp(self, prefixe="_t"):
        self._n += 1
        return f"{prefixe}{self._n}"

    def _exec(self, nom, src):
        exec(compile(src, f"<G {nom}>", "exec"), self._ns)  # noqa: S102 — source générée depuis l'arbre du programme
        self.sources.append(src)
        return self._ns[nom]

    def c(self, t, P):
        if not (isinstance(t, list) and t and isinstance(t[0], str)) or t[0] in self.mots or t[0] in self.fonctions \
                or t[0] not in _COUVERTS:
            return ProgrammeCompile.c(self, t, P)
        try:
            src = self._x(t, P, 0, None)
        except _NonCouvert:
            return ProgrammeCompile.c(self, t, P)
        return self._def(src)

    def _def(self, expr):
        nom = self._tmp("T")
        self.genere += 1
        return self._exec(nom, f"def {nom}(V):\n    return {expr}\n")

    def _appel(self, op, a, P, sorte):
        """= `ProgrammeCompile._appel` pour un mot (macro) bien employé : une fonction en ligne droite par site d'appel
        (même ordre : profondeur vérifiée, arguments évalués, paramètres sauvés puis liés, corps, restauration)."""
        d = self.mots.get(op)
        if op in self.fonctions or d is None or d.get("sorte", "terme") != sorte \
                or len(a) != len(d.get("params", [])):
            return ProgrammeCompile._appel(self, op, a, P, sorte)
        ps = d.get("params", [])
        args = [self._x(u, P, 0, None) for u in a]
        ks = [self._case(p[1:]) for p in ps]
        if op not in self._corps:
            Pm = dict(zip((p[1:] for p in ps), ks, strict=True))
            self._corps[op] = self.c(d["corps"], Pm) if sorte == "terme" else tuple(self.e(x, Pm) for x in d["corps"])
        corps = self._corps[op]
        nom = self._tmp("C")
        msg = self._nom("K", f"mot {op!r} : profondeur d'appel > {PROF_MAX}")
        L = [f"def {nom}(V):", f"    if prog._prof >= {PROF_MAX}:", f"        raise ErreurLangage({msg})"]
        L += [f"    v{i} = {s}" for i, s in enumerate(args)]
        L += [f"    o{i} = V[{k}]" for i, k in enumerate(ks)] + ["    dep = V[3]"]
        L += [f"    V[{k}] = v{i}" for i, k in enumerate(ks)] + ["    prog._prof += 1", "    try:"]
        if sorte == "terme":
            L.append(f"        return {self._nom('B', corps)}(V)")
        else:
            L += [ln for f in corps for ln in (f"        {self._nom('B', f)}(V)", "        _M.clear()")]
            L.append("        return None")
        L += ["    finally:", "        prog._prof -= 1"] + [f"        V[{k}] = o{i}" for i, k in enumerate(ks)]
        L.append("        V[3] = dep")
        return self._exec(nom, "\n".join(L) + "\n")

    # -------------------------------------------------------------- effets : instructions Python
    def e(self, x, P):
        """Tout effet (couvert ou non) passe par une fonction générée qui vide la mémoire des `objets` avant et après."""
        nom = self._tmp("E")
        lignes = self._s(x, P, 1, 0)
        return self._exec(nom, f"def {nom}(V):\n    _M.clear()\n" + "\n".join(lignes) + "\n")

    # mémoire des `objets(filtre)` d'un coup : vidée au début du coup, au début et après chaque effet (seuls les effets
    # changent la scène) ; chaque lecture rend une COPIE de la liste (même identité que sim_rapide : liste neuve à chaque appel)
    def step(self, scene, action, niveau=0):
        self._M.clear()
        return ProgrammeCompile.step(self, scene, action, niveau)

    def distance(self, regle):
        f, M = ProgrammeCompile.distance(self, regle), self._M

        def distance(scene, etat):
            M.clear()
            return f(scene, etat)
        return distance

    def ev(self, t, env):
        self._M.clear()
        return ProgrammeCompile.ev(self, t, env)

    def fait(self, e, env):
        self._M.clear()
        return ProgrammeCompile.fait(self, e, env)

    def _s(self, x, P, ind, blocs):
        """Instructions de l'effet x (indentation `ind`, `blocs` blocs Python déjà ouverts) ; effet non couvert ou mal
        formé → appel de la fermeture de ProgrammeCompile (qui le délègue à l'interpréteur s'il est mal formé)."""
        sp = "    " * ind
        if not (isinstance(x, list) and x and isinstance(x[0], str)) or x[0] not in _EFFETS_COUVERTS \
                or x[0] in self.mots or x[0] in self.fonctions:
            return [f"{sp}{self._nom('F', ProgrammeCompile.e(self, x, P))}(V)", f"{sp}_M.clear()"]
        if blocs >= _BLOCS_MAX:  # limite de blocs imbriqués de Python : sous-fonction
            return [f"{sp}{self._nom('F', self.e(x, P))}(V)", f"{sp}_M.clear()"]
        try:
            L = self._s_op(x[0], x[1:], P, ind, blocs)
        except _ERREURS_COMPIL:
            return [f"{sp}{self._nom('F', ProgrammeCompile.e(self, x, P))}(V)", f"{sp}_M.clear()"]
        return L if x[0] in ("si_alors", "pour") else [*L, f"{sp}_M.clear()"]

    def _s_op(self, op, a, P, ind, blocs):
        sp = "    " * ind
        x = lambda u: self._x(u, P, 0, None)  # pas de sortie de boucle entre des effets (ils modifient l'état)
        if op == "si_alors":
            c = x(a[0])
            oui = [ln for f in a[1] for ln in self._s(f, P, ind + 1, blocs + 1)] or [f"{sp}    pass"]
            non = [ln for f in (a[2] if len(a) > 2 else []) for ln in self._s(f, P, ind + 1, blocs + 1)]
            return [f"{sp}if {c}:", *oui] + ([f"{sp}else:", *non] if non else [])
        if op == "pour":
            nv = a[0].lstrip("$")
            k = self._case(nv)
            sl = x(a[1])
            Pc = {**P, nv: k}
            corps = [self._s(f, Pc, ind + 2, blocs + 2) for f in a[2]]
            anc, dep, v = self._tmp("_anc"), self._tmp("_dep"), self._tmp("_v")
            L = [f"{sp}{anc}, {dep} = V[{k}], V[3]", f"{sp}try:", f"{sp}    for {v} in list({sl} or []):"]
            for c in corps:  # chaque effet du corps a sa copie de l'environnement, comme sim_rapide
                L += [f"{sp}        V[{k}], V[3] = {v}, {dep}", *c]
            if not corps:
                L.append(f"{sp}        pass")
            return [*L, f"{sp}finally:", f"{sp}    V[{k}], V[3] = {anc}, {dep}"]
        if op == "poser":
            return [f"{sp}prog.etat[{self._nom('K', a[0])}] = {x(a[1])}"]
        if op == "consommer":
            n = self._nom("K", a[0])
            return [f"{sp}prog.etat[{n}] = (prog.etat.get({n}) or 0) - ({x(a[1])})"]
        if op == "empiler":
            return [f"{sp}prog.etat.setdefault({self._nom('K', a[0])}, []).append(copy.deepcopy({x(a[1])}))"]
        if op == "depiler":
            p = self._tmp("_p")
            return [f"{sp}{p} = prog.etat.get({self._nom('K', a[0])}) or []", f"{sp}V[3] = {p}.pop() if {p} else None"]
        if op == "poser_attr":
            s0, s1, s2 = x(a[0]), x(a[1]), x(a[2])
            return [f"{sp}({s0}).setdefault('attrs', {{}})[{s1}] = {s2}"]  # même ordre : valeur, objet, clé
        if op in ("niveau_suivant", "gagner", "perdre"):
            return [f"{sp}V[0].{op}()"]
        ts = [self._tmp("_e") for _ in a]
        L = [f"{sp}{t} = {x(u)}" for t, u in zip(ts, a, strict=True)]
        if op == "deplacer" and len(a) == 3:
            s, dx, dy = ts
            return [*L, f"{sp}if {s} is not None:", f"{sp}    {s}['x'], {s}['y'] = {s}['x'] + {dx}, {s}['y'] + {dy}"]
        if op == "ecrire" and len(a) == 4:
            s, dy, dx, c = ts
            return [*L, f"{sp}if {s} is not None:", f"{sp}    {s}['pixels'] = {s}['pixels'].copy()",
                    f"{sp}    {s}['pixels'][{dy}, {dx}] = {c}"]
        if op == "montrer" and len(a) == 2:
            s, b = ts
            return [*L, f"{sp}if {s} is not None:", f"{sp}    {s}['visible'] = {b}"]
        if not ts:
            return [f"{sp}V[0].{op}()"]
        return [*L, f"{sp}if {ts[0]} is not None:", f"{sp}    V[0].{op}({', '.join(ts)})"]

    def _ferm(self, t, P):
        """Sous-terme laissé à ProgrammeCompile (sa fermeture est appelée depuis le code généré)."""
        return f"{self._nom('F', ProgrammeCompile.c(self, t, P))}(V)"

    # -------------------------------------------------------------- analyse : cases lues, coût
    def _libres(self, t, P):
        """Cases de V lues par le terme (contexte du coup exclu : fixe pendant un coup) ; None si inconnu (fermeture)."""
        try:
            if isinstance(t, str) and t.startswith("$"):
                n = t[1:]
                return frozenset((P[n],)) if n in P else (frozenset() if n in sr._CTX else None)
            if not isinstance(t, list) or not t or not isinstance(t[0], str):
                return frozenset()
            op, a = t[0], t[1:]
            if op in self.mots or op in self.fonctions or op not in _COUVERTS:
                return None
            if op in ("etat", "objets", "action", "debut_niveau"):
                return frozenset()
            if op == "epuise":
                return self._libres(a[1], P) if len(a) > 1 else frozenset()
            if op in _LIEURS:
                nv = a[0].lstrip("$")
                k = self._case(nv)
                l1, l2 = self._libres(a[1], P), self._libres(a[2], {**P, nv: k})
                return None if l1 is None or l2 is None else l1 | (l2 - {k})
            out = frozenset()
            for u in a:
                lu = self._libres(u, P)
                if lu is None:
                    return None
                out |= lu
            return out
        except _ERREURS_COMPIL:
            return None

    def _jamais_dict(self, t):
        """Vrai si la valeur du terme ne peut pas être un dict (ni un sprite) : constante non dict, ou opérateur couvert
        dont le résultat est un booléen, un nombre, une chaîne ou une liste."""
        if isinstance(t, str) and t.startswith("$"):
            return False
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            return type(t) in (int, float, str, bool, type(None), list)
        return t[0] in _JAMAIS_DICT and t[0] not in self.mots and t[0] not in self.fonctions

    def _cout(self, t):
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            return 0
        return (100 if t[0] in _CHERS else 1) + sum(self._cout(u) for u in t[1:])

    # -------------------------------------------------------------- génération
    def _x(self, t, P, prof, ctx):
        """Source de l'expression du terme t (portée P : nom → case de V). ctx = (case de la variable de boucle, liste des
        sorties de boucle) quand t est dans le corps d'un quantificateur généré, sinon None."""
        if isinstance(t, str) and t.startswith("$"):
            n = t[1:]
            if n in P:
                return f"V[{P[n]}]"
            if n in sr._CTX:
                return f"V[{sr._CTX[n]}]"
            return self._ferm(t, P)
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            if type(t) in (int, bool) or t is None:
                return repr(t)
            return self._nom("K", t)  # même objet (identité gardée, comme _const)
        op = t[0]
        if op in self.mots or op in self.fonctions or op not in _COUVERTS:
            return self._ferm(t, P)
        if ctx is not None and self._cout(t) >= 4:
            lib = self._libres(t, P)
            if lib is not None and ctx[0] not in lib:
                h = self._tmp("_h")
                ctx[1].append(h)
                self.sorties += 1
                return f"({h} if {h} is not _U else ({h} := {self._x(t, P, prof, None)}))"
        if prof >= _PROF_DEF:
            return f"{self._nom('G', self._def(self._x(t, P, 0, None)))}(V)"
        try:
            return self._op(op, t[1:], P, prof + 1, ctx)
        except _ERREURS_COMPIL:  # nœud mal formé : ProgrammeCompile le délègue à l'interpréteur, comme avant
            return self._ferm(t, P)

    def _boucle(self, op, a, P, prof, ctx):
        """Quantificateur ou argmin/argmax : fonction générée (liste évaluée par l'appelant, comme sim_rapide : avant la
        boucle), corps avec ses propres sorties de boucle."""
        nv = a[0].lstrip("$")
        k = self._case(nv)
        sl = self._x(a[1], P, prof, ctx)
        sorties = []
        corps = self._x(a[2], {**P, nv: k}, 0, (k, sorties))
        nom = self._tmp("Q")
        init = "".join(f"    {h} = _U\n" for h in sorties)
        if op in ("argmin", "argmax"):
            cmp = "<" if op == "argmin" else ">"
            src = (f"def {nom}(V, l0):\n    meilleur = cle = None\n    ancien = V[{k}]\n{init}    try:\n"
                   f"        for e in l0 or []:\n            V[{k}] = e\n            x = {corps}\n"
                   f"            if cle is None or x {cmp} cle:\n                meilleur, cle = e, x\n"
                   f"    finally:\n        V[{k}] = ancien\n    return meilleur\n")
        else:
            fin = {"tous": "len(ok) == len(liste)", "existe": "bool(ok)", "premier_tel_que": "ok[0] if ok else None",
                   "filtrer": "ok"}[op]
            src = (f"def {nom}(V, l0):\n    liste = l0 or []\n    ancien, ok = V[{k}], []\n{init}    try:\n"
                   f"        for e in liste:\n            V[{k}] = e\n            if {corps}:\n                ok.append(e)\n"
                   f"    finally:\n        V[{k}] = ancien\n    return {fin}\n")
        self._exec(nom, src)
        return f"{nom}(V, {sl})"

    def _op(self, op, a, P, prof, ctx):
        x = lambda u: self._x(u, P, prof, ctx)
        if op in _LIEURS:
            return self._boucle(op, a, P, prof, ctx)
        if op in ("et", "ou"):
            fs = [x(u) for u in a]
            if not fs:
                return "True" if op == "et" else "False"
            return "bool(" + f" {'and' if op == 'et' else 'or'} ".join(f"({f})" for f in fs) + ")"
        if op in ("non", "vide"):
            return f"(not {x(a[0])})"
        if op in ("=", "!="):
            s0, s1 = x(a[0]), x(a[1])
            if self._jamais_dict(a[0]) or self._jamais_dict(a[1]):  # un côté n'est jamais un dict : `is` et `==`
                e = f"(({s0}) == ({s1}))"  # donnent tous deux faux si l'autre en est un ; sinon c'est `==`, comme avant
            else:
                u, w = self._tmp(), self._tmp()
                e = f"(({u} is {w}) if (isinstance({u} := {s0}, dict) | isinstance({w} := {s1}, dict)) else ({u} == {w}))"
            return e if op == "=" else f"(not {e})"
        if op in sr._ARITH:
            s0, s1 = x(a[0]), x(a[1])
            return f"(({s0}) {op} ({s1}))"
        if op == "si":
            s0, s1, s2 = x(a[0]), x(a[1]), x(a[2])
            return f"(({s1}) if ({s0}) else ({s2}))"
        if op == "liste":
            return "[" + ", ".join(x(u) for u in a) + "]"
        if op == "longueur":
            return f"len({x(a[0])})"
        if op == "elem":
            v = self._tmp()
            s0, s1 = x(a[0]), x(a[1])
            return f"({v}[{s1}] if ({v} := {s0}) is not None else None)"
        if op == "premier":
            v = self._tmp()
            return f"({v}[0] if ({v} := {x(a[0])}) else None)"
        if op == "contient":
            return f"_contient({x(a[0])}, {x(a[1])})"
        if op == "etat":
            return f"prog.etat.get({self._nom('K', a[0])})"  # nom NON évalué, comme sim_rapide
        if op == "epuise":
            s1 = x(a[1]) if len(a) > 1 else "0"
            return f"((prog.etat.get({self._nom('K', a[0])}) or 0) <= ({s1}))"
        if op == "action":
            return "V[1][0]"
        if op == "debut_niveau":
            return "bool(V[4])"
        if op in ("x", "y"):
            return f"({x(a[0])})[{op!r}]"
        if op in ("largeur", "hauteur"):
            d, p = (1 if op == "largeur" else 0), self._tmp()
            return f"({p}.shape[{d}] if type({p} := ({x(a[0])})['pixels']) is nd else np.asarray({p}).shape[{d}])"
        if op == "attr":
            s0, s1 = x(a[0]), x(a[1])
            return f"({s0}).get('attrs', _VIDE).get({s1})"
        if op == "attr_cache":
            o = self._tmp()
            s0, s1 = x(a[0]), x(a[1])
            return f"(None if ({o} := {s0}) is None else {o}.get('cache', _VIDE).get({s1}))"
        if op == "nom":
            return f"({x(a[0])}).get('nom')"
        if op == "echelle":
            return f"({x(a[0])}).get('echelle', 1)"
        if op in ("visible", "bloquant"):
            o = self._tmp()
            return f"(({o} := {x(a[0])}) is not None and bool({o}.get({op!r}, True)))"
        if op == "utilise":
            o = self._tmp()
            return f"(({o} := {x(a[0])}) is not None and bool({o}.get('attrs', _VIDE).get('utilise')))"
        if op == "calque":
            if len(a) != 1:
                raise ValueError  # ProgrammeCompile rend l'erreur du langage
            o = self._tmp()
            return f"(None if ({o} := {x(a[0])}) is None else {o}['couche'])"
        if op == "tags":
            o = self._tmp()
            return f"([] if ({o} := {x(a[0])}) is None else list({o}.get('tags', ())))"
        if op == "a_tag":
            return f"_a_tag({x(a[0])}, {x(a[1])})"
        if op == "pixel":
            return f"_pixel({x(a[0])}, {x(a[1])}, {x(a[2])})"
        if op == "intervalle":
            return f"list(range({x(a[0])}, {x(a[1])}))"
        if op == "chevauche":
            u, w = self._tmp(), self._tmp()
            return f"(({u} := {x(a[0])}) is not ({w} := {x(a[1])}) and _chev({u}, {w}))"
        if op == "a":
            return f"_a(V[0], {x(a[0])}, {x(a[1])})"
        if op == "objets":
            f = a[0] if a else {}
            if not isinstance(f, dict):
                raise _NonCouvert
            tag = f.get("tag")
            s = self._tmp()
            tests = []
            for k, v in f.items():
                if k == "tag" and isinstance(tag, str):
                    continue
                if k == "tag":
                    tests.append(f"{self._nom('K', v)} in {s}.get('tags', ())")
                elif k == "nom":
                    tests.append(f"{s}.get('nom') == {self._nom('K', v)}")
                elif k == "visible":
                    tests.append(f"bool({s}.get('visible', True)) == {bool(v)}")
            if "couleur" in f:
                v = f["couleur"]
                if type(v) in (int, float, bool):
                    tests.append(f"{self._nom('K', v)} in _couleurs({s}['pixels'])")
                else:
                    tests.append(f"_filtre({s}, {self._nom('K', {'couleur': v})})")
            source = f"_par_tag(V[0], {self._nom('K', tag)})" if isinstance(tag, str) else "V[0].sprites"
            cond = " and ".join(tests)
            calcul = f"[{s} for {s} in {source}" + (f" if {cond}]" if cond else "]")
            cle = self._nom("K", repr(sorted((str(k), repr(v)) for k, v in f.items())))
            m = self._tmp("_m")
            return f"({m}.copy() if ({m} := _M.get({cle})) is not None else _M.setdefault({cle}, {calcul}).copy())"
        raise _NonCouvert

# ------------------------------------------------------------------ interrupteur
_ORIG = {}


def _remplacer(paires):
    fait = []
    for m in list(sys.modules.values()):
        if m is None or m.__name__ == __name__:  # jamais ce module-ci (ses propres définitions)
            continue
        for nom, ancien, nouv in paires:
            try:  # module paresseux (transformers, peft…) : getattr déclenche un import qui peut échouer (CW-429, B)
                trouve = getattr(m, nom, None)
            except Exception:  # noqa: BLE001
                break
            if trouve is ancien:
                setattr(m, nom, nouv)
                fait.append((m.__name__, nom))
    return fait


def installer(force=False, plate=None):
    """Remplace `ProgrammeCompile`, `cloner` et `cle_complete` (sim_rapide, plan_langage et tout module déjà chargé qui
    les a importés par leur nom) par ceux de G. → liste des (module, nom) remplacés. Ne fait rien (→ []) si
    `CHRYS_BACKEND_TABLEAUX` n'est ni 1 ni 2, sauf `force=True` (bancs de G). À appeler au démarrage, après les imports."""
    if not (ACTIF or force):
        return []
    plate = NIVEAU == "2" if plate is None else plate
    desinstaller()
    _ORIG.setdefault("ProgrammeCompile", sr.ProgrammeCompile)
    _ORIG.setdefault("cloner", sr.cloner)
    _ORIG.setdefault("cle_complete", _pl.cle_complete)
    return _remplacer([("ProgrammeCompile", _ORIG["ProgrammeCompile"], ProgrammeGenere),
                       ("cloner", _ORIG["cloner"], cloner),
                       ("cle_complete", _ORIG["cle_complete"], cle_plate if plate else cle_complete)])


def desinstaller():
    """Remet les fonctions d'origine partout où `installer` les avait remplacées."""
    if not _ORIG:
        return []
    return _remplacer([("ProgrammeCompile", ProgrammeGenere, _ORIG["ProgrammeCompile"]), ("cloner", cloner, _ORIG["cloner"]),
                       ("cle_complete", cle_complete, _ORIG["cle_complete"]),
                       ("cle_complete", cle_plate, _ORIG["cle_complete"])])
