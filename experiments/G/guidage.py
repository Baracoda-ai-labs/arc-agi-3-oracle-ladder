"""[G] CW-304 — guidage lu dans le programme. `distance_graduee(prog, regle)` : distance au but GRADUÉE, lue dans la seule
condition de victoire (aucune règle par jeu), là où `plan_langage.distance_but` rend 0/1 pour `existe` et compte les
éléments faux pour `tous` :
- `et` → somme ; `ou` → minimum ; `existe v L c` → minimum sur les éléments de la distance de c (1 si L est vide) ;
  `tous v L c` → somme sur les éléments ; `vide L` → nombre d'éléments ;
- `=` sur deux nombres → écart absolu ; `<`, `<=`, `>`, `>=` → ce qui manque pour que l'inégalité tienne ;
- `non` est poussé vers l'intérieur (De Morgan, `non existe` = `tous non`, `non =` → 0 si différents, sinon 1) ;
- tout autre terme → 0 s'il est vrai, 1 sinon ; une erreur → 1 (comme distance_but).
Distance nulle ⟺ condition vraie (même lecture que distance_but sur les termes qu'elle sait graduer)."""
from collections import deque

import numpy as np

from chrysalide.arc3.sim_rapide import _BASE, _DEBUT, _DEPILE, _LIBRE, _NIVEAU, _SCENE

_NUM = (int, float)


def _nombre(x):
    return isinstance(x, _NUM) and not isinstance(x, bool)


def _producteurs(texte, n, vrai):
    """Règles dont un effet pose la variable cachée n (à une valeur vraie si `vrai`, fausse sinon ; valeur calculée :
    gardée dans les deux cas) → [(règle, conditions sur le chemin : quand de la règle, conditions des si_alors)]."""
    mots, out = texte.get("mots") or {}, []

    def scan(effets, conds, r, vus):
        for e in effets or []:
            if not (isinstance(e, list) and e and isinstance(e[0], str)):
                continue
            op = e[0]
            if op == "poser" and len(e) > 2 and e[1] == n:
                v = e[2]
                if isinstance(v, list) or bool(v) == vrai:
                    out.append((r, conds))
            elif op == "si_alors" and len(e) > 2:
                scan(e[2], [*conds, e[1]], r, vus)
                if len(e) > 3:
                    scan(e[3], [*conds, ["non", e[1]]], r, vus)
            elif op == "pour" and len(e) > 3:
                scan(e[3], conds, r, vus)
            elif op in mots and op not in vus and mots[op].get("sorte") == "effet":
                scan(mots[op].get("corps"), conds, r, vus | {op})
    for r in texte.get("regles", []):
        scan(r.get("alors"), [r.get("quand", True)], r, frozenset())
    return out


