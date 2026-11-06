# SPDX-License-Identifier: MIT-0
"""C (CW-369 / 370 / 371) : noyau ASP qui JOUE. Prototype, drapeau éteint (aucun appel depuis le moteur).
Deux étages (docs/ONTOLOGIE_FORMELLE_GDL_VGDL.md) :
- étage 1, axiomes universels GDL en ASP : `does` (une action par pas tant que la partie n'est pas finie), `next` par
  effets + persistance, `terminal` (gagne / perdu, la victoire prime), `goal` ;
- étage 2, règles du jeu tirées de la THÉORIE INDUITE (`Theorie`) : la relation de transition de base (pas du piloté,
  collisions aux cases, fond solide, portes qui bloquent) est CALCULÉE par la théorie Python elle-même, case par case,
  et donnée au solveur en tables (`mv(P, porte, action, Q)`) : rien n'est réécrit à la main ; les extensions à mémoire
  (E4 : retour au départ, fantôme qui rejoue le trajet de la vie précédente, porte tenue par une dalle, écrasement)
  sont des règles ASP.
Couverture : un piloté (une classe de `moves`), `retour`, `fantome`, `tenue_cases` (une porte), `portes_cases`, but
quelconque évalué par `Theorie._vrai` sur la position du piloté. Usage : `planifier(th, monde, taille, but, horizon)`."""
import time

import clingo

from chrysalide.arc3.logique.theorie import MEM_FANTOME, MEM_TRAJET, Theorie, cells

NOMS = {1: "up", 2: "down", 3: "left", 4: "right", 5: "space"}

AXIOMES = """
% ---- étage 1 : axiomes universels (GDL) ----
time(0..h). step(0..h-1).
1 { does(A,T) : action(A) } 1 :- step(T), not fini(T).
fini(T) :- gagne(T).
fini(T+1) :- fini(T), step(T).
perdu(T) :- defaite(T), not gagne(T).
:- perdu(T).
:- not gagne_un.
gagne_un :- gagne(T).
"""

REGLES = """
% ---- étage 2 : règles du jeu (théorie induite) ----
% déplacement de base (table calculée par la théorie) ; SPACE = retour au départ
at(Q,T+1) :- at(P,T), does(A,T), A != space, porte(D,T), mv(P,D,A,Q), step(T), not fini(T).
at(S,T+1) :- does(space,T), depart(S), step(T), not fini(T).
at(P,T+1) :- at(P,T), fini(T), step(T).
eff(T) :- at(P,T), at(Q,T+1), P != Q, does(A,T), A != space.
% mémoire (E4) : cum(T) = pas effectifs avant T ; segments séparés par les SPACE (avant le plan : histoire donnée)
cum(T,N) :- time(T), N = #count{ U : eff(U), U < T }.
ret(T) :- does(space,T).
debut(-1).                                    % début du segment en cours au départ du plan (histoire)
debut(T+1) :- ret(T).
seg(T,S) :- time(T), debut(S), S <= T, not plus_recent(S,T).
plus_recent(S,T) :- debut(S), debut(S2), S < S2, S2 <= T, time(T).
% trajet du segment en cours : non vide si un pas effectif depuis son début
plein_traj(T) :- seg(T,S), cum(T,N), cumd(S,M), N > M.
cumd(-1,M) :- hist_cum(M).
cumd(S,M) :- debut(S), S >= 0, cum(S,M).
% fantôme : créé au SPACE si trajet non vide et pas de fantôme ; un SPACE avec fantôme l'efface
fant(T+1,S) :- ret(T), plein_traj(T), not fant_vivant(T), seg(T,S).
fant(T+1,F) :- fant(T,F), not ret(T), step(T).
fant(T+1,F) :- fant(T,F), ret(T), not plein_traj(T), step(T).
fant_vivant(T) :- fant(T,_).
fant(0,F) :- hist_fant(F).
% index du fantôme : pas effectifs depuis sa création, plafonné à la longueur du trajet enregistré
nait(F,R) :- fant(R,F), R > 0, not fant(R-1,F).
longueur(F,L) :- nait(F,R), cumd(F,A), cum(R-1,B), L = B - A.
idx(T,F,K) :- fant(T,F), F >= -1, nait(F,R), cum(T,N), cum(R,M), longueur(F,L), K = #min{ N-M ; L }.
idx(T,-2,K) :- fant(T,-2), hist_idx0(K0), cum(T,N), hist_longueur(-2,L), K = #min{ K0+N ; L }.
% position du fantôme : position du piloté juste après le K-ième pas effectif du segment F (ou départ si K = 0)
gpos(T,P) :- idx(T,F,0), depart(P).
gpos(T,P) :- idx(T,F,K), K > 0, F >= -1, cumd(F,A), A+K > 0, cum(U,A+K), eff(U-1), at(P,U), U >= 1.
gpos(T,P) :- idx(T,F,K), K > 0, F >= -1, cumd(F,A), A+K <= 0, hist_at(A+K,P).
gpos(T,P) :- idx(T,-2,K), K > 0, hist_pos(-2,K,P).
% porte tenue : ouverte tant que le piloté ou le fantôme est sur la dalle
porte(ouverte,T) :- at(P,T), dalle(P).
porte(ouverte,T) :- gpos(T,P), dalle(P).
porte(fermee,T) :- time(T), not porte(ouverte,T).
defaite(T) :- porte(fermee,T), at(P,T), ecrase(P).
gagne(T) :- at(P,T), but(P).
"""


