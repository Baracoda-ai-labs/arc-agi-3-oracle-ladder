# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — planification DANS LE LANGAGE (programme JSON de A, simulateur `sim_rapide`), sortie du banc P0
(`experiments/T3.0/plafonds.py`) pour être appelée par l'agent (CCM-174-A : `but` = 27/60 contre 18/60 sur le banc).
- état de recherche : `cle_complete` (tous les sprites et l'état caché) ou `cle_compilee` (compteurs retirés, CW-192) ;
- distance au but lue dans la condition de victoire du programme (`regle_victoire`, `distance_but`) ;
- `planifier_langage(texte, scene, coups, recherche)` : "but" (meilleur d'abord sur la distance) ou "paliers" (SIW :
  sous-buts sérialisés, tr87 N2 gagné en 26 coups). Aucun accès au jeu : le plan est à revérifier par l'appelant."""
import heapq
import os
import time
from collections import deque

import numpy as np

CLE = os.environ.get("CHRYS_CLE", "complete")
# G (CW-324 P1, CCM-012-G ; accord de C et A) : CHRYS_CLE_MONOTONE=1 → `compiler_schema` ne sort de la clé que les variables
# cachées numériques DÉMONTRÉES monotones pendant sa marche (jamais une position, une sélection, une pile, un canevas), et
# `planifier_langage` les garde dans un vecteur de dominance (un état n'est écarté que s'il est dominé). Éteint : inchangé.
CLE_MONOTONE = os.environ.get("CHRYS_CLE_MONOTONE", "0") == "1"


class _VusDominance:
    """États vus : clé privée des ressources monotones → vecteurs de ces ressources (orientés « plus = mieux »). Un état
    est nouveau si sa clé est neuve ou si son vecteur n'est dominé (≤ partout) par aucun vecteur déjà vu sous cette clé."""

    def __init__(self, dominance):
        self.noms = sorted(dominance)
        self.signes = [dominance[n] for n in self.noms]
        self.d = {}

    def nouveau(self, k, etat):
        v = tuple(sg * (v if isinstance(v := (etat or {}).get(n, 0), (int, float)) else 0)
                  for n, sg in zip(self.noms, self.signes, strict=True))
        deja = self.d.setdefault(k, [])
        if any(all(a <= b for a, b in zip(v, w, strict=True)) for w in deja):
            return False
        deja.append(v)
        return True


_GELES = {}  # id(tableau) → (tableau, valeur gelée) : les tableaux inchangés sont partagés par `cloner`


_ATOMES = (int, float, str, bool, type(None))


def _gel(v):
    """Valeur hachable (rapide : la clé de recherche en dépend à chaque nœud)."""
    t = type(v)
    if t in _ATOMES:  # A (CW-254, vitesse) : cas le plus fréquent d'abord
        return v
    if t is dict:  # clés uniques : trier les paires revient à trier par clé (le 2ᵉ terme n'est jamais comparé)
        return tuple(sorted([(k if type(k) is str else str(k), _gel(x)) for k, x in v.items()]))
    if isinstance(v, np.ndarray):
        g = _GELES.get(id(v))
        if g is None or g[0] is not v:
            if len(_GELES) > 200000:
                _GELES.clear()
            g = _GELES[id(v)] = (v, (v.shape, v.tobytes()))
        return g[1]
    if isinstance(v, dict):
        return tuple(sorted(((str(k), _gel(x)) for k, x in v.items()), key=lambda t: t[0]))  # clés uniques
    if isinstance(v, (list, tuple)):
        return tuple(_gel(x) for x in v)
    if isinstance(v, set | frozenset):
        return tuple(sorted(repr(x) for x in v))
    return v if isinstance(v, (int, float, str, bool, type(None))) else repr(v)


_ORDRES = {}  # frozenset des clés d'un sprite → clés triées (les sprites d'un jeu partagent quelques formes de dictionnaire)
_TAGS = {}  # id(liste de tags) → (liste, tuple) : les tags ne sont jamais modifiés par un effet (`sim_rapide.cloner` les partage)


def _gel_sprite(o):
    """= `_gel(o)` pour un sprite (même tuple), plus vite : ordre des clés mis en cache, tags gelés une fois (CW-254)."""
    ks = _ORDRES.get(frozenset(o))
    if ks is None:
        if len(_ORDRES) > 10000:
            _ORDRES.clear()
        ks = _ORDRES[frozenset(o)] = sorted(o, key=str)
    out = []
    for k in ks:
        v = o[k]
        if type(v) in _ATOMES:
            out.append((k, v))
        elif k == "tags" and type(v) is list:
            g = _TAGS.get(id(v))
            if g is None or g[0] is not v:
                if len(_TAGS) > 200000:
                    _TAGS.clear()
                g = _TAGS[id(v)] = (v, _gel(v))
            out.append((k, g[1]))
        else:
            out.append((k, _gel(v)))
    return tuple(out)


class Compacteur:
    """Clé d'état COMPRESSÉE SANS PERTE (CW-256, A) : seuls les sprites qui diffèrent de la scène de départ y entrent (le
    décor resté fixe sort de la clé). Deux états ont la même clé ssi ils ont les mêmes sprites (mêmes indices, mêmes
    champs), la même caméra, les mêmes canevas, données, issue et état caché : aucune confusion possible (au pire, deux
    états égaux à une permutation près des sprites sont distingués, ce que la clé complète fusionnait). Les pixels inchangés
    sont reconnus par identité (`sim_rapide.cloner` les partage). Nombre de sprites différent du départ → clé complète."""

    def __init__(self, sc0):
        self.ref = [dict(o) for o in sc0.sprites]
        self.gels = [{} for _ in self.ref]  # gel des champs non atomiques du départ, calculé à la demande

    def _pareil(self, i, o):
        r = self.ref[i]
        if len(o) != len(r):
            return False
        for k, v in o.items():
            if k not in r:
                return False
            w = r[k]
            if v is w or (type(v) in _ATOMES and type(w) in _ATOMES and v == w and type(v) is type(w)):
                continue
            if type(v) in _ATOMES or type(w) in _ATOMES:
                return False
            g = self.gels[i].get(k)
            if g is None:
                g = self.gels[i][k] = _gel(w)
            if _gel(v) != g:
                return False
        return True

    def cle(self, sc, etat):
        if len(sc.sprites) != len(self.ref):
            return cle_complete(sc, etat)
        diff = tuple((i, _gel_sprite(o)) for i, o in enumerate(sc.sprites) if not self._pareil(i, o))
        return hash(("compacte", diff, _gel(sc.camera), _gel(getattr(sc, "canevas", None)),
                     _gel(getattr(sc, "donnees", None)), sc.issue, _gel(etat or {})))


def cle_complete(sc, etat):
    """État COMPLET pour la recherche (CW-189 a) : tous les sprites, cachés ou hors champ compris, avec TOUS leurs
    champs (attributs posés par les règles, blocage, étiquettes…), caméra, canevas, données du niveau, issue, et l'état
    caché du programme. L'ancienne clé (sprites visibles dans la vue) confondait des états différents."""
    # tri par hachage (CW-254, vitesse ; avant : par repr) : ordre canonique pour un même multiensemble de sprites ; deux
    # hachages égaux gardent l'ordre d'origine, ce qui peut seulement dédoubler un état, jamais en confondre deux
    return hash((tuple(sorted((_gel_sprite(o) for o in sc.sprites), key=hash)), _gel(sc.camera), _gel(getattr(sc, "canevas", None)),
                 _gel(getattr(sc, "donnees", None)), sc.issue, _gel(etat or {})))


def compiler_schema(sc0, prog, coups, nom, pas=400, graine=0, seuil=0.8):
    """Compilateur d'état, v1 (CW-192, `RelevantStateSchema`) : une marche au hasard DANS LE PROGRAMME mesure, pour chaque
    champ (sprite i : position, dessin, visibilité, autres champs ; variable cachée k), la part des coups où il change.
    Jamais changé → constante (hors de la clé) ; changé à ≥ `seuil` des coups → COMPTEUR (jauge, horloge, barre
    d'interface), hors de la clé : à état égal, le chemin le plus court domine (la recherche en largeur le trouve
    d'abord). Le reste = l'état pertinent. → (champs de sprites retenus, variables retenues, compteurs, constantes)."""
    import random as _r

    from chrysalide.arc3.sim_rapide import cloner
    rnd = _r.Random(graine)
    etat0 = prog.etat

    def champs(sc, etat):
        out = {}
        for i, o in enumerate(sc.sprites):
            out[("pos", i)] = (o["x"], o["y"])
            out[("dessin", i)] = _gel(o.get("pixels"))
            out[("visible", i)] = o.get("visible", True)
            for kk, v in o.items():
                if kk not in ("x", "y", "pixels", "visible"):
                    out[(kk, i)] = _gel(v)
        for kk, v in (etat or {}).items():
            out[("etat", kk)] = _gel(v)
        out[("camera",)] = _gel(sc.camera)
        out[("canevas",)] = _gel(getattr(sc, "canevas", None))
        return out
    freq, n, sens, hausses, baisses = {}, 0, {}, {}, {}
    sc, etat = cloner(sc0, etat0)
    avant = champs(sc, etat)
    for _ in range(pas):
        c = rnd.choice(coups)
        sc2, e2 = cloner(sc, etat)
        prog.etat = e2
        try:
            prog.step(sc2, nom(c))
        except Exception:  # noqa: BLE001, S112
            continue
        apres = champs(sc2, prog.etat)
        n += 1
        for kk in set(avant) | set(apres):
            if avant.get(kk) != apres.get(kk):
                freq[kk] = freq.get(kk, 0) + 1
                a, b = avant.get(kk), apres.get(kk)
                if kk[0] == "etat" and isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    sens[kk] = sens.get(kk, 0) + (1 if b > a else -1)
                    (hausses if b > a else baisses)[kk] = (hausses if b > a else baisses).get(kk, 0) + 1
        if sc2.issue is not None:  # fin de partie ou de niveau : on repart du début
            sc, etat = cloner(sc0, etat0)
            avant = champs(sc, etat)
        else:
            sc, etat, avant = sc2, prog.etat, apres
    prog.etat = etat0
    compteurs = {kk for kk, f in freq.items() if n and f / n >= seuil}
    if CLE_MONOTONE:  # seules sortent les variables cachées numériques qui n'ont fait que monter ou que baisser
        compteurs = {kk for kk in compteurs if kk[0] == "etat" and hausses.get(kk, 0) + baisses.get(kk, 0) >= 2
                     and not (hausses.get(kk) and baisses.get(kk))}
    pertinents = set(freq) - compteurs
    # compteurs numériques : RESSOURCE (baisse en général : plus haut = mieux) ou TEMPS (monte : plus bas = mieux)
    dominance = {kk[1]: (1 if sens.get(kk, 0) < 0 else -1) for kk in compteurs if kk[0] == "etat" and kk in sens}
    return pertinents, compteurs, n, dominance


def cle_compilee(sc, etat, compteurs):
    """Clé COMPLÈTE privée des seuls compteurs (un champ jamais vu changer dans l'échantillon peut changer plus tard :
    il reste dans la clé ; seuls les champs qui changent presque à chaque coup en sortent)."""
    sp = []
    for i, o in enumerate(sc.sprites):
        d = dict(o)
        if ("pos", i) in compteurs:
            d["x"] = d["y"] = None
        if ("dessin", i) in compteurs:
            d["pixels"] = None
        if ("visible", i) in compteurs:
            d["visible"] = None
        for kk in list(d):
            if (kk, i) in compteurs:
                d[kk] = None
        sp.append(_gel(d))
    e = {kk: v for kk, v in (etat or {}).items() if ("etat", kk) not in compteurs}
    cam = None if ("camera",) in compteurs else sc.camera
    can = None if ("canevas",) in compteurs else getattr(sc, "canevas", None)
    return hash((tuple(sp), _gel(cam), _gel(can), _gel(getattr(sc, "donnees", None)), sc.issue, _gel(e)))


def atomes(sc, etat):
    """Atomes d'un état pour la recherche par nouveauté : (nom, x, y) et (nom, apparence) de chaque sprite visible (une
    clé qui tourne, une case cliquée qui change de couleur ne bougent pas), + chaque variable cachée du programme."""
    return {("s", o.get("nom"), o["x"], o["y"]) for o in sc.sprites if o.get("visible", True)} | {
        ("a", o.get("nom"), hash(np.asarray(o["pixels"]).tobytes())) for o in sc.sprites if o.get("visible", True)} | {
        ("e", k, repr(v)) for k, v in (etat or {}).items()}


def regle_victoire(texte):
    """Condition de victoire du programme : la règle dont un effet (même imbriqué dans `si_alors`, `pour`) est
    `niveau_suivant` ou `gagner` → {"soit", "quand"} où `quand` = les conditions des `si_alors` qui l'entourent
    (ou la condition de la règle s'il n'y en a pas)."""
    def chercher(effets, conds):
        for e in effets or []:
            if not isinstance(e, list) or not e:
                continue
            if e[0] in ("niveau_suivant", "gagner"):
                return conds
            if e[0] == "si_alors" and len(e) >= 3:
                r = chercher(e[2], [*conds, e[1]])
                if r is None and len(e) >= 4:
                    r = chercher(e[3], [*conds, ["non", e[1]]])
                if r is not None:
                    return r
            elif e[0] == "pour" and len(e) >= 4:
                r = chercher(e[3], conds)
                if r is not None:
                    return r
            elif e[0] in mots and e[0] not in vus:  # mot défini par le programme (sk48 : `fin_coup`)
                vus.add(e[0])
                r = chercher(mots[e[0]].get("corps"), conds)
                if r is not None:
                    return r
        return None
    mots, vus = texte.get("mots") or {}, set()
    for regle in texte.get("regles", []):
        conds = chercher(regle.get("alors"), [])
        if conds is not None:
            return {"soit": regle.get("soit"), "quand": ["et", *conds] if conds else regle.get("quand")}
    return None


_DISTANCES = {}  # (id(texte), id(règle)) → (texte, règle, distance compilée par sim_rapide) ; CW-254 (vitesse)


def distance_but(interp, regle, sc, etat):
    """Version compilée (sim_rapide.ProgrammeCompile.distance) quand elle se construit, même résultat ; sinon l'interprétée."""
    if os.environ.get("CHRYS_DISTANCE_INTERPRETEE") != "1":
        k = (id(interp.p), id(regle))
        g = _DISTANCES.get(k)
        if g is None or g[0] is not interp.p or g[1] is not regle:
            try:
                from chrysalide.arc3.sim_rapide import ProgrammeCompile
                g = (interp.p, regle, ProgrammeCompile(interp.p).distance(regle))
            except Exception:  # noqa: BLE001 — terme non compilable : on garde l'interprétée
                g = (interp.p, regle, None)
            if len(_DISTANCES) > 1000:
                _DISTANCES.clear()
            _DISTANCES[k] = g
        if g[2] is not None:
            return g[2](sc, etat)
    return _distance_interpretee(interp, regle, sc, etat)


def _distance_interpretee(interp, regle, sc, etat):
    """Distance au but lue dans la condition de la règle de victoire du programme (0 = gagné) : « vide » compte les
    objets restants, « et » additionne, « ou » prend le minimum, « tous » compte les éléments qui ne vérifient pas
    encore, « = » entre nombres donne l'écart ; sinon 0 si vrai, 1 si faux. Aucun savoir propre à un jeu."""
    interp.etat = etat
    env = {"_scene": sc, "_action": None, "_niveau": 0, "_debut": False}
    for v, t in (regle.get("soit") or {}).items():  # liaisons : peuvent dépendre de l'action (clic) → ignorées si
        try:  # elles échouent sans action
            env[v] = interp.ev(t, env)
        except Exception:  # noqa: BLE001
            env[v] = None

    def h(t):
        try:
            if isinstance(t, list) and t and isinstance(t[0], str):
                op, a = t[0], t[1:]
                if op == "vide":
                    return len(interp.ev(a[0], env) or [])
                if op == "et":
                    return sum(h(x) for x in a)
                if op == "ou":
                    return min(h(x) for x in a)
                if op == "tous" and len(a) == 3:
                    liste = interp.ev(a[1], env) or []
                    return sum(0 if interp.ev(a[2], {**env, a[0][1:]: x}) else 1 for x in liste)
                if op == "=" and len(a) == 2:
                    x, y = interp.ev(a[0], env), interp.ev(a[1], env)
                    if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
                        return abs(x - y)
                    if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):  # suites : éléments différents
                        return sum(1 for u, v in zip(x, y, strict=False) if _gel(u) != _gel(v)) + abs(len(x) - len(y))
            return 0 if interp.ev(t, env) else 1
        except Exception:  # noqa: BLE001
            return 1
    return h(regle.get("quand"))