def distance_graduee(prog, regle, regression=2):
    """prog : ProgrammeCompile / ProgrammeGenere ; → fonction (scène, état caché) → distance ≥ 0. `regression` : profondeur
    de la remontée « variable cachée du but ← règles qui la posent ← leurs conditions » (0 : pas de remontée)."""
    portee, soit = {}, []
    for v, t in (regle.get("soit") or {}).items():
        f = prog.c(t, portee)
        portee = {**portee, v: prog._case(v)}
        soit.append((portee[v], f))

    def sur(f):
        def g(V):
            try:
                return f(V)
            except Exception:  # noqa: BLE001 — sous-distance qui plante : 1, comme distance_but
                return 1
        return g

    def booleen(t, P, neg, prof=regression):
        f = prog.c(t, P)
        if prof > 0 and isinstance(t, list) and len(t) == 2 and t[0] == "etat" and isinstance(t[1], str):
            prods = []
            for r, conds in _producteurs(prog.p, t[1], not neg):  # chaque producteur : ses liaisons, puis ses conditions
                Pr, soit_r = {}, []
                for v, u in (r.get("soit") or {}).items():
                    g = prog.c(u, Pr)
                    Pr = {**Pr, v: prog._case(v)}
                    soit_r.append((Pr[v], sur(g)))
                dc = d(["et", *conds], Pr, False, prof - 1)

                def prod(V, soit_r=soit_r, dc=dc):
                    anciens = [V[k] for k, _ in soit_r]
                    try:
                        for k, g in soit_r:
                            V[k] = g(V)
                        return dc(V)
                    finally:
                        for (k, _), x in zip(soit_r, anciens, strict=True):
                            V[k] = x
                prods.append(prod)
            if prods:
                def regr(V):
                    vrai = bool(f(V))
                    if vrai != neg:
                        return 0
                    return 1 + min(p(V) for p in prods)
                return sur(regr)
        return sur((lambda V: 1 if f(V) else 0) if neg else (lambda V: 0 if f(V) else 1))

    def d(t, P, neg=False, prof=regression):
        if not (isinstance(t, list) and t and isinstance(t[0], str)):
            return booleen(t, P, neg, prof)
        op, a = t[0], t[1:]
        if op == "non" and len(a) == 1:
            return d(a[0], P, not neg, prof)
        if op in ("et", "ou") and a:
            fs = [d(x, P, neg, prof) for x in a]
            somme = (op == "et") != neg  # non(et) = ou des non ; non(ou) = et des non
            return sur((lambda V: sum(f(V) for f in fs)) if somme else (lambda V: min(f(V) for f in fs)))
        if op in ("existe", "tous") and len(a) == 3 and isinstance(a[0], str):
            nv = a[0].lstrip("$")
            k = prog._case(nv)
            fl, fc = prog.c(a[1], P), d(a[2], {**P, nv: k}, neg, prof)
            mini = (op == "existe") != neg  # non(existe c) = tous (non c)

            def q(V):
                liste, ancien = list(fl(V) or []), V[k]
                if not liste:
                    return (1 if mini else 0)
                try:
                    vals = []
                    for e in liste:
                        V[k] = e
                        vals.append(fc(V))
                finally:
                    V[k] = ancien
                return min(vals) if mini else sum(vals)
            return sur(q)
        if op == "vide" and len(a) == 1 and not neg:
            fl = prog.c(a[0], P)
            return sur(lambda V: len(fl(V) or []))
        if op in ("=", "!=", "<", "<=", ">", ">=") and len(a) == 2:
            fx, fy, fe = prog.c(a[0], P), prog.c(a[1], P), prog.c(t, P)
            vrai_si = {"=": "=", "!=": "!="}.get(op, op)
            if neg:
                vrai_si = {"=": "!=", "!=": "=", "<": ">=", "<=": ">", ">": "<=", ">=": "<"}[vrai_si]

            def cmp(V):
                x, y = fx(V), fy(V)
                if not (_nombre(x) and _nombre(y)):
                    v = bool(fe(V))
                    return 0 if v != neg else 1
                if vrai_si == "=":
                    return abs(x - y)
                if vrai_si == "!=":
                    return 0 if x != y else 1
                manque = {"<": x - y + 1, "<=": x - y, ">": y - x + 1, ">=": y - x}[vrai_si]
                return max(0, manque)
            return sur(cmp)
        return booleen(t, P, neg, prof)

    corps = d(regle.get("quand", True), portee)
    prog._V.extend([None] * (_BASE + len(prog._cases) - len(prog._V)))

    def distance(scene, etat):
        V = prog._V
        V[_SCENE], V[1], V[_NIVEAU], V[_DEBUT], V[_DEPILE] = scene, None, 0, False, _LIBRE
        prog.etat = etat
        if hasattr(prog, "_M"):
            prog._M.clear()
        for k, f in soit:
            try:
                V[k] = f(V)
            except Exception:  # noqa: BLE001 — liaison qui dépend de l'action : None, comme distance_but
                V[k] = None
        return corps(V)
    return distance