def _monde(base, pilote, p, portes):
    """Monde de la théorie : décor + portes dans leur configuration + piloté en p."""
    c, forme = pilote
    out = [*base, *portes]
    out.append((c, forme, p[0], p[1]))
    return tuple(sorted(out))


def tables(th: Theorie, monde, taille, but):
    """Tables de l'étage 2, calculées par la théorie : positions atteignables du piloté (exploration des pas de base,
    les deux états de la porte), transitions, dalle, écrasement, but."""
    c = next(iter(sorted({k for k, _a in th.moves})))
    pj = next(o for o in monde if o[0] == c)
    pilote = (c, pj[1])
    cg = th.fantome[2] if th.fantome else None
    base = [o for o in monde if o[0] < 1024 and o[0] != c and o[0] != cg]
    cfg = {"ouverte": [], "fermee": []}
    dalles = {frozenset(t[3]) for t in th.tenue_cases}
    if len(dalles) > 1:
        raise NotImplementedError("portes tenues par des dalles différentes : un état de porte par dalle (à faire)")
    dalle_cases = next(iter(dalles)) if dalles else frozenset()
    for p_, r_cases, a_cases, _s in th.tenue_cases:  # toutes les portes de la même dalle : un seul état
        ens = {z for o in base if o[0] == p_ for z in cells(o)}
        base = [o for o in base if o[0] != p_]
        for nom, cs in (("ouverte", (ens - r_cases) | a_cases), ("fermee", (ens - a_cases) | r_cases)):
            if cs:
                x0, y0 = min(x for x, _ in cs), min(y for _, y in cs)
                cfg[nom].append((p_, frozenset((x - x0, y - y0) for x, y in cs), x0, y0))
    sauve = (th.retour, th.fantome, th.tenue_cases)
    th.retour, th.fantome, th.tenue_cases = (), None, ()  # pas de BASE seulement (le reste est dans l'ASP)
    try:
        vus, file, mv = {(pj[2], pj[3])}, [(pj[2], pj[3])], []
        depart = next(((x, y) for k, a, x, y in sauve[0] if k == c), (pj[2], pj[3]))
        if depart not in vus:
            vus.add(depart)
            file.append(depart)
        while file:
            p = file.pop()
            for d, porte in cfg.items():
                for a in (1, 2, 3, 4):
                    if (c, a) not in th.moves:
                        continue
                    res, _ = th._pas(_monde(base, pilote, p, porte), a, taille)
                    q = next(((o[2], o[3]) for o in res if o[0] == c), p)
                    mv.append((p, d, a, q))
                    if q not in vus:
                        vus.add(q)
                        file.append(q)
    finally:
        th.retour, th.fantome, th.tenue_cases = sauve
    forme = pj[1]
    dalle = [p for p in vus if {(x + p[0], y + p[1]) for x, y in forme} & dalle_cases]
    ecrase = []
    for p in vus:  # theorie._tenir_cases : porte (portes_cases) refermée sur le piloté
        pc = {(x + p[0], y + p[1]) for x, y in forme}
        w = _monde(base, pilote, p, cfg["fermee"])
        if any(cs & pc & {z for o in w if o[0] == pp for z in cells(o)} for pp, cs in th.portes_cases):
            ecrase.append(p)
    buts = [p for p in vus if Theorie._vrai(but, _monde(base, pilote, p, cfg["fermee"]))]
    return {"pilote": c, "depart": depart, "vus": sorted(vus), "mv": mv, "dalle": dalle, "ecrase": ecrase, "but": buts}