def _selecteurs(t, mots, out, vus):
    """Noms et tags d'objets cités dans un terme (filtres {"tag"/"nom"}, `a_tag`), mots du programme compris.
    → False si un filtre d'objets ne cite ni tag ni nom (tous les objets peuvent compter)."""
    ok = True
    if isinstance(t, dict):
        if ("tag" in t or "nom" in t) and all(isinstance(v, (str, int, bool, type(None))) or k in ("tag", "nom")
                                              for k, v in t.items()):
            out.update(str(t[k]) for k in ("tag", "nom") if k in t)
            return True
        for v in t.values():
            ok &= _selecteurs(v, mots, out, vus)
        return ok
    if isinstance(t, list) and t:
        if t[0] == "objets" and (len(t) < 2 or not isinstance(t[1], dict) or not ({"tag", "nom"} & set(t[1]))):
            ok = False
        if t[0] == "a_tag" and len(t) >= 3 and isinstance(t[2], str):
            out.add(t[2])
        if isinstance(t[0], str) and t[0] in mots and t[0] not in vus:
            vus.add(t[0])
            ok &= _selecteurs(mots[t[0]], mots, out, vus)
        for x in t:
            ok &= _selecteurs(x, mots, out, vus)
    return ok


def objets_du_but(texte, regle):
    """C (E2, V1 b) : abstraction par le but. Fermeture arrière : les objets lus par la victoire, puis tous ceux cités par
    une règle qui en cite un (elle peut les déplacer, les créer, les cacher), jusqu'au point fixe. → ensemble de tags et
    noms, ou None si un filtre générique rend tous les objets possibles (pas d'abstraction)."""
    mots = texte.get("mots") or {}
    pert = set()
    if not _selecteurs(regle, mots, pert, set()):
        return None
    regles = [(r, s, ok) for r in texte.get("regles", []) for s in [set()] for ok in [_selecteurs(r, mots, s, set())]]
    change = True
    while change:
        change = False
        for _, s, ok in regles:
            if s & pert and not s <= pert:
                if not ok:
                    return None
                pert |= s
                change = True
            elif s & pert and not ok:
                return None
    return pert