def lus_par_le_but(texte, regle, prof=2):
    """(filtres `objets` lus, noms de variables cachées lues) par la condition de victoire, ses liaisons, et — sur `prof`
    niveaux — par les conditions des règles qui posent ces variables (même remontée que distance_graduee)."""
    filtres, noms = [], set()

    def scan(t):
        if isinstance(t, list) and t and isinstance(t[0], str):
            if t[0] == "objets":
                f = t[1] if len(t) > 1 and isinstance(t[1], dict) else {}
                if f not in filtres:
                    filtres.append(f)
            elif t[0] in ("etat", "epuise") and len(t) > 1 and isinstance(t[1], str):
                noms.add(t[1])
            for u in t[1:]:
                scan(u)
        elif isinstance(t, list):
            for u in t:
                scan(u)
        elif isinstance(t, dict):
            for u in t.values():
                scan(u)
    scan(regle.get("quand"))
    scan(regle.get("soit"))
    faits = set()
    for _ in range(prof):
        for n in sorted(noms - faits):
            faits.add(n)
            for r, conds in _producteurs(texte, n, True) + _producteurs(texte, n, False):
                scan(conds)
                scan(r.get("soit"))
    return filtres, noms


def empreinte_but(prog, regle):
    """→ fonction (scène, état caché) → valeur hachable de ce que lit le but : position, visibilité et dessin (identité des
    pixels, copiés à l'écriture) des objets des filtres lus, et valeurs des variables cachées lues."""
    from chrysalide.arc3.logique.plan_langage import _gel
    filtres, noms = lus_par_le_but(prog.p, regle)
    fs = [prog.c(["objets", f], {}) for f in filtres]
    noms = sorted(noms)

    def empreinte(scene, etat):
        V = prog._V
        V[_SCENE] = scene
        prog.etat = etat
        if hasattr(prog, "_M"):
            prog._M.clear()
        objs = []
        for f in fs:
            try:
                objs.append(tuple((s["x"], s["y"], s.get("visible", True), id(s["pixels"])) for s in f(V)))
            except Exception:  # noqa: BLE001
                objs.append(None)
        return hash((tuple(objs), tuple(_gel((etat or {}).get(n)) for n in noms)))
    return empreinte, (len(filtres), len(noms))


def ressources_monotones(sc0, prog, coups, nom, pas=400, graine=0):
    """Champs numériques (x, y des sprites ; variables cachées) qui, pendant une marche au hasard DANS LE PROGRAMME, ne
    font que baisser (ou que monter) et changent au moins 2 fois. La marche repart du départ après une issue ou une
    création d'objet ; la monotonie est jugée par segment. → {champ: signe} ; champ = (« sprite », i, « x »|« y ») ou
    (« etat », nom) ; signe +1 si la ressource baisse (plus haut = mieux), −1 si elle monte. Exemple : une jauge."""
    import copy
    import random

    from chrysalide.arc3.sim_rapide import cloner
    rnd = random.Random(graine)
    etat0 = copy.deepcopy(prog.etat)

    def lire(sc, e):
        out = {}
        for i, o in enumerate(sc.sprites):
            for ch in ("x", "y"):
                if _nombre(o.get(ch)):
                    out[("sprite", i, ch)] = o[ch]
        for k, v in (e or {}).items():
            if _nombre(v):
                out[("etat", k)] = v
        return out
    n0 = len(sc0.sprites)
    diffs = {}  # champ → liste des variations non nulles, par segment ([[…], […]])
    sc, etat = cloner(sc0, etat0)
    avant = lire(sc, etat)
    for k in avant:
        diffs[k] = [[]]
    for _ in range(pas):
        s2, e2 = cloner(sc, etat)
        prog.etat = e2
        ok = True
        try:
            prog.step(s2, nom(rnd.choice(coups)))
        except Exception:  # noqa: BLE001 — coup qui plante : la marche repart du départ
            ok = False
        if not ok or s2.issue is not None or len(s2.sprites) != n0:
            sc, etat = cloner(sc0, etat0)
            avant = lire(sc, etat)
            for seg in diffs.values():
                seg.append([])
            continue
        sc, etat = s2, prog.etat
        apres = lire(sc, etat)
        for k, v in apres.items():
            if k not in diffs:  # variable apparue en cours de partie (ex. un compteur posé au 1er coup)
                diffs[k] = [[]]
            if k in avant and v != avant[k]:
                diffs[k][-1].append(v - avant[k])
        avant = apres
    prog.etat = etat0
    out = {}
    for k, segs in diffs.items():
        tout = [d for seg in segs for d in seg]
        if len(tout) >= 2 and (all(d < 0 for d in tout) or all(d > 0 for d in tout)):
            out[k] = 1 if tout[0] < 0 else -1
    return out