def histoire(th, monde):
    """Faits d'histoire au départ du plan : pas effectifs du segment en cours, fantôme vivant (trajet, index)."""
    from chrysalide.arc3.logique.theorie import _CHEMINS
    mem = [o for o in monde if o[0] == MEM_TRAJET]
    rec = _CHEMINS.get(mem[0][2], ()) if mem else ()
    fants = [(o[2], o[3]) for o in monde if o[0] == MEM_FANTOME]
    # cum compte les pas effectifs depuis le début du plan : le segment en cours a commencé len(rec) pas plus tôt
    faits = [f"hist_cum({-len(rec)})."]
    if th.fantome:  # positions du piloté après chaque pas du segment en cours (parti du départ), cum ≤ 0
        _cj, _b, _cg, x, y = th.fantome
        for i, d in enumerate(rec, 1):
            x, y = x + d[0], y + d[1]
            faits.append(f"hist_at({i - len(rec)},p({x},{y})).")
    if fants and th.fantome:
        pid, k = fants[0]
        chemin = _CHEMINS.get(pid, ())
        _cj, _b, _cg, x0, y0 = th.fantome
        faits += ["hist_fant(-2).", f"hist_longueur(-2,{len(chemin)})."]
        x, y = x0, y0
        for i, d in enumerate(chemin, 1):
            x, y = x + d[0], y + d[1]
            faits.append(f"hist_pos(-2,{i},p({x},{y})).")
        faits.append(f"hist_idx0({k}).")
    return faits, rec


def _borne(horizon, reserve):
    """CW-381 : un plan ne dépasse jamais la réserve de coups apprise (F : `economie_plan`, h = R suffit)."""
    return min(horizon, reserve) if reserve is not None else horizon


def planifier(th, monde, taille, but, horizon=30, limite_s=60, reserve=None):
    """→ {"plan": [noms d'actions] ou None, "horizon", "cpu_s", "tables": tailles}. Horizons croissants (1..horizon),
    bornés par la réserve de coups apprise (`reserve`, CW-381)."""
    horizon = _borne(horizon, reserve)
    t0 = time.process_time()
    tb = tables(th, monde, taille, but)
    hist, _rec = histoire(th, monde)
    p0 = next((o[2], o[3]) for o in monde if o[0] == tb["pilote"])
    f = [f"action({NOMS[a]})." for a in (1, 2, 3, 4)] + ["action(space)."]
    f += [f"at(p({p0[0]},{p0[1]}),0).", f"depart(p({tb['depart'][0]},{tb['depart'][1]}))."]
    f += [f"mv(p({p[0]},{p[1]}),{d},{NOMS[a]},p({q[0]},{q[1]}))." for p, d, a, q in tb["mv"]]
    f += [f"dalle(p({x},{y}))." for x, y in tb["dalle"]] + [f"ecrase(p({x},{y}))." for x, y in tb["ecrase"]]
    f += [f"but(p({x},{y}))." for x, y in tb["but"]]
    f += hist
    texte = AXIOMES + REGLES + "\n".join(f)
    for h in range(1, horizon + 1):
        ctl = clingo.Control(["--models=1", f"-c h={h}"])
        ctl.add("base", [], texte)
        ctl.ground([("base", [])])
        plan = []

        def surm(m, plan=plan):
            plan[:] = sorted((s.arguments[1].number, s.arguments[0].name) for s in m.symbols(shown=True)
                              if s.name == "does")
        r = ctl.solve(on_model=surm)
        if r.satisfiable:
            return {"plan": [a for _, a in plan], "horizon": h, "cpu_s": round(time.process_time() - t0, 2),
                    "tables": {k: len(v) for k, v in tb.items() if isinstance(v, list)}}
        if time.process_time() - t0 > limite_s:
            break
    return {"plan": None, "horizon": h, "cpu_s": round(time.process_time() - t0, 2),
            "tables": {k: len(v) for k, v in tb.items() if isinstance(v, list)}}