_VIDE = {}


class _Vue:
    """Scène vue à travers l'abstraction : un sprite non pertinent devient un dictionnaire vide à sa place (les indices,
    lus par `cle_compilee` et `Compacteur`, ne bougent pas ; leur nombre reste dans la clé)."""
    __slots__ = ("_sc", "sprites")

    def __init__(self, sc, garder):
        self._sc, self.sprites = sc, [o if garder(o) else _VIDE for o in sc.sprites]

    def __getattr__(self, k):
        return getattr(self._sc, k)


def conjoints(regle):
    """C (E2, V1 a) : sous-buts = conjoints de la victoire qui ne dépendent pas de l'action jouée (le dernier coup les
    règle) → liste de règles {"soit", "quand"} évaluables par `distance_but`."""
    q = regle.get("quand")
    termes = q[1:] if isinstance(q, list) and q and q[0] == "et" else [q]

    def lit_action(t):
        return (isinstance(t, list) and bool(t) and (t[0] in ("action", "case_clic") or any(lit_action(x) for x in t)))
    return [{"soit": regle.get("soit"), "quand": t} for t in termes if t is not None and not lit_action(t)]


def _profondeur(scene, etat0, utiles, pas, noter, cle, mesure, elaguer, noeuds, secondes, t0, progression, infos):
    """« Clé seule » (CW-305, A) : approfondissement itératif en profondeur, enfants dans l'ordre de la distance au but, table
    de transposition hachage de clé → profondeur (≈ 100 octets par état au lieu de la scène entière : la mémoire ne borne
    plus la recherche, seul le temps). Profondeur limite 16, 32, 64… jusqu'à CHRYS_PROFONDEUR_MAX (4 096). Les seules
    scènes gardées sont celles du chemin courant et de leurs enfants. Hachage 64 bits : une collision peut faire manquer un
    état (jamais un plan faux, puisque tout plan est rejoué)."""
    n = 0
    lmax = int(os.environ.get("CHRYS_PROFONDEUR_MAX", "4096"))

    def enfants(sc, etat):
        nonlocal n
        k1 = cle(sc, etat) if elaguer else None
        out = []
        for i, c in enumerate(utiles()):
            n += 1
            if progression is not None:
                progression(n)
            s2, e2 = pas(sc, etat, c)
            if s2 is None:
                continue
            noter(c, s2.issue is not None or cle(s2, e2) != k1)
            if s2.issue in ("niveau", "victoire"):
                return c, []
            if s2.issue is None:
                out.append((mesure(s2, e2)[0], i, s2, e2, c))
        out.sort(key=lambda x: (x[0], x[1]))
        return None, out

    def raccourcir(plan):
        """Boucles retirées par rejeu (CCM-292-A) : si l'état après le coup j est celui d'avant le coup i ≤ j, les coups i..j
        sont retirés ; recommencé jusqu'à point fixe. Le plan raccourci gagne toujours (dernier coup vérifié), sinon on garde
        le plan d'origine."""
        while True:
            sc, e, vus, coupe = scene, etat0, {cle(scene, etat0): 0}, None
            for j, c in enumerate(plan):
                sc, e = pas(sc, e, c)
                if sc is None:
                    return plan
                if sc.issue is not None:
                    break
                kk = cle(sc, e)
                if kk in vus:
                    coupe = (vus[kk], j + 1)
                    break
                vus[kk] = j + 1
            if coupe is None:
                return plan
            court = plan[:coupe[0]] + plan[coupe[1]:]
            sc, e = scene, etat0
            for i, c in enumerate(court):
                sc, e = pas(sc, e, c)
                if sc is None or (sc.issue is not None and sc.issue not in ("niveau", "victoire")):
                    return plan
                if sc.issue is not None:  # victoire plus tôt : le reste du plan est inutile
                    court = court[:i + 1]
                    break
            if sc is None or sc.issue not in ("niveau", "victoire"):
                return plan
            plan = court

    def fini(plan, inf):
        p = raccourcir(plan)
        return p, {**inf, "plan_brut": len(plan)}

    lim, table_max = 16, 0
    while lim <= lmax:
        table = {hash(cle(scene, etat0)): 0}
        g, lst = enfants(scene, etat0)
        if g is not None:
            return fini([g], {**infos, "noeuds": n, "profondeur": lim})
        pile, chemin, coupe = [iter(lst)], [], False
        while pile:
            if n >= noeuds or time.time() - t0 >= secondes:
                return None, {**infos, "noeuds": n, "profondeur": lim, "table": max(table_max, len(table)),
                              "refus": "budget"}
            try:
                _, _, s2, e2, c = next(pile[-1])
            except StopIteration:
                pile.pop()
                if chemin:
                    chemin.pop()
                continue
            d = len(pile)
            hk = hash(cle(s2, e2))
            if table.get(hk, 1 << 30) <= d:
                continue
            table[hk] = d
            if d >= lim:
                coupe = True
                continue
            g, lst = enfants(s2, e2)
            if g is not None:
                return fini([*chemin, c, g], {**infos, "noeuds": n, "profondeur": lim, "table": len(table)})
            chemin.append(c)
            pile.append(iter(lst))
        table_max = max(table_max, len(table))
        if not coupe:
            return None, {**infos, "noeuds": n, "profondeur": lim, "table": table_max, "refus": "espace épuisé sans issue"}
        lim *= 2
    return None, {**infos, "noeuds": n, "profondeur": lim // 2, "table": table_max, "refus": "profondeur maximale"}


def planifier_langage(texte, scene, coups, recherche="but", noeuds=100000, secondes=30.0, compiler=True, etat=None,
                      progression=None):
    """`coups` : actions au format du langage, ("UP", None, None) … ("CLICK", ligne, colonne). La scène est déroulée par
    `sim_rapide.ProgrammeCompile`. `etat` : état caché du programme à l'état courant (ex. `Programme.etat` après le rejeu de
    la porte 1 de l'agent) ; sinon l'état initial. → (plan | None, infos). « but » : meilleur d'abord sur la distance au but, à égalité
    le plus court ; « paliers » : SIW. `compiler` : clé privée des compteurs appris par échantillonnage (CW-192).
    « generique » (défi 6 de ChatGPT, CW-278/279, intégré par A) : sous-buts lus dans le programme (`plan_generique`).
    `progression(n)` : rappel du nombre de nœuds (portefeuille parallèle, `plan_portefeuille`)."""
    if recherche == "generique":
        from chrysalide.arc3.logique.plan_generique import planifier
        return planifier(texte, scene, coups, noeuds=noeuds, secondes=secondes, etat=etat, progression=progression,
                         macros=os.environ.get("CHRYS_SOUSBUTS_MACROS", "0") == "1")  # sans macros : sa meilleure config
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    t0 = time.time()
    prog, interp, regle = ProgrammeCompile(texte), Programme(texte), regle_victoire(texte)
    infos = {"recherche": recherche}
    if regle is None:
        return None, {**infos, "refus": "pas de règle de victoire"}
    if etat is not None:
        from copy import deepcopy
        prog.etat = deepcopy(etat)
    etat0 = prog.etat
    compteurs, dominance = set(), {}
    if compiler:
        _, compteurs, _, dominance = compiler_schema(scene, prog, list(range(len(coups))), lambda i: coups[i])
        infos["compteurs"] = len(compteurs)
        if CLE_MONOTONE:
            infos["dominance"] = dominance

    comp = Compacteur(scene) if os.environ.get("CHRYS_CLE") == "compacte" else None  # CW-256 (A), sans perte
    # C (E2, pré-inscrit) : CHRYS_PLAN_V1=1 → (a) heuristique lexicographique (sous-buts non atteints, distance) et paliers
    # qui ne défont aucun sous-but atteint ; (b) clé réduite aux objets de la fermeture arrière du but
    v1 = os.environ.get("CHRYS_PLAN_V1") == "1"
    pert = objets_du_but(texte, regle) if v1 else None
    sous = conjoints(regle) if v1 else []
    infos.update(v1=v1, objets_but=None if pert is None else len(pert), sous_buts=len(sous))
    if pert is not None:
        nommes = {str(o.get("nom")) for o in scene.sprites} | {str(t) for o in scene.sprites for t in o.get("tags") or []}
        if not pert & nommes:  # victoire sur des objets inconnus de la scène (créés plus tard) : pas d'abstraction
            pert = None

    def garder(o):
        ids = [o.get("nom"), *(o.get("tags") or [])]
        return not any(i is not None for i in ids) or any(str(i) in pert for i in ids if i is not None)

    def cle(sc, etat):
        if pert is not None:
            sc = _Vue(sc, garder)
        if compteurs:
            return cle_compilee(sc, etat, compteurs)
        return comp.cle(sc, etat) if comp is not None else cle_complete(sc, etat)

    # C (CW-249 action 2, bp35 : 95 % de coups sans effet) : CHRYS_ELAGUER_ACTIONS=1 → une action essayée ≥ 40 fois sans
    # JAMAIS changer l'état est écartée du reste de la recherche (clics hors de toute cible, flèches inertes)
    elaguer = os.environ.get("CHRYS_ELAGUER_ACTIONS") == "1"
    essais, effets, ecartees = {}, {}, set()

    def utiles():
        return [c for c in coups if c not in ecartees]

    def noter(c, change):
        if not elaguer:
            return
        essais[c] = essais.get(c, 0) + 1
        effets[c] = effets.get(c, 0) + bool(change)
        if essais[c] >= 40 and not effets[c] and len(ecartees) < len(coups) - 1:
            ecartees.add(c)

    def mesure(sc, etat):
        """V0 : distance au but. V1 : (sous-buts non atteints, distance), et l'ensemble des sous-buts atteints."""
        d = distance_but(interp, regle, sc, etat)
        if not v1:
            return d, None
        ok = frozenset(i for i, r in enumerate(sous) if distance_but(interp, r, sc, etat) == 0)
        return (len(sous) - len(ok), d), ok

    def mieux(m2, ok2, m, ok):
        if not v1:
            return m2 < m
        return (ok is None or ok2 >= ok) and m2 < m

    def pas(sc, etat, c):
        s2, e2 = cloner(sc, etat)
        prog.etat = e2
        try:
            prog.step(s2, c)
        except Exception:  # noqa: BLE001 — règle qui plante sur ce coup : branche abandonnée
            return None, None
        return s2, prog.etat
    n = 0
    from chrysalide.arc3.logique.economie_plan import cout as cout_eco
    from chrysalide.arc3.logique.economie_plan import limite as limite_eco
    reserve = limite_eco()  # F (CW-333, CHRYS_ECONOMIE) : None = inchangé
    if recherche == "paliers":
        sc, etat, plan, h, ok = scene, etat0, [], (float("inf"),) * (2 if v1 else 1), None
        if not v1:
            h = h[0]
        while n < noeuds and time.time() - t0 < secondes:
            file, vus, trouve = deque([(sc, etat, [])]), {cle(sc, etat)}, None
            vdom = _VusDominance(dominance) if CLE_MONOTONE and dominance else None
            if vdom is not None:
                vdom.nouveau(cle(sc, etat), etat)
            while file and not trouve and n < noeuds and time.time() - t0 < secondes:
                s1, e1, ch = file.popleft()
                k1 = cle(s1, e1) if elaguer else None
                for c in utiles():
                    n += 1
                    if progression is not None:
                        progression(n)
                    s2, e2 = pas(s1, e1, c)
                    if s2 is None:
                        continue
                    noter(c, s2.issue is not None or cle(s2, e2) != k1)
                    if s2.issue in ("niveau", "victoire"):
                        return [*plan, *ch, c], {**infos, "noeuds": n}
                    if s2.issue is not None:
                        continue
                    if reserve is not None and sum(map(cout_eco, (*plan, *ch, c))) >= reserve:
                        continue  # F (CHRYS_ECONOMIE) : réserve épuisée sans victoire → position perdue
                    kk = cle(s2, e2)
                    if vdom is not None:
                        if not vdom.nouveau(kk, e2):
                            continue
                    elif kk in vus:
                        continue
                    vus.add(kk)
                    h2, ok2 = mesure(s2, e2)
                    if mieux(h2, ok2, h, ok):
                        trouve = (s2, e2, [*ch, c], h2, ok2)
                        break
                    file.append((s2, e2, [*ch, c]))
            if not trouve:
                return None, {**infos, "noeuds": n, "refus": "palier introuvable" if not file else "budget"}
            sc, etat, ch, h, ok = trouve
            plan += ch
        return None, {**infos, "noeuds": n, "refus": "budget"}
    if recherche == "profondeur":
        if CLE_MONOTONE and compteurs:  # table de transposition sans dominance : clé complète, aucun champ retiré
            def cle_p(sc, etat):
                return cle_complete(_Vue(sc, garder) if pert is not None else sc, etat)
        else:
            cle_p = cle
        return _profondeur(scene, etat0, utiles, pas, noter, cle_p, mesure, elaguer, noeuds, secondes, t0, progression, infos)
    tas, k = [(mesure(scene, etat0)[0], 0, 0, scene, etat0, [])], 1
    vus = {cle(scene, etat0)}
    vdom = _VusDominance(dominance) if CLE_MONOTONE and dominance else None
    if vdom is not None:
        vdom.nouveau(cle(scene, etat0), etat0)
    while tas and n < noeuds and time.time() - t0 < secondes:
        _, _, _, sc, etat, chemin = heapq.heappop(tas)
        k1 = cle(sc, etat) if elaguer else None
        for c in utiles():
            n += 1
            if progression is not None:
                progression(n)
            s2, e2 = pas(sc, etat, c)
            if s2 is None:
                continue
            noter(c, s2.issue is not None or cle(s2, e2) != k1)
            if s2.issue in ("niveau", "victoire"):
                return [*chemin, c], {**infos, "noeuds": n}
            if s2.issue is not None:
                continue
            if reserve is not None and sum(map(cout_eco, (*chemin, c))) >= reserve:
                continue  # F (CHRYS_ECONOMIE) : réserve épuisée sans victoire → position perdue
            kk = cle(s2, e2)
            if vdom is not None:
                if not vdom.nouveau(kk, e2):
                    continue
            elif kk in vus:
                continue
            vus.add(kk)
            heapq.heappush(tas, (mesure(s2, e2)[0], len(chemin) + 1, k, s2, e2, [*chemin, c]))
            k += 1
    return None, {**infos, "noeuds": n, "refus": "budget" if tas else "espace épuisé"}