_ATOMIQUES = (int, float, str, bool, type(None))


def faits(sc, etat, exclus=frozenset()):
    """Faits d'un état pour la nouveauté (BFWS) : position et apparence de chaque sprite visible, attributs atomiques des
    sprites (porte « ouverte »…), variables cachées atomiques. Les listes (trajets, piles) n'en font pas partie : elles
    rendraient chaque état « nouveau »."""
    from chrysalide.arc3.logique.plan_langage import _gel
    out = set()
    for i, o in enumerate(sc.sprites):
        if not o.get("visible", True):
            continue
        nom = o.get("nom")
        if ("sprite", i) not in exclus:  # ressource monotone (jauge) : sa position rendrait tout état « nouveau »
            out.add(("s", nom, o["x"], o["y"]))
        out.add(("a", nom, hash(_gel(o["pixels"]))))
        for k, v in (o.get("attrs") or {}).items():
            if type(v) in _ATOMIQUES:
                out.add(("t", nom, k, v))
    for k, v in (etat or {}).items():
        if type(v) in _ATOMIQUES and ("etat", k) not in exclus:
            out.add(("e", k, v))
    return out


# ------------------------------------------------------------------ V1 (CW-339, Astra) : coût relaxé h_max sur l'état caché
_JOKER = object()  # « n a une valeur calculée » : satisfait toute condition sur n (relâché)


def _conds_etat(t, out):
    """Conditions de la forme (etat n) vrai, (= (etat n) c), (non (etat n)) dans une conjonction ; le reste est RELÂCHÉ."""
    if isinstance(t, list) and t and isinstance(t[0], str):
        if t[0] == "et":
            for u in t[1:]:
                _conds_etat(u, out)
        elif t[0] == "etat" and len(t) == 2 and isinstance(t[1], str):
            out.append((t[1], True))
        elif t[0] == "non" and len(t) == 2 and isinstance(t[1], list) and t[1][:1] == ["etat"] and len(t[1]) == 2:
            out.append((t[1][1], False))
        elif t[0] == "=" and len(t) == 3:
            for a, b in ((t[1], t[2]), (t[2], t[1])):
                if isinstance(a, list) and a[:1] == ["etat"] and len(a) == 2 and type(b) in (int, str, bool, type(None)):
                    out.append((a[1], b))
    return out


def regles_relachees(texte):
    """[(préconditions, effets)] : faits = (variable cachée, valeur), valeur True = « vraie », False = « fausse »,
    _JOKER = « calculée » ; une règle par effet `poser` du programme (gardes et conditions de `si_alors` sur le chemin)."""
    mots, out = texte.get("mots") or {}, []

    def scan(effets, conds, vus):
        for e in effets or []:
            if not (isinstance(e, list) and e and isinstance(e[0], str)):
                continue
            if e[0] == "poser" and len(e) > 2 and isinstance(e[1], str):
                v = e[2]
                eff = (e[1], v if type(v) in (int, str, bool, type(None)) else _JOKER)
                out.append((tuple(c for t in conds for c in _conds_etat(t, [])), eff))
            elif e[0] == "si_alors" and len(e) > 2:
                scan(e[2], [*conds, e[1]], vus)
                if len(e) > 3:
                    scan(e[3], conds, vus)
            elif e[0] == "pour" and len(e) > 3:
                scan(e[3], conds, vus)
            elif e[0] in mots and e[0] not in vus and mots[e[0]].get("sorte") == "effet":
                scan(mots[e[0]].get("corps"), conds, vus | {e[0]})
    for r in texte.get("regles", []):
        scan(r.get("alors"), [r.get("quand", True)], frozenset())
    return out