# ------------------------------------------------ ka59 N4 : sélection au clic (E1), glissade (E7), emboîter (E3)
REGLES_SEL = """
% objets mobiles O (pièces de la classe pilotée, blocs poussables) ; sel(O,T) : la pièce sélectionnée
1 { does(A,T) : action(A) } 1 :- step(T), not fini(T).
sel(O,T+1) :- does(clic(O),T), step(T), not fini(T).
sel(O,T+1) :- sel(O,T), not clic_fait(T), step(T).
clic_fait(T) :- does(clic(_),T).
% cases occupées par chaque mobile (anneau + trou porteur d'un passager)
occ(O,X+DX,Y+DY,T) :- at(O,X,Y,T), forme(O,DX,DY).
% la pièce sélectionnée S avance de V : si elle rencontrerait un autre mobile, c'est une POUSSÉE
cible(S,X+DX+VX,Y+DY+VY,A,T) :- sel(S,T), at(S,X,Y,T), forme(S,DX,DY), vec(A,VX,VY), does(A,T).
pousse(S,P,A,T) :- cible(S,X,Y,A,T), occ(P,X,Y,T), P != S, poussable(P).
pousse_un(S,A,T) :- pousse(S,_,A,T).
% déplacement normal : pas statiquement possible et aucun mobile devant
at(S,X+VX,Y+VY,T+1) :- sel(S,T), at(S,X,Y,T), does(A,T), vec(A,VX,VY), mv_ok(S,X,Y,A), not pousse_un(S,A,T).
% glissade du poussé P (depuis SA position X,Y : la position est dans chaque atome, sinon le fondement croise toutes
% les longueurs avec toutes les positions) : le J-ième pas est possible s'il l'est statiquement et ne touche aucun mobile
gl_bloque(P,X,Y,A,J,T) :- pousse(S,P,A,T), at(P,X,Y,T), vec(A,VX,VY), j(J), forme(P,DX,DY),
                          occ(Q,X+DX+J*VX,Y+DY+J*VY,T), Q != P, Q != S.
gl_ok(P,X,Y,A,J,T) :- pousse(_,P,A,T), at(P,X,Y,T), j(J), gl_stat(P,X,Y,A,J), not gl_bloque(P,X,Y,A,J,T).
gl_k(P,X,Y,A,1,T) :- gl_ok(P,X,Y,A,1,T).
gl_k(P,X,Y,A,J,T) :- gl_ok(P,X,Y,A,J,T), gl_k(P,X,Y,A,J-1,T), J > 1.
gl_n(P,X,Y,A,K,T) :- pousse(_,P,A,T), at(P,X,Y,T), K = #max{ J : gl_k(P,X,Y,A,J,T) ; 0 }.
at(P,X+K*VX,Y+K*VY,T+1) :- gl_n(P,X,Y,A,K,T), vec(A,VX,VY).
% persistance (A-U2) : tout mobile qui n'a pas bougé reste ; « bougé » se lit sur ses CAUSES (pas, glissade), pas en
% comparant des paires de positions (quadratique au fondement) ; l'unicité de position (A-U3) découle des règles
bouge(S,T) :- sel(S,T), does(A,T), vec(A,_,_), at(S,X,Y,T), mv_ok(S,X,Y,A), not pousse_un(S,A,T).
bouge(P,T) :- gl_n(P,_,_,_,K,T), K > 0.
at(O,X,Y,T+1) :- at(O,X,Y,T), step(T), not bouge(O,T), not fini(T).
at(O,X,Y,T+1) :- at(O,X,Y,T), fini(T), step(T).
% but « emboîter » : chaque cible (centre ×2) porte le centre (×2) d'un mobile d'une classe permise, à 2 près
centre2(O,2*X+W-1,2*Y+H-1,T) :- at(O,X,Y,T), taille(O,W,H).
remplie(C,T) :- cible(C,CX,CY), permis(C,K), classe(O,K), centre2(O,X,Y,T), |X-CX| <= 2, |Y-CY| <= 2.
gagne(T) :- time(T), #count{ C : cible(C,_,_), not remplie(C,T) } = 0.
"""