def _vrai(fait_n, attendu, faits):
    """Le fait (n, attendu) est-il satisfait par l'ensemble relâché `faits` (dict n → set de valeurs) ?"""
    vals = faits.get(fait_n, set())
    if _JOKER in vals:
        return True
    if attendu is True:
        return any(bool(x) for x in vals)
    if attendu is False:
        return any(not x for x in vals) or not vals
    return any(x == attendu and type(x) is type(attendu) or x == attendu for x in vals)


def hmax_etat(texte, regle_victoire):
    """→ fonction (état caché) → h_max relâché des conditions de victoire sur l'état caché (0 s'il n'y en a pas),
    ou None si le but ne lit aucune variable cachée (rien à guider). Coût 1 par règle (un coup peut en déclencher
    plusieurs : h_max reste un minorant, on ne somme pas)."""
    regles = regles_relachees(texte)
    but = _conds_etat(regle_victoire.get("quand"), []) if regle_victoire else []
    if not but:
        return None

    def h(etat):
        cout = {}  # (n, valeur) → coût
        faits = {}
        for n, v in (etat or {}).items():
            if type(v) in (int, str, bool, type(None)):
                cout[(n, v)] = 0
                faits.setdefault(n, set()).add(v)
        change = True
        while change:
            change = False
            for pre, (n, v) in regles:
                if not all(_vrai(a, b, faits) for a, b in pre):
                    continue
                c = 1 + max((min((cout[(a, x)] for x in faits.get(a, ()) if (a, x) in cout), default=0)
                             for a, _b in pre), default=0)
                if c < cout.get((n, v), float("inf")):
                    cout[(n, v)] = c
                    faits.setdefault(n, set()).add(v)
                    change = True
        couts = []
        for n, b in but:
            if not _vrai(n, b, faits):
                return float("inf")
            vals = [cout.get((n, x), 0) for x in faits.get(n, ()) if _vrai(n, b, {n: {x}})]
            couts.append(min(vals, default=0))
        return max(couts, default=0)
    return h


# ------------------------------------------------------------------ V1 géométrique (CW-349/350), étape A
def table_geometrique(prog, sc0, coups, nom, regle, max_pos=5000):
    """Relaxation « obstacles fixes gardés, reste de l'état figé au départ » calculée UNE fois : graphe des positions de
    l'objet piloté (parcours en largeur aux flèches dans le simulateur, depuis le départ), cibles = centres des objets
    non pilotés lus par la victoire, distances inverses depuis les cibles (centre du piloté = centre d'une cible).
    → (fonction scène → distance ou None, infos) ; None : hors du graphe ou cible inatteignable (« non pris en charge »)."""
    from chrysalide.arc3.sim_rapide import cloner
    fleches = [c for c in coups if nom(c)[0] in ("UP", "DOWN", "LEFT", "RIGHT")]

    def sig(o):
        px = np.asarray(o["pixels"])
        return o.get("nom"), tuple(o.get("tags") or ()), tuple(sorted(set(px[px >= 0].ravel().tolist())))

    def centre(o):
        px = np.asarray(o["pixels"])
        return o["x"] + px.shape[1] // 2, o["y"] + px.shape[0] // 2
    etat0 = prog.etat
    depl = {}
    for c in fleches:
        s2, e2 = cloner(sc0, etat0)
        prog.etat = e2
        try:
            prog.step(s2, nom(c))
        except Exception:  # noqa: BLE001, S112
            continue
        if len(s2.sprites) == len(sc0.sprites):
            for a, b in zip(sc0.sprites, s2.sprites, strict=True):
                depl.setdefault(sig(a), set()).add((b["x"] - a["x"], b["y"] - a["y"]))
    pil = {s for s, ds in depl.items() if len(ds) > 1 and any(d != (0, 0) for d in ds)}
    infos = {"pilotes": len(pil)}
    if not pil:
        prog.etat = etat0
        return (lambda sc: None), {**infos, "statut": "pas d'objet piloté"}

    def pos(sc):
        return tuple(sorted(centre(o) for o in sc.sprites if sig(o) in pil and o.get("visible", True)))
    filtres, _ = lus_par_le_but(prog.p, regle)
    cibles = set()
    for f in filtres:
        try:
            V = prog._V
            V[0] = sc0
            for o in prog.c(["objets", f], {})(V):
                if sig(o) not in pil:
                    cibles.add(centre(o))
        except Exception:  # noqa: BLE001, S112
            continue
    voisins, vus, file = {}, {pos(sc0)}, deque([(sc0, etat0)])
    while file and len(vus) < max_pos:
        s, e = file.popleft()
        p = pos(s)
        for c in fleches:
            s2, e2 = cloner(s, e)
            prog.etat = e2
            try:
                prog.step(s2, nom(c))
            except Exception:  # noqa: BLE001, S112
                continue
            if s2.issue not in (None, "niveau", "victoire"):
                continue
            q = pos(s2)
            voisins.setdefault(p, set()).add(q)
            if q not in vus:
                vus.add(q)
                file.append((s2, prog.etat))
    prog.etat = etat0
    # distances inverses depuis les positions où un objet piloté est centré sur une cible
    inverse = {}
    for p, qs in voisins.items():
        for q in qs:
            inverse.setdefault(q, set()).add(p)
    buts = [p for p in vus if any(c in cibles for c in p)]
    dist = {p: 0 for p in buts}
    file2 = deque(buts)
    while file2:
        q = file2.popleft()
        for p in inverse.get(q, ()):
            if p not in dist:
                dist[p] = dist[q] + 1
                file2.append(p)
    infos.update(positions=len(vus), cibles=len(cibles), atteignables=len(dist), statut="ok" if buts else "cible hors d'atteinte")
    return (lambda sc: dist.get(pos(sc))), infos


# ------------------------------------------------------------------ V1-B (CW-351.4) : h_max lu dans les relations de C
def _cases(o):
    px = np.asarray(o["pixels"])
    ys, xs = np.nonzero(px >= 0)
    return {(int(o["x"] + x), int(o["y"] + y)) for x, y in zip(xs, ys, strict=True)}


def _classe(o):
    px = np.asarray(o["pixels"])
    v = px[px >= 0]
    return int(v[0]) if v.size else None


def h_relations(th):
    """→ fonction (scène du programme exporté de la théorie th) → h_max relâché, ou None (non pris en charge).
    Relations lues dans la théorie de C (aucune extraction en double) : pas des flèches (`moves`), classes solides,
    portes tenues (`tenue_cases` : R part et A arrive tant qu'un mobile occupe S), but (`centre`/`sortie`, cm → cs).
    h = min(d_fermée, max(coût d'ouverture, d_ouverte)) ; coût d'ouverture = distance du joueur jusqu'à poser une de
    ses cases sur S (persistance fictive : la porte reste ouverte une fois payée, piège noté par Astra)."""
    but = getattr(th, "but", None)
    if not but or but[0] not in ("centre", "sortie"):
        return None
    cm, cs = but[1], but[2]
    pas = {a: d for (c, a), d in th.moves.items() if c == cm}
    if not pas:
        return None
    solides = set(th.solides) - {cm}
    portes = list(getattr(th, "tenue_cases", ()))

    def h(sc):
        objs = [(o, _classe(o)) for o in sc.sprites if o.get("visible", True)]
        joueur = [o for o, c in objs if c == cm]
        cibles = [o for o, c in objs if c == cs]
        if not joueur or not cibles:
            return None
        j = _cases(joueur[0])
        mur = {z for o, c in objs if c in solides for z in _cases(o)}
        # sol : classe(s) sous le joueur (AMODAL la garde) ; si la théorie n'a pas de solides, seules ses cases sont
        # praticables (g50t : on ne marche que sur le sol)
        sols = {c for o, c in objs if c != cm and _cases(o) & j}
        sol = {z for o, c in objs if c in sols for z in _cases(o)}

        def bfs(bloque, arrive, max_n=4000, praticable=None):
            vus, file = {(0, 0): 0}, deque([(0, 0)])
            while file and len(vus) < max_n:
                d = file.popleft()
                if arrive(d):
                    return vus[d]
                for dx, dy in pas.values():
                    e = (d[0] + dx, d[1] + dy)
                    if e in vus or any((x + e[0], y + e[1]) in bloque for x, y in j):
                        continue
                    if praticable is not None and not all((x + e[0], y + e[1]) in praticable for x, y in j):
                        continue
                    vus[e] = vus[d] + 1
                    file.append(e)
            return None

        # 'centre' comme `Theorie._vrai` : centre de la boîte du joueur à ≤ 1 case (Chebyshev) d'une case d'un b de ≤ 2 cases
        cx2 = min(x for x, _ in j) + max(x for x, _ in j)
        cy2 = min(y for _, y in j) + max(y for _, y in j)
        petits = {z for t in (_cases(o) for o in cibles) if len(t) <= 2 for z in t}

        def sur_cible(d):
            return any(max(abs(2 * x - cx2 - 2 * d[0]), abs(2 * y - cy2 - 2 * d[1])) <= 2 for x, y in petits) \
                if but[0] == "centre" else any((x + d[0], y + d[1]) in {z for o in cibles for z in _cases(o)} for x, y in j)
        prat = sol if not solides and sol else None
        meilleur = bfs(mur, sur_cible, praticable=prat)
        for pc, r_cases, a_cases, s_cases in portes:
            cout = bfs(mur, lambda d, s=s_cases: any((x + d[0], y + d[1]) in s for x, y in j), praticable=
                       (prat | set(s_cases)) if prat is not None else None)
            if cout is None:
                continue
            if prat is not None:  # porte ouverte : le sol gagne ses cases A (si la loi porte sur le sol) et perd R
                p2 = (prat | set(a_cases)) - set(r_cases) if pc in sols else prat
                p2 = p2 | {z for e in portes if e[0] in sols for z in e[2]}
                ouverte = bfs(mur, sur_cible, praticable=p2)
            else:
                ouverte = bfs((mur - set(r_cases)) | set(a_cases), sur_cible)
            if ouverte is not None:
                v = max(cout, ouverte)
                meilleur = v if meilleur is None else min(meilleur, v)
        return meilleur
    return h