def planifier_selection(th, monde, taille, but, horizon=40, limite_s=600, direct=False, reserve=None):
    """Noyau ASP pour un niveau à sélection au clic + glissade + emboîter (ka59 N4). Les validités qui ne dépendent que du
    décor fixe (grille, cases exclues, fond solide, solides fixes ; pour la glissade : classes traversées) sont CALCULÉES
    en Python selon les règles de la théorie (`_pas`, `_glisser`) ; ce qui dépend des mobiles est en ASP aux cases."""
    from chrysalide.arc3.logique.theorie import FIGE, _enclos
    horizon = _borne(horizon, reserve)  # CW-381 : borné par la réserve apprise
    t0 = time.process_time()
    c = th.selection_clic[0]
    dmax, trav = th.glisse[:2]
    par_classe = dict(th.glisse[3]) if len(th.glisse) > 3 else {}
    prolonge = set(th.glisse[4]) if len(th.glisse) > 4 else set()
    poussees = {c} | set(th.glisse[2] if len(th.glisse) > 2 else ())
    fam = lambda k: (k - 512) % 16 if 512 <= k < 1024 else k % 16 if k >= 16 else k
    mob = [o for o in monde if o[0] < 1024 and (fam(o[0]) == fam(c) and len(o[1]) > 1 or o[0] in poussees and o[0] != c
                                                 and len(o[1]) > 1)]
    passagers = {i: [q for q in monde if q[0] < 1024 and q not in mob and _enclos(o, q)] for i, o in enumerate(mob)}
    pris = {q for qs in passagers.values() for q in qs}
    fixes = [o for o in monde if o[0] < 1024 and o not in mob and o not in pris]
    w, h = taille
    hj = th.hors_jeu
    stat = {}
    for o in fixes:
        for z in cells(o):
            stat.setdefault(z, set()).add(o[0])
    v = {a: th.moves[(c, a)] for a in (1, 2, 3, 4) if (c, a) in th.moves}
    step = max(abs(x) + abs(y) for x, y in v.values())
    solides_fixes = {k for k in th.solides if k not in poussees and fam(k) != fam(c) and k < FIGE}
    faits = [f"action({NOMS[a]}). vec({NOMS[a]},{x},{y})." for a, (x, y) in v.items()]
    faits += [f"j(1..{3 * max([dmax, *par_classe.values()]) // step})."]
    for i, o in enumerate(mob):
        forme = cells((o[0], o[1], 0, 0)) | {(q[2] - o[2], q[3] - o[3]) for q in passagers[i]}
        bx = (max(x for x, _ in o[1]) + 1, max(y for _, y in o[1]) + 1)
        k = c if fam(o[0]) == fam(c) else o[0]
        faits += [f"at(o{i},{o[2]},{o[3]},0).", f"classe(o{i},{k}).", f"taille(o{i},{bx[0]},{bx[1]})."]
        faits += [f"forme(o{i},{dx},{dy})." for dx, dy in sorted(forme)]
        if k == c:
            faits.append(f"action(clic(o{i})).")
        if o[0] in poussees or k == c:
            faits.append(f"poussable(o{i}).")
        anneau = cells((o[0], o[1], 0, 0))
        # positions atteignables : le réseau du pas autour du départ
        xs = range(o[2] % step - step if o[2] % step else 0, w, step)
        ys = range(o[3] % step - step if o[3] % step else 0, h, step)
        for x in xs:
            for y in ys:
                for a, (vx, vy) in v.items():
                    cs = {(dx + x + vx, dy + y + vy) for dx, dy in anneau}
                    ok = all(0 <= p < w and 0 <= q < h and (q, p) not in hj and stat.get((p, q))
                             and not (stat.get((p, q), set()) & solides_fixes) for p, q in cs)
                    if ok and k == c:
                        faits.append(f"mv_ok(o{i},{x},{y},{NOMS[a]}).")
                    propres = {(dx + x, dy + y) for dx, dy in anneau}
                    for jj in range(1, 3 * dmax // step + 1):
                        if jj * step > par_classe.get(fam(o[0]), dmax):  # prolongation : chevauche encore la barrière
                            avant_pas = {(dx + x + vx * (jj - 1), dy + y + vy * (jj - 1)) for dx, dy in anneau}
                            if not any(stat.get(z, set()) & prolonge for z in avant_pas):
                                break
                        cs = {(dx + x + vx * jj, dy + y + vy * jj) for dx, dy in anneau}
                        if all(0 <= p < w and 0 <= q < h and not (stat.get((p, q), set()) - set(trav))
                               and (stat.get((p, q)) or (p, q) in propres) for p, q in cs):
                            faits.append(f"gl_stat(o{i},{x},{y},{NOMS[a]},{jj}).")
                        else:
                            break
    from chrysalide.arc3.logique.theorie import SEL_CLIC
    v = [o for o in monde if o[0] == SEL_CLIC]  # en cours de partie : la sélection courante (objet virtuel)
    ref = (v[0][2], v[0][3]) if v else tuple(th.selection_clic[1:])
    isel = next(i for i, o in enumerate(mob) if (o[2], o[3]) == ref)
    faits.append(f"sel(o{isel},0).")
    _k, centres, _pieces, *ex = but
    exige = dict(ex[0]) if ex else {}
    for n, (cx, cy) in enumerate(centres):
        faits.append(f"cible(t{n},{cx},{cy}).")
        permis = ([exige[(cx, cy)]] if (cx, cy) in exige  # une classe à moule ne remplit que son moule
                  else sorted(({c} | {o[0] for o in mob if fam(o[0]) != fam(c)}) - set(exige.values())))
        faits += [f"permis(t{n},{k})." for k in permis]
    texte = AXIOMES.replace("1 { does(A,T) : action(A) } 1 :- step(T), not fini(T).", "") + REGLES_SEL + "\n".join(faits)
    # pas de 2 : un plan de longueur impaire sort à l'horizon suivant (fini persiste) ; `direct` : un seul horizon
    for hh in ([horizon] if direct else range(2, horizon + 1, 2)):
        ctl = clingo.Control(["--models=1", f"-c h={hh}"])
        ctl.add("base", [], texte)
        ctl.ground([("base", [])])
        plan, pos = [], {}

        def surm(m, plan=plan, pos=pos):
            sy = m.symbols(shown=True)
            plan[:] = sorted((s.arguments[1].number, str(s.arguments[0])) for s in sy if s.name == "does")
            pos.update({(str(s.arguments[0]), s.arguments[3].number): (s.arguments[1].number, s.arguments[2].number)
                        for s in sy if s.name == "at" and len(s.arguments) == 4})
        r = ctl.solve(on_model=surm)
        if r.satisfiable:
            return {"plan": [_coup(a, mob, pos, t) for t, a in plan], "horizon": hh,
                    "cpu_s": round(time.process_time() - t0, 2), "mobiles": [(o[0], o[2], o[3]) for o in mob]}
        if time.process_time() - t0 > limite_s:
            break
    return {"plan": None, "horizon": hh, "cpu_s": round(time.process_time() - t0, 2),
            "mobiles": [(o[0], o[2], o[3]) for o in mob]}


def _coup(a, mob, pos, t):
    """Symbole ASP → coup : nom de flèche, ou ('clic', x, y) au centre de l'anneau de l'objet cliqué, À SA POSITION au
    moment du clic (pas celle du départ : une pièce poussée a pu glisser)."""
    if a.startswith("clic("):
        i = int(a[6:-1])
        o = mob[i]
        x0, y0 = pos.get((f"o{i}", t), (o[2], o[3]))
        xs, ys = [x for x, _ in o[1]], [y for _, y in o[1]]
        return ("clic", x0 + (min(xs) + max(xs)) // 2, y0 + (min(ys) + max(ys)) // 2)
    return a