def meilleur_dabord(texte, sc0, etat0, noms, h, noeuds=200000, secondes=300):
    """Recherche meilleur d'abord sur un programme fourni (théorie exportée), priorité (h, profondeur), clé
    `cle_complete` ; h None → ordonné en dernier (jamais élagué). → (plan en noms d'action | None, infos)."""
    import heapq
    import time

    from chrysalide.arc3.logique.plan_langage import cle_complete
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    T, t0 = time.process_time, time.process_time()
    prog = ProgrammeCompile(texte)
    prog.etat = etat0 if etat0 is not None else prog.etat
    h0 = h(sc0)
    tas, vus, n, k = [((h0 if h0 is not None else 10 ** 6), 0, 0, sc0, prog.etat, [])], {cle_complete(sc0, prog.etat)}, 0, 1
    hmin = h0
    while tas and n < noeuds and T() - t0 < secondes:
        _, g, _, sc, et, ch = heapq.heappop(tas)
        for a in noms:
            n += 1
            s2, e2 = cloner(sc, et)
            prog.etat = e2
            try:
                prog.step(s2, a)
            except Exception:  # noqa: BLE001, S112
                continue
            if s2.issue in ("niveau", "victoire"):
                return [*ch, a], {"noeuds": n, "h0": h0, "hmin": hmin, "cpu": round(T() - t0, 1)}
            if s2.issue is not None:
                continue
            kk = cle_complete(s2, prog.etat)
            if kk in vus:
                continue
            vus.add(kk)
            v = h(s2)
            hmin = v if hmin is None or (v is not None and v < hmin) else hmin
            heapq.heappush(tas, ((v if v is not None else 10 ** 6), g + 1, k, s2, prog.etat, [*ch, a]))
            k += 1
    return None, {"noeuds": n, "h0": h0, "hmin": hmin, "cpu": round(T() - t0, 1), "etats": len(vus)}
