# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — induction de la théorie MINIMALE cohérente avec TOUTES les transitions observées (CW-067).
Python calcule la géométrie (ce que toucherait chaque objet s'il se déplaçait de v) ; clingo choisit les règles
(déplacement par couleur et action, solides, poussables, consommation, liens, autonomes) qui expliquent chaque
déplacement et chaque disparition observés, en minimisant le nombre de règles (rasoir d'Occam, ILP par ASP).
Puis : paramètres des autonomes par rejeu, prior « statique jamais traversé = solide », but parmi 2 familles du vocabulaire."""
import math
import os
import time

import clingo

from chrysalide.arc3.logique.faits import apparier
from chrysalide.arc3.logique.theorie import Theorie, _sous_clic, _voisinage, cells, cle_objet, monde_final, reflet, rejeu

PROGRAMME = """
{ move(C,A,V) : cand(C,A,V) }.
:- move(C,A,V1), move(C,A,V2), V1 != V2.
{ solide(C) : couleur(C) }.  { poussable(C) : couleur(C) }.  :- solide(C), poussable(C).
{ autonome(C) : couleur(C) }.
:- autonome(C), move(C,_,_).
{ consomme(C1,C2) : couleur(C1), couleur(C2), C1 != C2 }.
{ lie(C1,C2) : couleur(C1), couleur(C2), C1 != C2 }.
essai(T,I,V) :- objt(T,I,C), action(T,A), move(C,A,V).
bloque(T,I,V) :- essai(T,I,V), hors(T,I,V).
{ fond_solide }.
bloque(T,I,V) :- essai(T,I,V), vide(T,I,V), fond_solide.
bloque(T,I,V) :- essai(T,I,V), touche(T,I,V,J), objt(T,J,C2), solide(C2).
bloque(T,I,V) :- essai(T,I,V), touche(T,I,V,J), objt(T,J,C2), poussable(C2), pousse_ko(T,J,V).
pousse_ko(T,J,V) :- derriere_hors(T,J,V).
pousse_ko(T,J,V) :- derriere(T,J,V,K), objt(T,K,C3), solide(C3).
pousse_ko(T,J,V) :- derriere(T,J,V,K), objt(T,K,C3), poussable(C3).
bouge(T,I,V) :- essai(T,I,V), not bloque(T,I,V).
% saut (CCM-037-C, ls20 niveau 3) : déplacement CONDITIONNEL ; si le pas normal V est bloqué et que la case à 2V est
% libre, le mobile avance de 2V (sauter un mur). Gabarit à paramètres finis : V2 = double de V, observé.
{ saut(C,A,V2) : cand(C,A,V2), move(C,A,V), double(V,V2) }.
bloq(T,I,V) :- hors(T,I,V).
bloq(T,I,V) :- vide(T,I,V), fond_solide.
bloq(T,I,V) :- touche(T,I,V,J), objt(T,J,C2), solide(C2).
bouge(T,I,V2) :- essai(T,I,V), bloque(T,I,V), objt(T,I,C), action(T,A), saut(C,A,V2), not bloq(T,I,V2).
#minimize { W,sa,C,A : saut(C,A,V2), poids(sa,W)}.
bouge(T,J,V) :- bouge(T,I,V), touche(T,I,V,J), objt(T,J,C2), poussable(C2), essai(T,I,V).
libre(T,I) :- objt(T,I,C), autonome(C).
% prior de B (CW-083), révisable : un objet couvert puis revu identique à une place déjà vue était CACHÉ, pas déplacé
{ cache(T,I) : occultable(T,I) }.
libre(T,I) :- cache(T,I).
err(m,T,I) :- obs(T,I,V), V != v(0,0), not bouge(T,I,V), not libre(T,I).
err(m,T,I) :- bouge(T,I,V), obs(T,I,V2), V2 != V, not libre(T,I).
disparait_c(T,I) :- objt(T,I,C2), couvert(T,I,C1), consomme(C1,C2).
disparait(T,I) :- disparait_c(T,I).
disparait(T,I) :- objt(T,I,Cd), lie(Cd,Ct), epuise(T,Ct).
reste(T,Ct) :- objt(T,I,Ct), not disparait_c(T,I).
epuise(T,Ct) :- objt(T,_,Ct), not reste(T,Ct).
err(d,T,I) :- doit_disparaitre(T,I), not disparait(T,I).
err(d,T,I) :- disparait(T,I), present(T,I).
inexplique(T,I) :- objt(T,I,C), autonome(C), obs(T,I,V), V != v(0,0), not bouge(T,I,V).
#minimize { W,m,C,A : move(C,A,V), not ancienne(move(C,A,V)), poids(m,W); W,s,C : solide(C), not ancienne(solide(C)), poids(s,W);
            W,p,C : poussable(C), not ancienne(poussable(C)), poids(p,W); W,a,C : autonome(C), poids(a,W);
            2,i,T,I : inexplique(T,I) ; W,o,T,I : cache(T,I), poids(o,W);
            2,pz,C : poussable(C), not vu_bouger(C) ;
            W,c,C1,C2 : consomme(C1,C2), not ancienne(consomme(C1,C2)), poids(c,W); W,l,C1,C2 : lie(C1,C2), not ancienne(lie(C1,C2)), poids(l,W);
            W,f : fond_solide, not ancienne(fond_solide), poids(f,W)}.
% prior de continuité (CCM-022-C) : une loi déjà retenue au niveau précédent ne coûte rien
#defined ancienne/1. #defined double/2.
% --- transformation par modificateur (CW-087, P10) : un mobile atterrit sur M → les objets de classe C deviennent C2
{ transforme(M,C,C2) : couleur(M), couleur(C), couleur(C2), C != C2 }.  % M = C : l'objet sur lequel on se pose change
:- transforme(M,C,C1), transforme(M,C,C2), C1 != C2.
devient(T,J,C2) :- transforme(M,C,C2), objt(T,J,C), atterrit(T,M), action(T,_).
#minimize { W,tr,M,C,C2 : transforme(M,C,C2), not ancienne(transforme(M,C,C2)), poids(tr,W)}.
% --- clics (vocabulaire : sélection, bascule par clic avec motif de voisinage) ---
{ motif(D) : cand_motif(D) }.
{ bascule(C1,C2) : couleur(C1), couleur(C2), C1 != C2 }.
:- bascule(C,C1), bascule(C,C2), C1 != C2.
{ zone(K) : couleur(K) }.
:- zone(K1), zone(K2), K1 != K2.
zone_active :- zone(_).
cliquable(T,I) :- clic_obj(T,I), not zone_active.
cliquable(T,I) :- clic_obj(T,I), zone(K), dedans(T,I,K).
touche_clic(T,J) :- cliquable(T,I), off(T,I,J,D), motif(D).
devient(T,J,C2) :- touche_clic(T,J), objt(T,J,C), bascule(C,C2).
err(c,T,J) :- change(T,J,C2), not devient(T,J,C2).
err(c,T,J) :- devient(T,J,C2), not change(T,J,C2).
% observations non expliquées : comptées et minimisées EN PRIORITÉ (@2), puis le nombre de règles (@1)
#minimize { 1@2,K,T,I : err(K,T,I) }.
erreur(T) :- err(_,T,_).
{ exclusif }.
selectionne(T) :- touche_clic(T,I), objt(T,I,C), bascule(C,C2), vu_bouger(C2).
rebascule(T,J) :- exclusif, selectionne(T), objt(T,J,C), vu_bouger(C), not touche_clic(T,J).
{ desel(C1,C2) : couleur(C1), couleur(C2), C1 != C2 }.
:- desel(C,C1), desel(C,C2), C1 != C2.
devient(T,J,C2) :- rebascule(T,J), objt(T,J,C), desel(C,C2).
#minimize { W,mo,D : motif(D), not ancienne(motif(D)), poids(mo,W); W,b,C1,C2 : bascule(C1,C2), not ancienne(bascule(C1,C2)), poids(b,W);
            W,z,K : zone(K), poids(z,W); W,e : exclusif, poids(e,W);
            W,ds,C1,C2 : desel(C1,C2), poids(ds,W)}.
"""
MONTRER = "\n#show move/3. #show solide/1. #show poussable/1. #show autonome/1. #show consomme/2. #show lie/2.\n#show motif/1. #show bascule/2. #show zone/1. #show exclusif/0. #show desel/2. #show transforme/3. #show saut/3. #show fond_solide/0. #show cache/2. #show erreur/1.\n"


def faits(sources):
    """Faits ASP ; `sources` = [(traj, ts)]. L'observation est recalée à chaque pas (induction, pas prédiction).
    Les transitions de la k-ième trajectoire sont numérotées 100000·k + t."""
    F, couleurs, traverse, cands, geo = [], set(), set(), set(), []
    for k, (traj, ts) in enumerate(sources):
        for t in ts:
            a = traj.actions[t]
            T = 100000 * k + t
            if isinstance(a, tuple):
                F += faits_clic(traj, t, T, a, couleurs)
                continue
            e0, e1 = traj.etats[t], traj.etats[t + 1]
            F.append(f"action({T},{a}).")
            paires, nouveaux = apparier(e0, e1)
            # changement de classe (transforme) : un objet non apparié et un nouvel objet de même forme, proches
            libres_j = list(nouveaux)
            change = {}
            couv_e1 = {c for o in e1 for c in cells(o)}
            # un objet disparu SOUS un autre est d'abord supposé masqué : il ne passe qu'en second pour un changement
            ordre = sorted(range(len(paires)), key=lambda n, p=paires: cells(e0[p[n][0]]) <= couv_e1)
            for n_i in ordre:
                i, j = paires[n_i]
                if j is not None:
                    continue
                o = e0[i]
                prox = [jj for jj in libres_j if e1[jj][1] == o[1] and e1[jj][0] != o[0]
                        and abs(e1[jj][2] - o[2]) + abs(e1[jj][3] - o[3]) <= 2 * max(len(o[1]), 1)]
                if prox:
                    jj = min(prox, key=lambda q, o=o: abs(e1[q][2] - o[2]) + abs(e1[q][3] - o[3]))
                    libres_j.remove(jj)
                    change[i] = jj
                    paires[n_i] = (i, jj)
            futurs = {o for e in traj.etats[t + 2:max(ts) + 2] for o in e}  # sans regarder au-delà de l'apprentissage
            c1 = {}
            for o in e1:
                for p in cells(o):
                    c1.setdefault(p, set()).add(o[0])
            for cs in c1.values():  # deux couleurs sur une même case : chacune a été traversée (perception sans masquage)
                if len(cs) > 1:
                    traverse |= cs
            for i, o in enumerate(e0):
                couleurs.add(o[0])
                F.append(f"objt({T},{i},{o[0]}).")
            passes = {ob for e in traj.etats[:t + 1] for ob in e}  # objets déjà vus (passé seulement)
            atterris = set()
            for i, j in paires:
                if j is not None and (e1[j][2], e1[j][3]) != (e0[i][2], e0[i][3]):  # a bougé : sur quoi atterrit-il ?
                    arrivee = cells(e1[j])
                    atterris |= {oo[0] for k2, oo in enumerate(e0) if k2 != i and cells(oo) & arrivee}
            for m in atterris:
                F.append(f"atterrit({T},{m}).")
            for i, j in paires:
                o = e0[i]
                if j is not None:
                    dx, dy = e1[j][2] - o[2], e1[j][3] - o[3]
                    F.append(f"obs({T},{i},v({dx},{dy})). present({T},{i}).")
                    if i in change:
                        F.append(f"change({T},{i},{e1[j][0]}).")
                        couleurs.add(e1[j][0])
                    if (dx, dy) != (0, 0):
                        cands.add((o[0], a, (dx, dy)))
                        couv_o = {c for p in cells(o) for c in c1.get(p, ()) if c != o[0]}
                        if couv_o and e1[j] in passes and e1[j] not in e0:
                            F.append(f"occultable({T},{i}).")  # couvert ici, revu identique à une place déjà vue
                    continue
                couv = {c for p in cells(o) for c in c1.get(p, ()) if c != o[0]}
                for c in couv:
                    F.append(f"couvert({T},{i},{c}).")
                    traverse.add(o[0])
                if couv and o not in futurs:  # caché, puis revu au MÊME endroit, même forme, AUTRE classe : transformé
                    revu = next((ob for ob in futurs if ob[1] == o[1] and (ob[2], ob[3]) == (o[2], o[3])  # sous le
                                 and ob[0] != o[0]), None)  # mobile (interrupteur pressé, T4 y000 L2, CCM-083-C)
                    if revu is not None:
                        F.append(f"change({T},{i},{revu[0]}).")
                        couleurs.add(revu[0])
                        continue
                if o in futurs:
                    F.append(f"present({T},{i}).")      # caché puis revu : pas une disparition
                elif not couv:
                    F.append(f"doit_disparaitre({T},{i}).")
            geo.append((traj, t, T, a))
    cand_par = {}
    for c, a, v in cands:
        cand_par.setdefault((c, a), set()).add(v)
        F.append(f"cand({c},{a},v({v[0]},{v[1]})).")
    for (c, a), vs in cand_par.items():  # doubles observés (saut) : V2 = 2·V
        for v in vs:
            if (2 * v[0], 2 * v[1]) in vs:
                F.append(f"double(v({v[0]},{v[1]}),v({2 * v[0]},{2 * v[1]})).")
    for traj, t, T, a in geo:
        w, h = traj.taille
        dans = lambda cs, w=w, h=h: all(0 <= x < w and 0 <= y < h for x, y in cs)
        e0 = traj.etats[t]
        occ = [cells(o) for o in e0]
        for i, o in enumerate(e0):
            for v in cand_par.get((o[0], a), ()):
                vt = f"v({v[0]},{v[1]})"
                cib = cells(o, *v)
                if not dans(cib) or {(y, x) for x, y in cib} & traj.exclues:  # la jauge (ligne, colonne) est hors jeu
                    F.append(f"hors({T},{i},{vt}).")
                    continue
                couvertes = set().union(*[occ[j] for j in range(len(e0)) if j != i]) if len(e0) > 1 else set()
                if cib - couvertes:
                    F.append(f"vide({T},{i},{vt}).")  # une case visée n'est couverte par aucun objet : le fond
                for j, oj in enumerate(e0):
                    if j == i or oj[0] == o[0] or not occ[j] & cib:
                        continue
                    F.append(f"touche({T},{i},{vt},{j}).")
                    cj = cells(oj, *v)
                    if not dans(cj):
                        F.append(f"derriere_hors({T},{j},{vt}).")
                    for q, oq in enumerate(e0):
                        if q not in (i, j) and occ[q] & cj:
                            F.append(f"derriere({T},{j},{vt},{q}).")
    F += [f"couleur({c})." for c in couleurs]
    F += [f"vu_bouger({c})." for c in {c for c, _, _ in cands}]
    return "\n".join(F), couleurs, traverse


def faits_clic(traj, t, T, a, couleurs):
    """Clic en case (x, y) : objet cliqué, voisins de même forme (décalages candidats du motif), inclusion dans la boîte
    d'un objet d'une autre couleur (zone cliquable candidate), changement de couleur uniforme observé à t+1."""
    e0, g1 = traj.etats[t], traj.cases[t + 1]
    F = []
    for i, o in enumerate(e0):
        couleurs.add(o[0])
        F.append(f"objt({T},{i},{o[0]}).")
    clique = [i for i, o in enumerate(e0) if (a[1], a[2]) in cells(o)]
    for i, o in enumerate(e0):
        vals = {int(g1[y, x]) for x, y in cells(o) if 0 <= y < g1.shape[0] and 0 <= x < g1.shape[1]}
        if len(vals) == 1 and vals != {o[0]}:
            c2 = vals.pop()
            couleurs.add(c2)
            F.append(f"change({T},{i},{c2}).")
    for i in clique:
        o = e0[i]
        F.append(f"clic_obj({T},{i}).")
        bi = boite(o)
        for kk, ok in enumerate(e0):
            if ok[0] != o[0] and len(ok[1]) > len(o[1]) and contient(boite(ok), bi):
                F.append(f"dedans({T},{i},{ok[0]}).")
        portee = 2 * (max(bi[2] - bi[0], bi[3] - bi[1]) + 2)
        for j, oj in enumerate(e0):
            dx, dy = oj[2] - o[2], oj[3] - o[3]
            if oj[1] == o[1] and abs(dx) <= portee and abs(dy) <= portee:
                F.append(f"off({T},{i},{j},d({dx},{dy})). cand_motif(d({dx},{dy})).")
    return F


def boite(o):
    xs, ys = [x for x, _ in cells(o)], [y for _, y in cells(o)]
    return min(xs), min(ys), max(xs), max(ys)


def contient(b, c):
    return b[0] <= c[0] and b[1] <= c[1] and c[2] <= b[2] and c[3] <= b[3]


def resoudre_asp(texte, limite_s=60):
    """Dernier modèle (optimal si la recherche finit avant `limite_s`) ; renvoie (atomes, optimal, coût)."""
    ctl = clingo.Control(["--opt-mode=opt"], logger=lambda code, msg: None)
    ctl.add("base", [], PROGRAMME + texte + ("" if "poids(" in texte else faits_poids()) + MONTRER)
    ctl.ground([("base", [])])
    meilleur, cout = [], []

    def garder(m):
        meilleur[:] = [str(s) for s in m.symbols(shown=True)]
        cout[:] = m.cost

    with ctl.solve(on_model=garder, async_=True) as h:
        fini = h.wait(limite_s)
        if not fini:
            h.cancel()
        optimal = fini and h.get().exhausted
    return meilleur, optimal, cout


def enumerer_asp(texte, cout, k, tolerance, limite_s=60):
    """Jusqu'à k modèles distincts (projetés sur les règles) d'erreurs ≤ optimum et de règles ≤ optimum + tolérance."""
    borne = ",".join(str(c + (tolerance if i == len(cout) - 1 else 0)) for i, c in enumerate(cout))
    ctl = clingo.Control([f"--opt-mode=enum,{borne}", "--project", f"--models={k}"], logger=lambda code, msg: None)
    ctl.add("base", [], PROGRAMME + texte + ("" if "poids(" in texte else faits_poids()) + MONTRER)
    ctl.ground([("base", [])])
    modeles = []
    with ctl.solve(on_model=lambda m: modeles.append(([str(s) for s in m.symbols(shown=True)], list(m.cost))),
                   async_=True) as h:
        if not h.wait(limite_s):
            h.cancel()
    return sorted(modeles, key=lambda x: x[1])


def depuis_symboles(syms):
    th = Theorie()
    sol, pou, con, lie, aut = set(), set(), set(), set(), {}
    for s in syms:
        f = clingo.parse_term(s)
        args = f.arguments
        if f.name == "move":
            th.moves[(args[0].number, args[1].number)] = (args[2].arguments[0].number, args[2].arguments[1].number)
        elif f.name == "solide":
            sol.add(args[0].number)
        elif f.name == "poussable":
            pou.add(args[0].number)
        elif f.name == "consomme":
            con.add((args[0].number, args[1].number))
        elif f.name == "lie":
            lie.add((args[0].number, args[1].number))
        elif f.name == "autonome":
            aut[args[0].number] = None
        elif f.name == "motif":
            th.motif = th.motif | {(args[0].arguments[0].number, args[0].arguments[1].number)}
        elif f.name == "bascule":
            th.bascule[args[0].number] = args[1].number
        elif f.name == "zone":
            th.zone = args[0].number
        elif f.name == "exclusif":
            th.exclusif = True
        elif f.name == "saut":
            th.saut[(args[0].number, args[1].number)] = (args[2].arguments[0].number, args[2].arguments[1].number)
        elif f.name == "transforme":
            th.transforme = th.transforme | {(args[0].number, args[1].number, args[2].number)}
        elif f.name == "desel":
            th.desel[args[0].number] = args[1].number
        elif f.name == "fond_solide":
            th.fond_solide = True
    th.solides, th.poussables, th.consomme, th.lie, th.autonomes = (frozenset(sol), frozenset(pou), frozenset(con),
                                                                    frozenset(lie), aut)
    return th


def actions_inconnues(th, actions_offertes):
    """Actions offertes sans aucune règle dans la théorie (jamais vues produire un effet) : l'exploration doit les essayer
    en priorité, l'entropie des théories concurrentes y est nulle par construction (sn01, CCM-026-C)."""
    connues = {a for _, a in th.moves} | ({6} if th.motif else set()) | ({th.annule} if th.annule else set())
    return [a for a in actions_offertes if a not in connues]


def classes_inconnues(th, monde):
    """Classes présentes dans `monde` que la théorie n'a jamais observées (déclencheur du mini-tutoriel de B)."""
    return {o[0] for o in monde} - set(th.formes)


def buts_candidats(th, couleurs):
    ctrl = {c for c, _ in th.moves}
    fl = ctrl | {c2 for _, c, c2 in th.transforme if c in ctrl}  # un mobile transformé (attribut porté par sa classe)
    mob = fl | set(th.poussables)
    emboite = [th.but_emboite] if getattr(th, "but_emboite", None) else []  # E (CCM-054-E), sous CHRYS_BUT_EMBOITE
    centre = ([("centre", a, b) for a in sorted(fl) for b in sorted(couleurs)]  # E (CCM-042-E) ; a = b permis (g50t :
              if os.environ.get("CHRYS_BUT_CENTRE", "0") == "1" else [])       # joueur et point de sortie en 9)
    return ([("sortie", a, b) for a in sorted(fl) for b in sorted(couleurs) if b != a] + centre
            + [("ancre", a, b) for a in sorted(fl) for b in sorted(couleurs) if b != a]
            + [("remplir", a, b) for a in sorted(mob) for b in sorted(couleurs) if b != a]
            + [("absent", c, c) for c in sorted(th.bascule)]
            + buts_paires(th, couleurs)
            + buts_conditionnels(th, couleurs)
            + list(th.buts_motifs)
            + [("modele", a, b) for a in sorted(mob) for b in sorted(couleurs - th.couleurs_dynamiques())
               if a != b and len(th.formes.get(b, ())) >= 2]
            + emboite)  # en DERNIER : devant, il faisait perdre ar25 N1 (contrôle ARC, CCM-258-C)


def buts_motifs(etats):
    """Buts `motif_rel` (CW-228, ft09) : paires de couleurs (même, autre) des anneaux de 8 marques à 2 couleurs autour
    d'une case isolée, vues sur un état (les deux sens : laquelle des marques veut « même » est choisie par la démo)."""
    from chrysalide.arc3.logique.theorie import centres_motifs
    paires = set()
    for e in etats[:1] + etats[-1:]:
        col = {c: o[0] for o in e for c in cells(o)}
        for a in {o[0] for o in e}:
            for b in {o[0] for o in e}:
                if a < b and centres_motifs(col, {a, b}):
                    paires |= {(a, b), (b, a)}
    return [("motif_rel", a, b) for a, b in sorted(paires)]


def buts_statiques(th, sources, max_cibles=4):
    """C (CW-250 E1, but d'abord ; CHRYS_BUT_STATIQUE=1) : buts candidats qui ne dépendent PAS des lois apprises.
    - acteurs = classes vues changer (bouger, apparaître, changer de classe, disparaître) dans une transition observée ;
    - cibles = classes peu nombreuses (≤ max_cibles objets) de la 1re image, hors acteurs ;
    - formes : sortie / ancre / remplir (acteur → cible), absent (classe dont le nombre a baissé : « éliminer »),
      marques (petits objets isolés de la 1re image, à couvrir par des pièces).
    Chaque but porte ses OBLIGATIONS (CW-251, but comme contrat) : `th.obligations[but]` = acteurs à faire bouger et
    actions déjà vues les faire changer ; l'exploration teste d'abord les obligations non démontrées."""
    from collections import Counter
    acteurs, actions, baisse = set(), {}, set()
    for tr, *_ in sources:
        for t, a in enumerate(tr.actions):
            e0, e1 = tr.etats[t], tr.etats[t + 1]
            if set(e0) == set(e1):
                continue
            paires, nouveaux = apparier(e0, e1)
            for i, j in paires:
                if j is None or e1[j] != e0[i]:
                    acteurs.add(e0[i][0])
                    actions.setdefault(e0[i][0], set()).add(a if not isinstance(a, tuple) else "clic")
            acteurs |= {e1[j][0] for j in nouveaux}
            n0, n1 = Counter(o[0] for o in e0), Counter(o[0] for o in e1)
            baisse |= {c for c in n0 if n1.get(c, 0) < n0[c]}
    if not sources or not sources[0][0].etats:
        return []
    e0 = sources[0][0].etats[0]
    n = Counter(o[0] for o in e0)
    cibles = sorted(c for c, k in n.items() if k <= max_cibles and c not in acteurs)
    deja = {c for c, _ in th.moves}
    buts = [(f, a, b) for a in sorted(acteurs - deja) for b in cibles for f in ("sortie", "ancre", "remplir")]
    buts += [("absent", c, c) for c in sorted(baisse)]
    petits = {}
    for o in e0:
        if len(o[1]) <= 2 and o[0] not in acteurs and o[0] < 512 and n[o[0]] <= 6:
            petits.setdefault(o[0], []).append((o[2], o[3]))
    if petits and any(len(o[1]) > 2 and o[0] in acteurs for o in e0):
        buts.append(("marques", tuple((k, tuple(sorted(v))) for k, v in sorted(petits.items())), None))
    th.obligations = {b: {"acteurs": sorted({b[1]} if b[0] != "marques" else acteurs),
                          "actions_vues": sorted({str(x) for x in actions.get(b[1], ())}) if b[0] != "marques" else []}
                      for b in buts}
    return buts


def buts_conditionnels(th, couleurs):
    """But conditionnel (CW-087) : sortie atteinte par un mobile ET un indicateur dans la classe produite par un
    modificateur (attribut conforme). Si c'est le mobile lui-même qui change, c'est déjà « sortie » par sa nouvelle classe."""
    fl = {c for c, _ in th.moves}
    ks = sorted({c2 for _, c, c2 in th.transforme if c not in fl})
    return [("sortie_si", a, b, k) for k in ks for a in sorted(fl) for b in sorted(couleurs) if b not in (a, k)]


def buts_paires(th, couleurs):
    """But conjonctif : chaque cible couverte par un objet de sa « famille » (couleur et sa couleur basculée)."""
    fl = {c for c, _ in th.moves}
    # famille = composante connexe du graphe des bascules, dans les deux sens (3↔6 ; 14→15 suffit à relier 14 et 15)
    voisins = {}
    for a, b in list(th.bascule.items()) + list(th.desel.items()):
        voisins.setdefault(a, set()).add(b)
        voisins.setdefault(b, set()).add(a)

    def famille(c):
        vu, pile = {c}, [c]
        while pile:
            for d in voisins.get(pile.pop(), ()):
                if d not in vu:
                    vu.add(d)
                    pile.append(d)
        return tuple(sorted(vu))

    fams = sorted({famille(c) for c in fl})
    cibles = sorted(c for c in couleurs if not any(c in f for f in fams))
    res = []
    for i, f1 in enumerate(fams):
        for f2 in fams[i + 1:]:
            for b1 in cibles:
                for b2 in cibles:
                    if b1 != b2:
                        res.append(("paires", ((f1, b1), (f2, b2)), None))
    return res


class _SansDerives:
    """Vue d'une trajectoire sans les objets dérivés (ils sont expliqués à part, par trouver_derives)."""

    def __init__(self, tr, classes):
        self._tr = tr
        self.etats = [tuple(o for o in e if o[0] not in classes) for e in tr.etats]

    def __getattr__(self, nom):
        return getattr(self._tr, nom)


def trouver_derives(trajs, tss=None):
    """Miroir (vocabulaire de B) : classe D à un seul objet, de forme variable, dont les cases sont exactement
    source ∪ reflet(source) dans TOUS les états vus ; sens et axe ajustés sur les données. → {D: (source, sens, 2·axe)}."""
    tss = tss or [None] * len(trajs)  # seulement les états des transitions d'apprentissage
    etats = [(tr, tr.etats[i]) for tr, ts in zip(trajs, tss, strict=True)
             for i in (range(len(tr.etats)) if ts is None else sorted({u for t in ts for u in (t, t + 1)}))]
    if not etats:
        return {}
    par = {}
    for _, e in etats:
        for o in e:
            par.setdefault(o[0], []).append(o)
    res = {}
    for d, objs in par.items():
        if len(objs) != len(etats) or len({o[1] for o in objs}) < 2:
            continue
        for src in par:
            if src == d:
                continue
            trouve = None
            for sens in ("x", "y", "xy"):
                e0 = etats[0][1]
                sc = {c for o in e0 if o[0] == src for c in cells(o)}
                dc = {c for o in e0 if o[0] == d for c in cells(o)}
                if not sc or not sc <= dc:
                    continue
                axes = sorted({(p[0] if sens != "y" else p[1]) + (q[0] if sens != "y" else q[1]) for p in sc for q in dc - sc})
                for a2 in axes:
                    def explique(tr, e, sens=sens, a2=a2, src=src, d=d):
                        s_c = {c for o in e if o[0] == src for c in cells(o)}
                        return {c for o in e if o[0] == d for c in cells(o)} == s_c | reflet(s_c, sens, a2, tr.taille)
                    if all(explique(tr, e) for tr, e in etats):
                        trouve = (src, sens, a2)
                        break
                if trouve:
                    break
            if trouve:
                res[d] = trouve
                break
    return res


def trouver_reflets(trajs, tss=None):
    """Reflet SANS oracle (ar25 en composantes ou en cases) : les cases de la classe D sont exactement le reflet des cases
    des classes MOBILES (vues se déplacer), moins les cases occupées par d'autres objets, dans tous les états
    d'apprentissage ; D peut avoir une autre couleur que la source. → {D: (sources, sens, 2·axe, atomique)}."""
    tss = tss or [None] * len(trajs)
    paires_etats, mobiles = [], set()
    for tr, ts in zip(trajs, tss, strict=True):
        idx = range(len(tr.actions)) if ts is None else ts
        for t in idx:
            pa, _ = apparier(tr.etats[t], tr.etats[t + 1])
            mobiles |= {tr.etats[t][i][0] for i, j in pa
                        if j is not None and tr.etats[t + 1][j][2:] != tr.etats[t][i][2:]}
        paires_etats += [(tr, tr.etats[i]) for i in sorted({u for t in idx for u in (t, t + 1)})]
    if not mobiles or not paires_etats:
        return {}
    src = frozenset(mobiles)
    classes = {o[0] for _, e in paires_etats for o in e} - src
    res = {}
    for d in sorted(classes):
        if not all(any(o[0] == d for o in e) for _, e in paires_etats):
            continue
        e0 = next(e for _, e in paires_etats)
        sc = {c for o in e0 if o[0] in src for c in cells(o)}
        dc = {c for o in e0 if o[0] == d for c in cells(o)}
        if not sc or not dc or len({tuple(sorted(c for o in e if o[0] == d for c in cells(o))) for _, e in paires_etats}) < 2:
            continue
        atom = all(len(o[1]) == 1 for _, e in paires_etats for o in e if o[0] == d)
        for sens in ("x", "y", "xy"):
            k = 1 if sens == "y" else 0
            axes = sorted({p[k] + q[k] for p in sc for q in dc})
            for a2 in axes:
                def explique(tr, e, sens=sens, a2=a2, d=d):
                    s_c = {c for o in e if o[0] in src for c in cells(o)}
                    autres = {c for o in e if o[0] not in src and o[0] != d for c in cells(o)}
                    return {c for o in e if o[0] == d for c in cells(o)} == reflet(s_c, sens, a2, tr.taille) - autres
                if all(explique(tr, e) for tr, e in paires_etats):
                    res[d] = (src, sens, a2, atom)
                    break
            if d in res:
                break
    return res


def trouver_teleports(th, sources):
    """Téléportation (ls20 niveau 3) : un mobile dont le déplacement observé diffère de sa règle de flèche V, d'un même
    décalage D, chaque fois qu'il arrive sur une case occupée par la classe K. → {K: D} (au moins 1 cas, aucun contre-cas)."""
    vus, contre = {}, set()
    for tr, ts, *_ in sources:
        for t in (range(len(tr.actions)) if ts is None else ts):
            a = tr.actions[t]
            if isinstance(a, tuple):
                continue
            paires, _ = apparier(tr.etats[t], tr.etats[t + 1])
            for i, j in paires:
                o = tr.etats[t][i]
                v = th.moves.get((o[0], a))
                if v is None or j is None:
                    continue
                arrivee = cells(o, *v)
                sous = {q[0] for q in tr.etats[t] if q is not o and cells(q) & arrivee}
                obs = (tr.etats[t + 1][j][2] - o[2], tr.etats[t + 1][j][3] - o[3])
                for k in sous:
                    if obs == v:
                        contre.add(k)
                    elif obs != (0, 0):
                        vus.setdefault(k, set()).add((obs[0] - v[0], obs[1] - v[1]))
    par_classe = {k: next(iter(d)) for k, d in vus.items() if len(d) == 1 and k not in contre}
    return par_classe


def trouver_teleports_cases(th, sources):
    """Téléportation liée à une CASE (pas à une classe : ls20 niveau 3, case de sol ordinaire) : arriver sur la case P
    décale encore de D, à chaque fois (aucun contre-cas). Vaut pour le niveau observé. → {(x, y): D}."""
    vus, contre = {}, set()
    for tr, ts, *_ in sources:
        for t in (range(len(tr.actions)) if ts is None else ts):
            a = tr.actions[t]
            if isinstance(a, tuple):
                continue
            paires, _ = apparier(tr.etats[t], tr.etats[t + 1])
            for i, j in paires:
                o = tr.etats[t][i]
                v = th.moves.get((o[0], a))
                if v is None or j is None:
                    continue
                p = (o[2] + v[0], o[3] + v[1])
                obs = (tr.etats[t + 1][j][2] - o[2], tr.etats[t + 1][j][3] - o[3])
                if obs == v:
                    contre.add(p)
                elif obs != (0, 0):
                    vus.setdefault(p, set()).add((obs[0] - v[0], obs[1] - v[1]))
    return {p: next(iter(d)) for p, d in vus.items() if len(d) == 1 and p not in contre}


def trouver_annulation(sources):
    """Action « annuler » (UNDO) : elle dépile un historique où l'on n'empile que les coups qui ont changé l'état
    (ar25 : 10/10). Retenue si ≥ 2 cas, ≥ 80 % exacts, ET si elle a défait au moins 2 sortes de coups différentes
    (sinon c'est un simple déplacement opposé : « droite » après « gauche », régression sn01, CCM-080-B).
    Ses transitions sortent de l'ASP (règle avec mémoire)."""
    actions = {tr.actions[t] for tr, ts in sources for t in ts if not isinstance(tr.actions[t], tuple)}
    for a in sorted(actions):
        ok = n = 0
        defaits = set()  # quels coups l'action a-t-elle défaits ? (« droite » ne défait que « gauche » : pas une annulation)
        for tr, ts in sources:  # seulement les transitions d'apprentissage ts
            for t in ts:
                if tr.actions[t] == a:
                    n += 1
                    if tr.etats[t + 1] == precedent_pile(tr.etats, tr.actions, t, a):
                        ok += 1
                        prec = [u for u in range(t) if tr.actions[u] != a and tr.etats[u + 1] != tr.etats[u]]
                        if prec and tr.etats[t] != tr.etats[t + 1]:
                            defaits.add(tr.actions[prec[-1]])
        if n >= 2 and ok >= 0.8 * n and len(defaits) >= 2:
            return a
    return None


def precedent_pile(etats, actions, t, annule):
    """État que rendrait « annuler » au coup t (pile des états d'avant chaque coup qui a changé l'état)."""
    pile = []
    for u in range(t):
        if actions[u] == annule:
            if pile:
                pile.pop()
        elif etats[u + 1] != etats[u]:
            pile.append(etats[u])
    return pile[-1] if pile else etats[t]


def but_rationnel(th, gagnants, max_buts=8, limite=5000):
    """Parmi les buts compatibles, le plus simple pour lequel chaque segment gagnant est presque optimal dans le modèle
    (plan ≥ 75 % de la démonstration) : un démonstrateur qui fait un long détour (par un modificateur, par un 2ᵉ objet)
    ne vise pas le but plus simple. None si aucun."""
    from chrysalide.arc3.logique.plan import planifier
    for b in th.buts_compatibles[:max_buts]:
        tb = th.pour_but(b)
        rationnel = True
        for tr, _fin in gagnants:
            actions = sorted({a for _, a in tb.moves}) + (
                [("clic", x, y) for x in range(tr.taille[0]) for y in range(tr.taille[1])] if tb.motif else [])
            plan, _ = planifier(tb, tr.etats[0], tr.taille, actions, limite=limite)
            if plan is None or len(plan) < 0.75 * (len(tr.actions) + 1):  # atteignable bien plus vite : détour inexpliqué
                rationnel = False
                break
        if rationnel:
            return b
    return None


def _preparer(sources):
    if not isinstance(sources, list):
        sources = [(sources, None, None)]
    issues = [(x + (None,) * 4)[:4] for x in sources]
    issues = [(tr, ts, fin, iss or ("niveau" if fin is not None else None)) for tr, ts, fin, iss in issues]
    derives = trouver_derives([tr for tr, *_ in issues], [ts for _, ts, *_ in issues])
    reflets = trouver_reflets([tr for tr, *_ in issues], [ts for _, ts, *_ in issues])
    if derives or reflets:
        issues = [(_SansDerives(tr, set(derives) | set(reflets)), ts, fin, iss) for tr, ts, fin, iss in issues]
    derives = {**derives, **{("reflet", d): v for d, v in reflets.items()}}  # clés tuples : dict(**) les refuse
    sources = [(tr, list(range(len(tr.actions))) if ts is None else list(ts), fin if iss in ("niveau", "gagne") else None)
               for tr, ts, fin, iss in issues]
    annule = trouver_annulation([(tr, ts) for tr, ts, _ in sources])
    if annule is not None:
        sources = [(tr, [t for t in ts if tr.actions[t] != annule], fin) for tr, ts, fin in sources]
    texte, couleurs, traverse = faits([(tr, ts) for tr, ts, _ in sources])
    return issues, sources, texte, couleurs, traverse, (derives, annule)


def faits_anciennes(th):
    """Lois retenues au niveau précédent, en faits ASP `ancienne(...)` (hors hypothèses nommées, qui ne sont pas des lois
    observées) : elles coûtent 0 dans l'objectif."""
    if th is None:
        return ""
    F = [f"ancienne(move({c},{a},v({v[0]},{v[1]})))." for (c, a), v in th.moves.items() if (c, a) not in th.moves_supposes]
    F += [f"ancienne(solide({c}))." for c in th.solides - th.murs_supposes]
    F += [f"ancienne(poussable({c}))." for c in th.poussables]
    F += [f"ancienne(consomme({a},{b}))." for a, b in th.consomme] + [f"ancienne(lie({a},{b}))." for a, b in th.lie]
    F += [f"ancienne(transforme({m},{c},{c2}))." for m, c, c2 in th.transforme]
    F += [f"ancienne(bascule({a},{b}))." for a, b in th.bascule.items()]
    F += [f"ancienne(motif(d({dx},{dy})))." for dx, dy in th.motif]
    F += ["ancienne(fond_solide)."] if th.fond_solide else []
    return "\n" + "\n".join(F)


def continuite(th, ancienne):
    """H_continuite : une loi de déplacement ou de transformation du niveau précédent, sur laquelle les nouvelles données
    sont MUETTES (aucun candidat), est reprise telle quelle (hypothèse nommée, révisable)."""
    if ancienne is None:
        return th
    for k, v in ancienne.moves.items():
        if k not in th.moves:
            th.moves[k] = v
            th.moves_supposes[k] = ancienne.moves_supposes.get(k, "H_continuite")
    th.transforme = th.transforme | ancienne.transforme
    th.consomme, th.lie = th.consomme | ancienne.consomme, th.lie | ancienne.lie
    th.formes = {**ancienne.formes, **th.formes}
    if th.but is None and ancienne.but is not None:
        th.but = ancienne.but
    return th


# familles de lois de la théorie de C (codes du #minimize) et noms de l'ontologie qui y renvoient (CW-206/220)
FAMILLES = {"move": "m", "deplacer": "m", "solide": "s", "mur": "s", "poussable": "p", "pousser": "p", "autonome": "a",
            "poursuite": "a", "consomme": "c", "ramasser": "c", "lie": "l", "fond_solide": "f", "transforme": "tr",
            "saut": "sa", "motif": "mo", "bascule": "b", "clic": "b", "zone": "z", "exclusif": "e", "desel": "ds",
            "cache": "o"}


def faits_poids(ordre=None):
    """Poids des familles de lois dans l'optimisation (CW-220) : sans `ordre`, tous à 1 (comportement inchangé). Avec
    une liste ordonnée d'hypothèses (proposeur ontologique, ou ordre par actions permises de CW-206), la famille de rang r
    (0 = la plus probable) coûte 1 + r, une famille absente de la liste 1 + len(ordre) : les lois proposées en tête
    sont préférées à égalité d'erreurs ; les erreurs restent minimisées en premier (@2)."""
    codes = sorted(set(FAMILLES.values()))
    rang = {}
    for r, nom in enumerate(ordre or []):
        c = FAMILLES.get(nom, nom)
        rang.setdefault(c, r)
    defaut = len(ordre) if ordre else 0
    return "\n" + " ".join(f"poids({c},{1 + rang.get(c, defaut)})." for c in codes) + "\n"


def faits_controle(c):
    """E (CW-458, CHRYS_P1_CONTROLE_FILMS) : objet contrôlé vu aux films = couleur c. Hypothèse PRIORITAIRE, pas vérité :
    c n'est pas autonome, et chaque flèche qui a un déplacement candidat de c dans son sens en reçoit un, dans son sens.
    L'appelant garde la théorie libre si celle-ci rejoue au moins aussi bien."""
    if c is None:
        return ""
    cs = [int(x) for x in (c if isinstance(c, (list, tuple, set)) else [c])]  # plusieurs couleurs : oracle (CW-459)
    return ("\n" + " ".join(f"ctrl_c({x})." for x in cs) + " sens(1,0,-1). sens(2,0,1). sens(3,-1,0). sens(4,1,0).\n"
            ":- ctrl_c(C), autonome(C).\n"
            ":- ctrl_c(C), move(C,A,v(X,Y)), sens(A,SX,SY), X*SX+Y*SY <= 0.\n"
            "bon_c(C,A) :- ctrl_c(C), cand(C,A,v(X,Y)), sens(A,SX,SY), X*SX+Y*SY > 0.\n"
            "ctrl_a(C,A) :- ctrl_c(C), move(C,A,_).\n"
            ":- bon_c(C,A), not ctrl_a(C,A).\n")


def induire(sources, prior_solide=True, limite_s=60, anciennes=None, ordre=None, controle=None):
    """Théorie induite. `sources` = Trajectoire, ou liste de (traj, ts|None, finale|None, issue|None) ; `finale` = action
    qui a fini le segment depuis le dernier état de traj ; issue 'niveau'/'gagne' → but, 'perdu' → mort.
    `anciennes` = théorie du niveau précédent (prior de continuité, CCM-022-C). `ordre` = liste ordonnée de familles de
    lois (noms de l'ontologie, voir FAMILLES) proposée par un proposeur (CW-220) ; None = poids égaux. → (Theorie, infos)"""
    t0 = time.process_time()
    sel_clic, marqueur, glisse = None, (), ()
    if os.environ.get("CHRYS_SELECTION_CLIC", "0") == "1":  # C (ka59 N4) : sélection au clic détectée AVANT l'ASP
        sel_clic, sources, marqueur, glisse = _selection_clic_brute(sources)
    issues, sources, texte, couleurs, traverse, (derives, annule) = _preparer(sources)
    texte += faits_anciennes(anciennes) + faits_poids(ordre) + faits_controle(controle)
    syms, optimal, cout = resoudre_asp(texte, limite_s)
    th = continuite(_completer(depuis_symboles(syms), issues, sources, couleurs, traverse, prior_solide), anciennes)
    th.derives, th.annule = derives, annule
    if sel_clic:
        th.selection_clic, th.marqueur_sel, th.glisse = sel_clic, marqueur, glisse
    if os.environ.get("CHRYS_PREFERE_MOVE") == "1":  # C (CW-451, CCM-091-D) : à exactitude égale, contrôlé > autonome
        th = prefere_move(th, [tr for tr, _ts, _f in sources])
    return th, {"cpu_s": time.process_time() - t0, "n_faits": texte.count("\n") + 1, "optimal": optimal,
                "transitions_inexpliquees": sum(x.startswith("erreur(") for x in syms), "cout": cout}


FLECHE = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}  # sens attendu d'un déplacement par flèche


def prefere_move(th, trajs):
    """C (CW-451) : une classe déclarée AUTONOME (`poursuit`) dont chaque déplacement vu SUIT la flèche jouée (même
    vecteur pour une même flèche, dans son sens, sur ≥ 2 flèches distinctes ; immobile aux autres coups) est essayée comme
    CONTRÔLÉE (`move(c, a, v)`) ; gardée si le rejeu recalé est au moins aussi bon sur toutes les trajectoires. dc22/tr87 :
    la démo gagnante faisait préférer « poursuit » à « move » (CCM-091-D). Un vrai poursuivant (bouge sans flèche, ou
    contre le sens) reste autonome."""
    import dataclasses

    from chrysalide.arc3.logique.theorie import rejeu
    for c in list(th.autonomes):
        vec, ok = {}, True
        for tr in trajs:
            for t, a in enumerate(tr.actions):
                p0 = [(o[2], o[3]) for o in tr.etats[t] if o[0] == c]
                p1 = [(o[2], o[3]) for o in tr.etats[t + 1] if o[0] == c]
                if len(p0) != 1 or len(p1) != 1:
                    continue
                d = (p1[0][0] - p0[0][0], p1[0][1] - p0[0][1])
                if d == (0, 0):
                    continue  # bloqué ou coup sans effet : compatible avec un contrôlé
                if a not in FLECHE or (d[0] * FLECHE[a][0] + d[1] * FLECHE[a][1]) <= 0 or vec.get(a, d) != d:
                    ok = False
                    break
                vec[a] = d
            if not ok:
                break
        if not ok or len(vec) < 2:
            continue
        cand = dataclasses.replace(th, autonomes={k: v for k, v in th.autonomes.items() if k != c},
                                   moves={**th.moves, **{(c, a): v for a, v in vec.items()}})
        # rejeu RECALÉ à chaque pas (libre=False) : compte les transitions bien prédites une à une ; le rejeu strict
        # échoue dès la 1re erreur ailleurs dans la théorie et ne distingue pas les deux explications (dc22 : 3 contre 0)
        if all(rejeu(cand, tr, libre=False)[0] >= rejeu(th, tr, libre=False)[0] for tr in trajs):
            th = cand
    return th


def induire_k(sources, k=10, tolerance=1, prior_solide=True, limite_s=60, ordre=None):
    """Théories concurrentes pour l'exploration par réfutation (demande de B, CCM-054-B) : jusqu'à k théories distinctes,
    aussi cohérentes que la meilleure (même nombre de transitions inexpliquées) et d'au plus `tolerance` règle(s) de plus.
    Triées de la plus simple à la moins simple. Renvoie [(Theorie, coût)] ; coût = [inexpliquées, règles]."""
    issues, sources, texte, couleurs, traverse, (derives, annule) = _preparer(sources)
    texte += faits_poids(ordre)
    _, _, cout = resoudre_asp(texte, limite_s)
    if not cout:
        return []
    res = []
    for syms, c in enumerer_asp(texte, cout, k, tolerance, limite_s):
        th = _completer(depuis_symboles(syms), issues, sources, couleurs, traverse, prior_solide)
        th.derives, th.annule = dict(derives), annule
        res.append((th, c))
    return res


OPPOSEES = {1: 2, 2: 1, 3: 4, 4: 3}


def formes_bascule(th, sources):
    """C (CCM-021-D, ft09 N3) : formes des objets vus BASCULER sous un clic (même case, même forme, classe → bascule) ;
    `theorie.clic` ne fera basculer que celles-là (un morceau d'interface de même couleur, cliqué sans effet, n'en est
    pas). Vide si aucune bascule n'a été vue (pas de restriction)."""
    vues = set()
    for tr, *_ in sources:
        for t, a in enumerate(tr.actions):
            if not isinstance(a, tuple):
                continue
            apres = {(o[1], o[2], o[3]): o[0] for o in tr.etats[t + 1]}
            vues |= {o[1] for o in tr.etats[t] if th.bascule.get(o[0]) is not None
                     and apres.get((o[1], o[2], o[3])) == th.bascule[o[0]]}
    return frozenset(vues)


def tuiles_courantes(g, t):
    """Tuiles de la grille `t` = (couleurs, y0, x0, py, px, h, l) (faits.grille_tuiles) dans l'image de cases `g` : blocs
    h × l unis d'une couleur de la grille, sur le réseau → {(i, j): (couleur, cases)} dans le plus grand rectangle plein."""
    import numpy as np
    g = np.asarray(g)
    couleurs, y0, x0, py, px, h, w = t
    tu = {}
    for y in range(y0, g.shape[0] - h + 1, py):
        for x in range(x0, g.shape[1] - w + 1, px):
            b = g[y:y + h, x:x + w]
            if (b == b[0, 0]).all() and int(b[0, 0]) in couleurs:
                tu[((y - y0) // py, (x - x0) // px)] = (int(b[0, 0]), tuple((x + j, y + i) for i in range(h) for j in range(w)))
    if not tu:
        return {}
    i0, j0 = min(i for i, _ in tu), min(j for _, j in tu)
    n, m = max(i for i, _ in tu) - i0 + 1, max(j for _, j in tu) - j0 + 1
    if len(tu) != n * m:  # réseau troué : pas une grille de tuiles simple
        return {}
    return {(i - i0, j - j0): v for (i, j), v in tu.items()}


def buts_copie(sources):
    """But `copie` (C, CCM-140-C ; détecteur de D, `faits.modele_reduit`) : la grille de tuiles cliquables doit reproduire la
    miniature STATIQUE affichée ailleurs. → [("copie", ((couleur, cases), …), None)] (même forme que `marques` : chaque
    case doit montrer sa couleur), ou []."""
    from chrysalide.arc3.logique.faits import grille_tuiles, modele_reduit
    tr = sources[0][0]
    if not hasattr(tr, "cases"):  # trajectoire simplifiée (tests de prédiction) : pas d'images en cases
        return []
    t = grille_tuiles(tr.cases, tr.exclues, tr.actions)
    if t is None:
        return []
    tu = tuiles_courantes(tr.cases[-1], t)
    if len(tu) < 2:
        return []
    xs = [x for _, cs in tu.values() for x, _ in cs]
    ys = [y for _, cs in tu.values() for _, y in cs]
    r = modele_reduit(tr.cases, {k: c for k, (c, _) in tu.items()}, exclure=(min(xs), min(ys), max(xs) + 1, max(ys) + 1),
                      palette=t[0], min_couleurs=1)
    if not r:
        return []
    groupes = {}
    for (i, j), (_, cs) in tu.items():
        groupes.setdefault(int(r[0]["grille"][i][j]), []).extend(cs)
    return [("copie", tuple((k, tuple(sorted(v))) for k, v in sorted(groupes.items())), None)]


def centres_cadres(etat):
    """C (re86 N5, CCM-275-C) : cadres = anneaux 3 × 3 (8 cases) d'une classe qui en a au moins 2 ; un cadre COUPÉ par
    une pièce (fragments de cette classe dont toutes les cases tombent sur l'anneau d'un même centre, au moins 2
    fragments) compte aussi. → {centre : couleur de l'objet d'une case au centre, ou -1 si caché}."""
    anneau = frozenset((x, y) for x in range(3) for y in range(3)) - {(1, 1)}
    classes = [c for c in {o[0] for o in etat} if sum(o[1] == anneau for o in etat if o[0] == c) >= 2]
    if len(classes) != 1:
        return {}
    k = classes[0]
    centres = {(o[2] + 1, o[3] + 1) for o in etat if o[0] == k and o[1] == anneau}
    frags = [cells(o) for o in etat if o[0] == k and o[1] != anneau and len(o[1]) < 8]
    proches = {}
    for i, f in enumerate(frags):
        for cx, cy in {(x + dx, y + dy) for x, y in f for dx in (-1, 0, 1) for dy in (-1, 0, 1)}:
            if all(max(abs(x - cx), abs(y - cy)) == 1 for x, y in f):
                proches.setdefault((cx, cy), set()).add(i)
    centres |= {c for c, fs in proches.items() if len(fs) >= 2}
    point = {(o[2], o[3]): o[0] for o in etat if len(o[1]) == 1 and o[0] < 512}
    return {c: point.get(c, -1) for c in sorted(centres)}


def ajouter_but_marques(th, sources, exclues=()):
    """But `marques` (re86) : objets d'une case de la 1re image, par couleur (hors marqueurs et classes exclues), à
    couvrir par des pièces ; proposé seulement quand une sélection (porteur ou cachée) a été trouvée."""
    from chrysalide.arc3.logique.faits import MARQUEUR
    groupes = {}
    for o in sources[0][0].etats[0]:
        if len(o[1]) == 1 and o[0] < MARQUEUR and o[0] not in exclues:
            groupes.setdefault(o[0], []).append((o[2], o[3]))
    if os.environ.get("CHRYS_PAIRES_COULEUR") == "1":  # CCM-275-C : marques = centres des cadres 3 × 3, coupés compris
        cadres = centres_cadres(sources[0][0].etats[0])
        if cadres:
            groupes = {}
            for (x, y), k in cadres.items():
                groupes.setdefault(k, []).append((x, y))
    if groupes:
        coul = "couleur" if os.environ.get("CHRYS_PAIRES_COULEUR") == "1" else None  # CCM-059-E : pièce de la couleur
        th.buts_motifs = [*th.buts_motifs, ("marques", tuple((k, tuple(sorted(v))) for k, v in sorted(groupes.items())), coul)]


def trouver_debord(th, sources):
    """Classes mobiles vues sortir EN PARTIE de la grille : un objet poussé par sa loi au-delà du bord réapparaît
    tronqué (exactement ses cases restées dans la grille)."""
    from chrysalide.arc3.logique.theorie import cells
    res = set()
    for tr, *_ in sources:
        w, h = tr.taille
        for t, a in enumerate(tr.actions):
            for o in tr.etats[t]:
                v = th.moves.get((o[0], a))
                if not v or o[0] in res:
                    continue
                cs = cells(o, *v)
                dedans = {(x, y) for x, y in cs if 0 <= x < w and 0 <= y < h}
                if dedans and dedans != cs and any(o2[0] == o[0] and cells(o2) == dedans for o2 in tr.etats[t + 1]):
                    res.add(o[0])
    return frozenset(res)


def trouver_enroulement(th, sources):
    """C (tr87 ; CHRYS_ENROULE=1) : une classe qui se déplace d'un pas fixe le long d'un axe, dans un intervalle
    [min, max] de positions observées, et qui, au-delà, revient à l'AUTRE bout (curseur cyclique). On lit sur les
    transitions, pour chaque (classe, action) : le déplacement le plus fréquent (la loi) et les sauts min ↔ max. Si chaque
    saut va d'un bout à l'autre dans le sens de la loi : th.enroule[c] = (axe, min, max), la loi est corrigée (l'ASP a pu
    choisir le saut) et les téléportations par case de cette classe sont retirées."""
    from collections import Counter
    obs = {}
    for tr, *_ in sources:
        for t, a in enumerate(tr.actions):
            if isinstance(a, tuple):
                continue
            paires, _ = apparier(tr.etats[t], tr.etats[t + 1])
            for i, j in paires:
                o0 = tr.etats[t][i]
                if j is None:
                    continue
                o1 = tr.etats[t + 1][j]
                d = (o1[2] - o0[2], o1[3] - o0[3])
                if d != (0, 0) and o1[0] == o0[0]:
                    obs.setdefault((o0[0], a), []).append(((o0[2], o0[3]), d))
    for c in sorted({c for c, _ in obs}):
        lois, sauts = {}, []
        for (cc, a), l in obs.items():
            if cc != c:
                continue
            v = Counter(d for _, d in l).most_common(1)[0][0]
            lois[a] = v
            sauts += [(p, d, v) for p, d in l if d != v]
        if not sauts or any((v[0] != 0) == (v[1] != 0) for v in lois.values()):
            continue
        axes = {0 if v[0] else 1 for v in lois.values()}
        if len(axes) != 1:
            continue
        axe = axes.pop()
        pos = [p[axe] for (cc, _), l in obs.items() if cc == c for p, _ in l] + \
              [p[axe] + d[axe] for (cc, _), l in obs.items() if cc == c for p, d in l]
        mini, maxi = min(pos), max(pos)
        bons = all(d[1 - axe] == 0 and ((v[axe] > 0 and p[axe] == maxi and p[axe] + d[axe] == mini)
                                        or (v[axe] < 0 and p[axe] == mini and p[axe] + d[axe] == maxi)) for p, d, v in sauts)
        if bons:
            th.enroule[c] = (axe, mini, maxi)
            for a, v in lois.items():
                th.moves[(c, a)] = v
                th.moves_supposes.pop((c, a), None)
            th.teleports_cases = {}


def trouver_selection(th, sources):
    """C (re86 N2 ; CHRYS_SELECTION=1) : sélection CACHÉE. Sous les actions autres que le sélecteur, UNE seule classe
    bouge (toujours du même pas pour une action donnée) ; la classe qui bouge ne change qu'après le sélecteur (action
    sous laquelle rien ne bouge), dans un ordre cyclique. → th.selection = (sélecteur, classes, index initial) ; lois de
    déplacement de chaque classe sélectionnable posées depuis les observations, explications concurrentes retirées."""
    obs = []  # (action, classe qui bouge | None, vecteur)
    brut = []  # (action, {(classe, dx, dy)})
    for tr, *_ in sources:
        for t, a in enumerate(tr.actions):
            if isinstance(a, tuple):
                return
            e0, e1 = tr.etats[t], tr.etats[t + 1]
            paires, _ = apparier(e0, e1)
            brut.append((a, {(e0[i][0], e1[j][2] - e0[i][2], e1[j][3] - e0[i][3]) for i, j in paires
                             if j is not None and e1[j][0] == e0[i][0] and (e1[j][2], e1[j][3]) != (e0[i][2], e0[i][3])}))
    # C (ar25 N4, CHRYS_FORMES_SEL) : SUIVEURS = classes qui bougent avec au moins DEUX autres classes différentes
    # (marques de la pièce choisie, quelle qu'elle soit) ; elles n'empêchent pas la sélection et reçoivent leurs propres
    # lois (pas constant par action)
    avec = {}
    for _, mv in brut:
        cs = {c for c, _, _ in mv}
        for c in cs:
            avec.setdefault(c, set()).update(cs - {c})
    suiveurs = ({c for c, v in avec.items() if len(v) >= 2} if os.environ.get("CHRYS_FORMES_SEL", "1") == "1" else set())
    lois_suiveurs = {}
    for a, mv in brut:
        for c, dx, dy in mv:
            if c in suiveurs:
                lois_suiveurs.setdefault((c, a), set()).add((dx, dy))
        mv = {m for m in mv if m[0] not in suiveurs}
        if len({c for c, _, _ in mv}) > 1:
            return
        obs.append((a, next(iter(mv)) if mv else None))
    bougeurs = [m[0] for _, m in obs if m]
    if len(set(bougeurs)) < 2:
        return
    for sel in sorted({a for a, m in obs if not m}):
        ordre, courant, lois, ok = [], None, {}, True
        for a, m in obs:
            if a == sel:
                if m:
                    ok = False
                    break
                courant = None  # la sélection a changé : la prochaine classe qui bouge est la suivante
                continue
            if m is None:
                continue
            c, dx, dy = m
            if lois.setdefault((c, a), (dx, dy)) != (dx, dy):
                ok = False
                break
            if courant is None:
                if c not in ordre:
                    ordre.append(c)
                courant = c
            elif c != courant:
                ok = False  # deux classes différentes sans sélecteur entre elles
                break
        if ok and len(ordre) >= 2:
            # index initial : les sélecteurs joués AVANT le 1er déplacement l'ont déjà avancé (ar25 N4 : SPACE au coup 0)
            avant = 0
            for a, m in obs:
                if m is not None:
                    break
                avant += a == sel
            th.selection = (sel, tuple(ordre), (-avant) % len(ordre) if os.environ.get("CHRYS_FORMES_SEL", "1") == "1" else 0)
            for (c, a), v in lois.items():
                th.moves[(c, a)] = v
                th.moves_supposes.pop((c, a), None)
            for c in ordre:  # H_oppose pour les flèches jamais vues de chaque classe sélectionnable
                for a, b in OPPOSEES.items():
                    if (c, a) in lois and (c, b) not in th.moves:
                        v = lois[(c, a)]
                        th.moves[(c, b)], th.moves_supposes[(c, b)] = (-v[0], -v[1]), "H_oppose"
            for (c, a), vs in lois_suiveurs.items():  # suiveurs : un seul pas par action, sinon pas de loi
                if len(vs) == 1:
                    th.moves[(c, a)] = next(iter(vs))
                    th.moves_supposes.pop((c, a), None)
            th.autonomes = {c: v for c, v in th.autonomes.items() if c not in ordre}
            th.poussables = frozenset(th.poussables - set(ordre))
            ajouter_but_marques(th, sources, exclues=set(ordre))
            return


def trouver_retour(th, sources):
    """C (g50t N1 : SPACE ramène le joueur au départ) : classe mobile, d'un seul objet, qui sous une action (non clic)
    se retrouve TOUJOURS à sa position de la 1re image de la trajectoire (au moins 2 fois, dont 1 où elle a bougé). La loi
    `move` de cette action (un pas inventé par l'induction) est retirée ; th.retour la remplace."""
    tr = sources[0][0]
    mobiles = {c for c, _ in th.moves}
    retour = []
    for c in sorted(mobiles):
        d0 = [o for o in tr.etats[0] if o[0] == c]
        if len(d0) != 1:
            continue
        x0, y0 = d0[0][2], d0[0][3]
        for a in sorted({a for a in tr.actions if not isinstance(a, tuple)}):
            vus, bouge, ok = 0, 0, True
            for t, b in enumerate(tr.actions):
                if b != a:
                    continue
                o0 = [o for o in tr.etats[t] if o[0] == c]
                o1 = [o for o in tr.etats[t + 1] if o[0] == c]
                if len(o0) != 1 or len(o1) != 1:
                    continue
                vus += 1
                bouge += (o0[0][2], o0[0][3]) != (x0, y0)
                if (o1[0][2], o1[0][3]) != (x0, y0):
                    ok = False
                    break
            if ok and vus >= 2 and bouge >= 1:
                retour.append((c, a, x0, y0))
                th.moves.pop((c, a), None)
                th.moves_supposes.pop((c, a), None)
    th.retour = tuple(_au_depart_courant(retour, sources))


def _au_depart_courant(lois, sources):
    """Lois « au départ » (retour, fantôme : …, x0, y0 en fin de tuple, classe en tête) : si les trajectoires portent un
    niveau (`tr.niveau`) et que la dernière est d'un AUTRE niveau que la première, le départ est celui de la 1re image du
    niveau courant (g50t N2, CCM-219-C). Sans niveau marqué : inchangé."""
    t0, tn = sources[0][0], sources[-1][0]
    n0, nn = getattr(t0, "niveau", None), getattr(tn, "niveau", None)
    if n0 is None or nn is None or n0 == nn:
        return list(lois)
    out = []
    for loi in lois:
        d = [o for o in tn.etats[0] if o[0] == loi[0]]
        out.append((*loi[:-2], d[0][2], d[0][3]) if len(d) == 1 else loi)
    return out


def _meme_niveau(sources):
    """Trajectoires du niveau courant (celui de la dernière), si les niveaux sont marqués ; sinon toutes."""
    nn = getattr(sources[-1][0], "niveau", None)
    if nn is None:
        return sources
    return [s for s in sources if getattr(s[0], "niveau", None) == nn]


def trouver_fantome(th, sources):
    """C (g50t N1, boucle temporelle) : après une loi `retour(c, a)`, une classe g ≠ c, ABSENTE de la 1re image, apparaît
    avec la forme du mobile c après une action a : c'est un fantôme qui rejoue le trajet. th.fantome = (c, a, g, x0, y0) ;
    les lois propres de g (pas inventés) sont retirées, ses positions viennent du chemin enregistré."""
    tr = sources[0][0]
    for c, a, x0, y0 in th.retour:
        formes = {o[1] for e in tr.etats for o in e if o[0] == c}
        apres = [t for t, b in enumerate(tr.actions) if b == a]
        if not apres:
            continue
        cands = {o[0] for e in tr.etats[apres[0] + 1:] for o in e if o[1] in formes and o[0] != c}
        cands -= {o[0] for o in tr.etats[0] if o[1] in formes}  # la même couleur peut servir ailleurs (pastilles)
        if len(cands) == 1:
            g = cands.pop()
            th.fantome = _au_depart_courant([(c, a, g, x0, y0)], sources)[0]
            for k in [k for k in th.moves if k[0] == g]:
                th.moves.pop(k)
                th.moves_supposes.pop(k, None)
            th.autonomes = {k: v for k, v in th.autonomes.items() if k != g and v != g}
            return


def trouver_tenue(th, sources):
    """C (g50t : dalle → porte) : couple (porte p, dalle d) tel que, sur TOUTE la trajectoire, des objets de classe p sont
    présents exactement quand aucun mobile n'occupe une case de d, avec les deux sens vus (ouverture ET fermeture) ;
    sinon on ne peut départager `lie` (irréversible) de la porte tenue. th.tenue reçoit les couples ; la loi `lie` de p,
    s'il y en a une, est retirée (la porte revient)."""
    tr = sources[0][0]
    mob = {c for c, _ in th.moves} | set(th.poussables) | ({th.fantome[2]} if th.fantome else set())
    presences = {c: [any(o[0] == c for o in e) for e in tr.etats] for c in {o[0] for e in tr.etats for o in e}}
    portes = [c for c, v in presences.items() if any(v) and not all(v) and c not in mob]
    fixes = {}  # dalle = classe immobile (mêmes cases à chaque image où elle est vue ; un mobile posé dessus la cache)
    for c in presences:
        vus = {frozenset(z for o in e if o[0] == c for z in cells(o)) for e in tr.etats if any(o[0] == c for o in e)}
        if c not in mob and len(vus) == 1:
            fixes[c] = next(iter(vus))
    dalles = list(fixes)  # une dalle cachée sous le mobile paraît « absente » : elle peut figurer aussi parmi les portes
    occupe = {d: [bool({z for o in e if o[0] in mob for z in cells(o)} & fixes[d]) for e in tr.etats] for d in dalles}
    tenue = []
    for p in portes:
        for d in dalles:
            if d == p:
                continue
            if all(presences[p][t] == (not occupe[d][t]) for t in range(len(tr.etats))) and any(occupe[d]) \
                    and any(not v for v in occupe[d]) and any(presences[p][t] and not presences[p][t + 1] for t in range(len(tr.actions))) \
                    and any(not presences[p][t] and presences[p][t + 1] for t in range(len(tr.actions))):
                tenue.append((p, d))
    th.tenue = tuple(tenue)
    th.lie = frozenset(x for x in th.lie if x[0] not in {p for p, _ in tenue})
    # g50t (CCM-021-G) : la porte n'est qu'une PARTIE d'un objet (porte + fil + dalle de même couleur). Cases D de la
    # classe p perdues (toujours les mêmes) exactement aux images où un mobile occupe un ensemble fixe S de cases.
    # Cherchée dans CHAQUE trajectoire (la porte peut n'être vue que dans des coups-expériences, CCM-021-G), puis gardée
    # seulement si aucune autre trajectoire ne la contredit (classe p : fermée, ouverte ou absente, selon la dalle).
    sans = {p for p, _ in tenue}
    vues = {}
    courant = _meme_niveau(sources)  # cases absolues : seulement le niveau courant (g50t N2, CCM-219-C)
    for tr_k, *_ in courant:
        for v in _cases_tenues(tr_k, mob, sans):
            vues.setdefault(v[0], v)
    th.tenue_cases = tuple((p, base - ouv, ouv - base, s_cases) for p, base, ouv, s_cases in vues.values()
                           if all(_cases_coherentes(tr_k, mob, p, base, ouv, s_cases) for tr_k, *_ in courant))
    autres = [x for x in sources if x not in courant]
    if autres and os.environ.get("CHRYS_PORTE_RELATIVE", "0") == "1":  # C (CW-349.2, CW-350) : lois vues ailleurs
        th.tenue_cases += _portes_transferees(th, autres, courant, mob, sans)
        th.dalles_proposees = _dalles_proposees(autres, courant, mob, sans)
    # PORTE = cases retirées à l'ouverture qui deviennent les cases AJOUTÉES d'une autre classe (le sol) : fermée, elles
    # bloquent (g50t : sans cela, `fond_solide` laissait traverser la porte, plan faux dans le vrai jeu)
    # (cases de la dalle exclues : le mobile doit pouvoir y monter ; le fil et la dalle de même classe ne bloquent pas)
    def boite(cs):  # la dalle entière (sa boîte) : une case au milieu de S, cachée sous le mobile, n'est pas une porte
        return {(x, y) for x in range(min(x for x, _ in cs), max(x for x, _ in cs) + 1)
                for y in range(min(y for _, y in cs), max(y for _, y in cs) + 1)}
    th.portes_cases = tuple((p, frozenset((r & a) - boite(s_p))) for p, r, _, s_p in th.tenue_cases
                            for q, _, a, _ in th.tenue_cases if q != p and (r & a) - boite(s_p))


def trouver_motif_formes(th, sources):
    """C (ft09 N5, CCM-039-E) : le voisinage basculé par un clic dépend de la FORME de l'objet cliqué (tuile simple :
    elle seule ; tuile « croix » : elle et ses 4 voisines). Pour chaque clic observé : objet cliqué o, objets dont la classe
    change (même forme, même place) ; (2×centre(j) − 2×centre(o), forme de j), réunis par forme cliquée. Gardé seulement si
    le rejeu des sources s'améliore (sinon `motif` reste seul)."""
    from chrysalide.arc3.logique.theorie import _centre2
    par_forme = {}
    for tr, *_ in sources:
        for t, a in enumerate(tr.actions):
            if not isinstance(a, tuple):
                continue
            _, x, y = a  # tr.actions : déjà en cases
            e0, e1 = tr.etats[t], tr.etats[t + 1]
            cl = [o for o in e0 if (x, y) in cells(o)]
            if not cl:
                continue
            apres = {(o[1], o[2], o[3]): o[0] for o in e1}
            bas = [j for j in e0 if apres.get((j[1], j[2], j[3]), j[0]) != j[0]]
            if not bas:
                continue
            c2 = _centre2(cl[0])
            par_forme.setdefault(cl[0][1], set()).update(
                (_centre2(j)[0] - c2[0], _centre2(j)[1] - c2[1], j[1]) for j in bas)  # forme basculée retenue
    if len({frozenset(v) for v in par_forme.values()}) < 2:
        return  # un seul voisinage : `motif` suffit
    def score(mf):
        th.motif_formes = mf
        return sum(rejeu(th, tr, 0, max(ts) + 1 if ts else len(tr.actions), libre=False)[0] for tr, ts, _ in sources)
    sans = score(())
    avec_mf = tuple(sorted(((f, frozenset(v)) for f, v in par_forme.items()), key=lambda fv: sorted(fv[0])))
    th.motif_formes = avec_mf if score(avec_mf) > sans else ()


def trouver_clic_configs(th, sources):
    """C (dc22 N3) : un clic sur un bouton (objet sous le clic, inchangé) remplace un ensemble d'objets par un autre, et
    l'inverse au clic suivant (pont, pièces). Si le changement n'est qu'un ÉCHANGE de place d'objets d'une case entre deux
    cases P et Q (plots), la règle est générale : tout objet d'une case en P ou en Q. Gardé si le rejeu s'améliore."""
    regles = []
    for tr, *_ in sources:
        for t, a in enumerate(tr.actions):
            if not isinstance(a, tuple):
                continue
            _, x, y = a
            e0, e1 = set(tr.etats[t]), set(tr.etats[t + 1])
            cl = sorted((o for o in e0 if (x, y) in cells(o)), key=cle_objet)
            av, ap = frozenset(e0 - e1), frozenset(e1 - e0)
            if not cl or cl[0] not in e1 or (not av and not ap):
                continue
            pos_av, pos_ap = {(o[2], o[3]) for o in av}, {(o[2], o[3]) for o in ap}
            if (len(av) == len(ap) == 2 and all(len(o[1]) == 1 for o in av | ap) and pos_av == pos_ap
                    and len(pos_av) == 2 and {o[0] for o in av} == {o[0] for o in ap}):
                p, q = sorted(pos_av)
                r = (cl[0], "echange", p, q)
            else:
                r = (cl[0], av, ap)
            if r not in regles and (r[1] == "echange" or (r[0], r[2], r[1]) not in regles):
                regles.append(r)
    if not regles:
        return
    def score(cc):
        th.clic_configs = cc
        return sum(rejeu(th, tr, 0, max(ts) + 1 if ts else len(tr.actions), libre=False)[0] for tr, ts, _ in sources)
    sans = score(())
    avec = score(tuple(regles))
    th.clic_configs = tuple(regles) if avec > sans else ()
    if th.clic_configs:  # les boutons expliquent les clics : lois de clic de l'ASP retirées si le rejeu ne baisse pas
        garde = (th.motif, dict(th.bascule), th.exclusif, dict(th.desel))
        th.motif, th.bascule, th.exclusif, th.desel = frozenset(), {}, False, {}
        if score(th.clic_configs) < avec:
            th.motif, th.bascule, th.exclusif, th.desel = garde


def lire_jauge(grilles, n_coups):
    """Réserve de coups lue par la loi de jauge de C (barre, rythme, marge prudente de deux cases), sur les images brutes
    d'un niveau et le nombre de coups joués → coups ou None. Pour les bancs de vérité de F (CCM-018-F)."""
    from types import SimpleNamespace
    th = Theorie()
    trouver_jauge(th, [(SimpleNamespace(grilles=list(grilles), actions=[None] * n_coups), None, None)])
    return th.jauge[0] if th.jauge else None


def _famille(c):
    """Classe de base : un jumeau séparé par COMPORTEMENT / IMMOBILE (512 + c + 16·k) revient à sa couleur c."""
    return (c - 512) % 16 if 512 <= c < 1024 else c


def _selection_clic_brute(sources):
    """C (ka59 N4, CCM-052-E) : AVANT l'ASP, sur les états bruts. Une famille de classe (c et ses jumeaux) a ≥ 2 objets
    de même forme ; à chaque flèche un seul bouge ; l'objet qui bouge ne change qu'après un CLIC sur lui (vu au moins une
    fois). Alors, à chaque instant, le sélectionné prend la classe c et les autres FIGE + c : l'ASP apprend les pas du
    seul sélectionné. → ((c, x0, y0) ou None, sources réétiquetées)."""
    import copy

    from chrysalide.arc3.logique.theorie import FIGE
    norm = [(x if isinstance(x, tuple) else (x, None, None)) for x in sources]
    fams = set()
    for tr, *_ in norm:
        compte = {}
        for o in tr.etats[0]:
            compte.setdefault((_famille(o[0]), o[1]), []).append(o)
        fams |= {f for (f, _), os_ in compte.items() if len(os_) >= 2 and f < 512}
    for c in sorted(fams):
        ok, change, depart, suivis, pousses = True, False, None, [], []
        for tr, *_ in norm:
            sel, clic_vu, positions = None, False, []
            for t, a in enumerate(tr.actions):
                e0, e1 = tr.etats[t], tr.etats[t + 1]
                positions.append(sel)
                if isinstance(a, tuple):
                    cl = [o for o in e0 if _famille(o[0]) == c and _sous_clic(o, a[1], a[2])]
                    if cl:
                        sel, clic_vu = (cl[0][2], cl[0][3]), True
                    continue
                paires, _ = apparier([(_famille(o[0]), *o[1:]) for o in e0], [(_famille(o[0]), *o[1:]) for o in e1])
                mv = [(e0[i], e1[j]) for i, j in paires if j is not None and _famille(e0[i][0]) == c
                      and (e0[i][2], e0[i][3]) != (e1[j][2], e1[j][3])]
                if len(mv) > 1:
                    ok = False
                    break
                if not mv:
                    continue
                avant, apres = mv[0]
                if sel is None:
                    sel = (avant[2], avant[3])
                    positions[-1] = sel
                    if not clic_vu and depart is None:
                        depart = sel
                if (avant[2], avant[3]) != sel:
                    s0 = [o for o in e0 if _famille(o[0]) == c and (o[2], o[3]) == sel]
                    if s0 and _pousse(s0[0], avant, apres):  # CCM-041-G : le sélectionné a POUSSÉ un autre objet
                        pousses.append((id(tr), t, avant, apres, e0))
                        continue
                    ok = False
                    break
                change = change or clic_vu
                sel = (apres[2], apres[3])
            positions.append(sel)
            suivis.append(positions)
            if not ok:
                break
        if not (ok and change):
            continue
        out = []
        for (tr, *reste), positions in zip(norm, suivis, strict=True):
            t2 = copy.copy(tr)
            etats = []
            for t, e in enumerate(tr.etats):
                p = positions[t] if t < len(positions) else None
                if p is None and depart is not None and any(_famille(o[0]) == c and (o[2], o[3]) == depart for o in e):
                    p = depart  # avant tout clic : le piloté de départ (vu dans une autre trajectoire), pas le futur cliqué
                if p is None:  # sélection encore inconnue : le 1er sélectionné connu plus tard
                    p = next((q for q in positions[t:] if q is not None), None)
                etats.append(tuple(sorted(((c if (o[2], o[3]) == p else FIGE + c), *o[1:]) if _famille(o[0]) == c else o
                                          for o in e)))
            t2.etats = etats
            out.append((t2, *reste))
        if depart is None:
            depart = next((p for pos in suivis for p in pos if p is not None), None)
        out, marqueur = _marqueur_sel(c, out)
        if pousses:  # les coups de poussée sortent de l'ASP (trajectoires coupées) : la glissade est apprise à part
            coupes = {}
            for k, t, *_ in pousses:
                coupes.setdefault(k, set()).add(t)
            out = [seg for (tr, *reste), (tr0, *_) in zip(out, norm, strict=True)
                   for seg in _couper(tr, coupes.get(id(tr0), set()), reste)]
        return ((c, *depart) if depart else None), out, marqueur, _glisse(pousses)
    return None, sources, (), ()


def trouver_glisse(th, sources):
    """C (ka59 N4, CCM-041-G) : sous selection_clic, une pièce de la famille c qui, sous une flèche, se déplace dans le
    sens du pas de c de PLUS d'un pas a été poussée et a glissé → th.glisse = (distance max, classes traversées). Sources
    à part de l'ASP (coups-expériences de poussée) : les poussées y cassent la sélection, la perception fusionnant les
    pièces qui se touchent."""
    if not th.selection_clic:
        return
    c = th.selection_clic[0]
    ev = []
    for tr, *_ in sources:
        for t, a in enumerate(tr.actions):
            d = th.moves.get((c, a))
            if isinstance(a, tuple) or not d:
                continue
            e0, e1 = tr.etats[t], tr.etats[t + 1]
            for o in e0:  # pièce de c OU autre objet (bloc c11, CCM-042-G) qui glisse de plus d'un pas, même forme
                if len(o[1]) < 4 or o[0] >= 1024:
                    continue
                fo = _famille(o[0]) % 16
                if any(_famille(r[0]) % 16 == fo and r[1] == o[1] and (r[2], r[3]) == (o[2], o[3]) for r in e1):
                    continue  # resté en place
                for q in e1:
                    if any(_famille(r[0]) % 16 == fo and r[1] == q[1] and (r[2], r[3]) == (q[2] - d[0], q[3] - d[1])
                           for r in e0):
                        continue  # un objet pareil a juste fait un pas normal jusque-là
                    if _famille(q[0]) % 16 == fo and q[1] == o[1] and q not in e0:
                        dx, dy = q[2] - o[2], q[3] - o[3]
                        k = dx // d[0] if d[0] else dy // d[1] if d[1] else 0
                        if k >= 2 and (dx, dy) == (d[0] * k, d[1] * k):
                            ev.append((None, t, o, q, e0))
    if ev:
        th.glisse = _glisse(ev)


def _pousse(sel, avant, apres):
    """Le sélectionné `sel` touche `avant` du côté d'où il vient, et `avant` s'est déplacé en s'éloignant de lui."""
    dx, dy = apres[2] - avant[2], apres[3] - avant[3]
    if (dx == 0) == (dy == 0):
        return False
    sx, sy = (1 if dx > 0 else -1 if dx < 0 else 0), (1 if dy > 0 else -1 if dy < 0 else 0)
    return bool({(x + sx, y + sy) for x, y in cells(sel)} & cells(avant))


def _couper(tr, ts, reste):
    """Segments de tr sans les transitions ts (attributs-listes coupés à la bonne longueur)."""
    import copy
    if not ts:
        return [(tr, *reste)]
    n, segs, debut = len(tr.actions), [], 0
    for t in sorted(ts) + [n]:
        if t > debut:
            seg = copy.copy(tr)
            for nom, v in vars(tr).items():
                if isinstance(v, list) and len(v) == n + 1:
                    setattr(seg, nom, v[debut:t + 1])
                elif isinstance(v, list) and len(v) == n:
                    setattr(seg, nom, v[debut:t])
            segs.append((seg, *reste))
        debut = t + 1
    return segs


def _glisse(pousses):
    """Glissade de l'objet poussé (ka59, CCM-041-G) : (pas maximal en nombre de pas, classes traversées). Le pas = le plus
    petit déplacement observé du sélectionné n'est pas connu ici : on rend les déplacements bruts, (dx, dy) en cases."""
    if not pousses:
        return ()
    longueurs, traverse = [], set()
    for _k, _t, avant, apres, e0 in pousses:
        dx, dy = apres[2] - avant[2], apres[3] - avant[3]
        longueurs.append(abs(dx) + abs(dy))
        sx, sy = (1 if dx > 0 else -1 if dx < 0 else 0), (1 if dy > 0 else -1 if dy < 0 else 0)
        occ = {}
        for o in e0:
            if o is not avant and o[0] < 1024:
                for z in cells(o):
                    occ.setdefault(z, set()).add(o[0])
        for k in range(1, abs(dx) + abs(dy) + 1):
            for x, y in cells(avant):
                traverse |= occ.get((x + sx * k, y + sy * k), set())
    poussees = frozenset(avant[0] for _k, _t, avant, _a, _e in pousses)
    # CCM-299-C : distance de base = la longueur la plus fréquente (ka59 : 15) ; au-delà, la glissade se PROLONGE tant que
    # l'objet chevauche une classe « prolongeante » (ka59 : la barrière c15 ; bloc 50 → 29 = 21 cases, puis 29 → 14 = 15).
    # Classes prolongeantes = celles chevauchées à chaque pas au-delà de la base, et plus à l'arrivée.
    from collections import Counter
    from math import gcd
    base = Counter(longueurs).most_common(1)[0][0]
    pas = 0
    for lg in longueurs:
        pas = gcd(pas, lg)
    prolonge = None
    for (_k, _t, avant, apres, e0), lg in zip(pousses, longueurs, strict=True):
        if lg <= base or not pas:
            continue
        dx, dy = apres[2] - avant[2], apres[3] - avant[3]
        sx, sy = (1 if dx > 0 else -1 if dx < 0 else 0), (1 if dy > 0 else -1 if dy < 0 else 0)
        occ = {}
        for o in e0:
            if o is not avant and o[0] < 1024:
                for z in cells(o):
                    occ.setdefault(z, set()).add(o[0])
        def sous(k, avant=avant, sx=sx, sy=sy, occ=occ):
            return set().union(*[occ.get((x + sx * k, y + sy * k), set()) for x, y in cells(avant)])
        ici = None
        for k in range(base, lg, pas):  # positions d'où il a fallu repartir au-delà de la base
            ici = sous(k) if ici is None else ici & sous(k)
        cand = (ici or set()) - sous(lg)
        prolonge = cand if prolonge is None else prolonge & cand
    return (base, frozenset(traverse) - poussees, poussees, (), frozenset(prolonge or ()))


def _marqueur_sel(c, sources):
    """C (ka59 sous CREUX) : dans chaque état, UN objet de même couleur est enclos dans le trou du sélectionné (classe c)
    au même décalage, et jamais dans celui d'un non sélectionné (FIGE + c) : c'est le marqueur de sélection. Il est retiré
    des états (l'ASP ne lui apprend aucune loi) et redessiné par la théorie. → (sources, (classe, cases, dx, dy) ou ())."""
    from collections import Counter

    from chrysalide.arc3.logique.theorie import FIGE, _enclos, _sans_marqueur
    coul = lambda v: v % 16 if v >= 16 else v
    par_etat = []
    for tr, *_ in sources:
        for e in tr.etats:
            sel = [h for h in e if h[0] == c]
            if len(sel) != 1:
                return sources, ()
            par_etat.append((e, sel[0], [o for o in e if o is not sel[0] and o[0] < 1024 and _enclos(sel[0], o)]))
    communes = set.intersection(*[{coul(o[0]) for o in d} for _, _, d in par_etat]) if par_etat else set()
    if len(communes) != 1:
        return sources, ()
    k = communes.pop()
    vus = Counter()
    for e, h, dans in par_etat:
        m = [o for o in dans if coul(o[0]) == k]
        if len(m) != 1 or any(coul(o2[0]) == k and o2[0] < 1024 and _enclos(f, o2) for f in e if f[0] == FIGE + c for o2 in e):
            return sources, ()
        vus[(m[0][0], m[0][1], m[0][2] - h[2], m[0][3] - h[3])] += 1
    if len({(cs, dx, dy) for _, cs, dx, dy in vus}) != 1:
        return sources, ()
    marqueur = (*vus.most_common(1)[0][0], tuple(sorted({v[0] for v in vus})))  # + classes vues (0, 272 : même couleur)
    import copy
    out = []
    for tr, *reste in sources:
        t2 = copy.copy(tr)
        t2.etats = [tuple(_sans_marqueur(list(e), c, marqueur[0])) for e in tr.etats]
        out.append((t2, *reste))
    return out, marqueur


def trouver_selection_clic(th, sources):
    """C (ka59 N4, CCM-052-E) : une classe pilotée c a plusieurs objets ; à chaque flèche, UN seul bouge ; l'objet qui bouge
    ne change qu'après un CLIC sur le nouvel objet, et cela est vu au moins une fois. → th.selection_clic = (c, x0, y0),
    (x0, y0) = l'objet qui bouge le premier sans clic préalable (le piloté au départ du niveau)."""
    for c in sorted({c for c, _ in th.moves}):
        ok, change, depart = True, False, None
        for tr, *_ in sources:
            if sum(o[0] == c for o in tr.etats[0]) < 2:
                continue
            sel, clic_vu = None, False
            for t, a in enumerate(tr.actions):
                e0, e1 = tr.etats[t], tr.etats[t + 1]
                if isinstance(a, tuple):
                    cl = [o for o in e0 if o[0] == c and _sous_clic(o, a[1], a[2])]
                    if cl:
                        sel, clic_vu = (cl[0][2], cl[0][3]), True
                    continue
                paires, _ = apparier(e0, e1)
                mv = [(e0[i], e1[j]) for i, j in paires if j is not None and e0[i][0] == c
                      and (e0[i][2], e0[i][3]) != (e1[j][2], e1[j][3])]
                if len(mv) > 1:
                    ok = False
                    break
                if not mv:
                    continue
                avant, apres = mv[0]
                if sel is None:
                    sel = (avant[2], avant[3])
                    if not clic_vu and depart is None:
                        depart = sel
                if (avant[2], avant[3]) != sel:
                    ok = False
                    break
                change = change or clic_vu
                sel = (apres[2], apres[3])
            if not ok:
                break
        if ok and change:
            if depart is None:  # seul le jeu après clic a été vu : le piloté de départ est celui de la 1re image non cliqué
                e = sources[0][0].etats[0]
                autres = [o for o in e if o[0] == c]
                depart = (autres[0][2], autres[0][3])
            th.selection_clic = (c, *depart)
            return


def but_emboite(th, sources):
    """E (CCM-054/055-E), écrit par C : but « emboîter ». Cibles = composantes CREUSES (fragments d'une même classe qui se
    touchent, réunis ; boîte ≥ 3 × 3 dont la case centrale est vide) des classes immobiles de la 1re image du niveau
    courant ; pièces = classes pilotées ou poussées. → ("emboite", centres 2× des cibles, classes des pièces) ou None."""
    from chrysalide.arc3.logique.theorie import FIGE, _boite
    e = sources[-1][0].etats[0]
    pieces = {c for c, _ in th.moves} | set(th.poussables)
    if getattr(th, "selection_clic", ()):
        pieces.add(th.selection_clic[0])
    centres, exige = [], {}
    fams = {_famille(p) % 16 for p in pieces}  # un jumeau d'une pièce (542 = 14 immobile à ka59) n'est pas une cible…
    base = lambda c: c - FIGE if FIGE <= c < FIGE + 1024 else c
    pieces |= {c for c in {o[0] for o in e} if base(c) < 1024 and _famille(base(c)) % 16 in fams}  # …mais une pièce
    boites = [_boite(o) for o in e if o[0] in pieces]
    pw = max((b[2] - b[0] for b in boites), default=0) + 2  # CCM-038-G : une cible n'est pas plus grande que la pièce plus
    ph = max((b[3] - b[1] for b in boites), default=0) + 2  # son cadre (les grandes enceintes ne sont pas des cibles)
    for c in sorted(c for c in {o[0] for o in e} - pieces if base(c) < 1024 and _famille(base(c)) % 16 not in fams):
        reste = {z for o in e if o[0] == c for z in cells(o)}
        while reste:  # composantes 8-connexes de la classe c
            pile, comp = [reste.pop()], set()
            while pile:
                x, y = pile.pop()
                comp.add((x, y))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if (x + dx, y + dy) in reste:
                            reste.discard((x + dx, y + dy))
                            pile.append((x + dx, y + dy))
            bx = _boite((c, frozenset(comp), 0, 0))
            cx2, cy2 = bx[0] + bx[2], bx[1] + bx[3]
            centre_vide = not any(abs(2 * x - cx2) <= 1 and abs(2 * y - cy2) <= 1 for x, y in comp)
            if 2 <= bx[2] - bx[0] <= pw and 2 <= bx[3] - bx[1] <= ph and centre_vide:
                centres.append((cx2, cy2))
            elif centre_vide and (moule := _moule(comp, bx, e, c)) is not None:  # CCM-061-E : creux de la forme exacte
                centres.append((cx2, cy2))                                        # d'un objet (croix-cible du bloc c11)
                pieces.add(moule)
                exige[(cx2, cy2)] = moule  # CCM-044-G : seule cette classe remplit ce moule
    if not (centres and pieces):
        return None
    b = ("emboite", tuple(sorted(set(centres))), tuple(sorted(pieces)))
    return (*b, tuple(sorted(exige.items()))) if exige else b


def _moule(comp, bx, e, c):
    """Classe d'un objet (plus d'une case, autre classe) dont la forme est EXACTEMENT le creux enclos par comp, ou None."""
    import numpy as np
    from scipy.ndimage import binary_fill_holes
    m = np.zeros((bx[3] - bx[1] + 1, bx[2] - bx[0] + 1), bool)
    for x, y in comp:
        m[y - bx[1], x - bx[0]] = True
    trou = [(int(x), int(y)) for y, x in zip(*np.nonzero(binary_fill_holes(m) & ~m), strict=True)]
    if len(trou) < 2:
        return None
    x0, y0 = min(x for x, _ in trou), min(y for _, y in trou)
    forme = frozenset((x - x0, y - y0) for x, y in trou)
    dedans = {(x + bx[0], y + bx[1]) for x, y in trou}
    for o in e:  # l'objet qui REMPLIT déjà le creux (fond de la cible) n'est pas la pièce : elle est ailleurs
        if o[0] != c and o[0] < 1024 and len(o[1]) == len(forme) and not cells(o) & dedans:
            cs = cells(o)
            u, v = min(x for x, _ in cs), min(y for _, y in cs)
            if frozenset((x - u, y - v) for x, y in cs) == forme:
                return o[0]
    return None


def trouver_peint_contact(th, sources):
    """C (re86 N5, CCM-270-C) : une pièce que la théorie déplace sur un objet IMMOBILE d'une autre couleur apparaît, dans
    l'image suivante, entièrement de la couleur de cet objet (contact : 8 voisins) → (classe, forme) de l'objet est une
    « palette » (th.peint_contact) : toute pièce qui la touche en arrivant en prend la couleur (Theorie._peindre)."""
    import numpy as np
    pal = set()
    formes = {f for _, f in th.hotes}  # un objet de la forme d'une pièce n'est pas une palette
    for tr, *_ in sources:
        depart = set(tr.etats[0])
        for t, a in enumerate(tr.actions):
            e0 = tr.etats[t]
            pred, _ = th.pas(e0, a, tr.taille)
            obs = np.asarray(tr.cases[t + 1])
            dessus = {z for q in pred if 512 <= q[0] < 1024 for z in cells(q)}  # marqueur posé sur la pièce : ignoré
            for o in set(pred) - set(e0):
                if len(o[1]) < 2 or o[0] >= 512:
                    continue
                cs = [(x, y) for x, y in cells(o) if 0 <= y < obs.shape[0] and 0 <= x < obs.shape[1] and (x, y) not in dessus]
                vus = {int(obs[y, x]) for x, y in cs}
                k0 = o[0] % 16 if o[0] >= 16 else o[0]
                if len(vus) != 1 or k0 in vus or not cs:
                    continue
                k = vus.pop()
                pal |= {(p[0], p[1]) for p in e0 if p in depart and p[1] not in formes and (p[0] % 16 if p[0] >= 16 else p[0]) == k and cells(p) & _voisinage(cs)
                        and len(p[1]) > 1}
    if pal:  # analogie : tout objet immobile de la MÊME forme qu'une palette vue en est une (re86 : les 5 carrés 4 × 4)
        fp = {f for _, f in pal}
        for tr, *_ in sources:
            pal |= {(o[0], o[1]) for o in tr.etats[0] if o[1] in fp and o[1] not in formes and o[0] < 512
                    and all(o in e for e in tr.etats[:2])}
    th.peint_contact = frozenset(pal)


def trouver_sans_effet(th, sources):
    """C (CW-354.2, défaut de g50t N3) : une flèche jouée qui n'a RIEN changé, alors que la théorie prédisait un
    changement (mur invisible, porte inconnue, bord), est retenue avec les positions des mobiles : la théorie ne la
    reproposera plus d'ici (`Theorie.pas`). Rien n'est supposé ailleurs : c'est une observation, pas une loi générale."""
    vus = set()
    for tr, *_ in sources:
        for t, a in enumerate(tr.actions):
            if isinstance(a, tuple) or set(tr.etats[t]) != set(tr.etats[t + 1]):
                continue
            avant = th.sans_effet
            th.sans_effet = frozenset()
            predit, _ = th.pas(tr.etats[t], a, tr.taille)
            th.sans_effet = avant
            if set(predit) != set(tr.etats[t]):
                vus.add(th.cle_sans_effet(tr.etats[t], a, tr.taille))
    th.sans_effet = frozenset(vus)


def trouver_jauge(th, sources):
    """C (CW-333 ; re86 : GAME_OVER au coup où la barre s'éteint, CCM-175-C) : barre de budget de l'interface (lue par
    `moteur.reserve_coups` sur les images brutes) → loi « chaque action consomme un coup, défaite à 0 ». Rythme lu sur la
    plus longue trajectoire ; réserve comptée sur la DERNIÈRE image de la dernière trajectoire (l'état courant).
    th.jauge = (coups restants, rythme), ou () si aucune barre n'est lue."""
    from chrysalide.arc3.moteur import reserve_coups, reste_barre
    trs = [tr for tr, *_ in sources if getattr(tr, "grilles", None) is not None]

    def lire(tr, k=40):  # au plus k+1 images (coût constant : CCM-244-B, −7 % de coups au banc de 3 min), rythme remis
        n = len(tr.actions)  # à l'échelle des vrais coups
        if n <= k:
            return reserve_coups(tr.grilles, n)
        idx = sorted({round(i * n / k) for i in range(k + 1)})
        r = reserve_coups([tr.grilles[i] for i in idx], len(idx) - 1)
        return r and {**r, "rythme": round(r["rythme"] * n / (len(idx) - 1), 2)}
    lus = [(len(tr.actions), lire(tr)) for tr in trs]
    lus = [(n, r) for n, r in lus if r]
    if not lus:
        th.jauge = ()
        return
    n, r = max(lus, key=lambda x: x[0])
    for tr in trs:  # la barre lue est une INTERFACE : ses cases sortent de la comparaison (re86 N5 : 1re divergence)
        x0, y0, x1, y1 = r["boite"]
        horiz = (x1 - x0) >= (y1 - y0)
        px = [(x, y) for y in range(y0, y1 + 1) for x in range(64)] if horiz else \
            [(x, y) for x in range(x0, x1 + 1) for y in range(64)]
        tr.exclues = frozenset(tr.exclues) | {((y - tr.oy) // tr.s, (x - tr.ox) // tr.s) for x, y in px
                                              if x >= tr.ox and y >= tr.oy}
    # marges prudentes (comme F) : rythme = coups / (cases perdues + 1), CCM-019-F : sans elle, 10 dépassements du vrai
    # sur 73 points des 20 publics ; puis deux cases de barre (sur re86 N5, sans elle, + 6 coups au-dessus du vrai)
    rythme = n / (n / r["rythme"] + 1)
    brut = int(reste_barre(trs[-1].grilles[-1], r) * rythme)
    th.jauge = (max(0, brut - math.ceil(2 * rythme)), round(rythme, 2))


def _grille_classes(etat, mob=frozenset()):
    """{case: classe} d'un état, objets mobiles exclus (le décor où chercher les motifs)."""
    return {z: o[0] for o in etat if o[0] not in mob for z in cells(o)}


_SYMETRIES = [lambda x, y: (x, y), lambda x, y: (-y, x), lambda x, y: (-x, -y), lambda x, y: (y, -x),
              lambda x, y: (-x, y), lambda x, y: (x, -y), lambda x, y: (y, x), lambda x, y: (-y, -x)]


def _occurrences(motif, grille):
    """Translations (et symétries) où le motif {(x, y): classe} apparaît tel quel dans la grille → [(T, dx, dy)]."""
    out = []
    for T in _SYMETRIES:
        m = {T(x, y): c for (x, y), c in motif.items()}
        pleins = sorted((z, c) for z, c in m.items() if c != -1)
        if not pleins:
            continue
        (x0, y0), c0 = pleins[0]  # ancre : une case non vide (le fond vaut -1 des deux côtés)
        for (gx, gy), gc in grille.items():
            if gc != c0:
                continue
            dx, dy = gx - x0, gy - y0
            if all(grille.get((x + dx, y + dy), -1) == c for (x, y), c in m.items()):
                out.append((T, dx, dy))
    return out


def _unique(occ):
    """Économie : la 1re symétrie (identité d'abord) qui place le motif en UN seul endroit ; sinon None (ambigu)."""
    for T in _SYMETRIES:
        lieux = [(t, dx, dy) for t, dx, dy in occ if t is T]
        if len(lieux) == 1:
            return lieux[0]
        if len(lieux) > 1:
            return None
    return None


def _dalles_proposees(autres, courant, mob, sans):
    """CW-350 (reconnaissance ≠ liaison) : les objets qui formaient la DALLE d'une loi de porte vue ailleurs (objets non
    mobiles qui touchent S sur la 1re image de ce niveau-là) PROPOSENT, par leur classe et leur forme, les dalles candidates
    du niveau courant → (cases de chaque candidate, …). Une proposition à vérifier par expérience, pas une loi."""
    if not courant:
        return ()
    e_c = courant[-1][0].etats[0]
    formes = set()
    for tr_k, *_ in autres:
        for p, base, ouv, s_cases in _cases_tenues(tr_k, mob, sans):
            formes |= {(o[0], o[1]) for o in tr_k.etats[0] if o[0] not in mob and cells(o) & s_cases and len(o[1]) <= 6}
    return tuple(sorted(frozenset(cells(o)) for o in e_c if (o[0], o[1]) in formes))


def _portes_transferees(th, autres, courant, mob, sans):
    """C (g50t N2 ; CW-350 : mécanisme / liaison / reconnaissance séparés). Une loi de porte vue sur un AUTRE niveau
    (mécanisme : la dalle S occupée fait passer la classe p de R à A) est reconnue sur le niveau courant par ses MOTIFS
    (classes des cases de la porte R ∪ A, et de la dalle S, sur la 1re image où la loi a été vue), à translation et
    symétrie près. Liaison posée seulement si chaque motif apparaît UNE seule fois ; sinon abstention (th.infos_portes)."""
    if not courant:
        return ()
    gc = _grille_classes(courant[-1][0].etats[0], mob)
    out, notes = [], []
    for tr_k, *_ in autres:
        g0 = _grille_classes(tr_k.etats[0], mob)
        for p, base, ouv, s_cases in _cases_tenues(tr_k, mob, sans):
            r_, a_ = base - ouv, ouv - base
            md = {z: g0.get(z, -1) for z in base | ouv}  # tout l'objet porte (fil compris), ses deux configurations
            ms = {z: g0.get(z, -1) for z in s_cases}
            od, os_ = _unique(_occurrences(md, gc)), _unique(_occurrences(ms, gc))
            if od is None or os_ is None:
                notes.append((p, od is not None, os_ is not None))
                continue
            (T, dx, dy), (Ts, sx, sy) = od, os_
            def place(cs, T=T, dx=dx, dy=dy):
                return frozenset((T(x, y)[0] + dx, T(x, y)[1] + dy) for x, y in cs)
            s2 = frozenset((Ts(x, y)[0] + sx, Ts(x, y)[1] + sy) for x, y in s_cases)
            out.append((p, place(r_), place(a_), s2))
    th.infos_portes = tuple(notes)
    return tuple(out)


def _cases_tenues(tr, mob, sans):
    """→ [(p, cases fermées, cases ouvertes, S)] vus dans la trajectoire tr (voir trouver_tenue)."""
    from collections import Counter
    cases_mob = [{z for o in e if o[0] in mob for z in cells(o)} for e in tr.etats]
    vues = []
    for p in sorted({o[0] for e in tr.etats for o in e} - mob - sans):
        ens = [frozenset(z for o in e if o[0] == p for z in cells(o)) for e in tr.etats]
        configs = Counter(ens)
        if len(configs) != 2:  # exactement deux configurations : fermée (la plus fréquente) et ouverte
            continue
        (base, _), (ouv, _) = configs.most_common(2)
        ouvertes = [t for t, e in enumerate(ens) if e == ouv]
        fermees = [t for t, e in enumerate(ens) if e == base]
        s_cases = frozenset.intersection(*[frozenset(cases_mob[t]) for t in ouvertes]) - frozenset().union(
            *[cases_mob[t] for t in fermees])  # occupées à CHAQUE ouverture, jamais aux fermetures
        if not s_cases:
            continue
        if not (any(ens[t] == base and ens[t + 1] == ouv for t in range(len(tr.actions)))
                and any(ens[t] == ouv and ens[t + 1] == base for t in range(len(tr.actions)))):
            continue  # les deux sens doivent être vus (sinon : `lie`, irréversible, n'est pas exclu)
        if not (ouv - base) and (base - ouv) <= frozenset().union(*[cases_mob[t] for t in ouvertes]):
            continue  # cases seulement CACHÉES sous le mobile (la dalle elle-même) : occultation, pas une porte
        vues.append((p, base, ouv, s_cases))
    return vues


def _cases_coherentes(tr, mob, p, base, ouv, s_cases):
    """Aucune image de tr ne contredit la porte : la classe p y est absente, ou dans la configuration que la dalle
    impose (ouverte si un mobile occupe une case de S, fermée sinon), aux cases cachées par un mobile près."""
    for e in tr.etats:
        ens = frozenset(z for o in e if o[0] == p for z in cells(o))
        if not ens:
            continue
        occ = {z for o in e if o[0] in mob for z in cells(o)}
        attendu = ouv if occ & s_cases else base
        if (ens ^ attendu) - occ:
            return False
    return True


def trouver_porteur(th, sources):
    """C (CCM-102-C) : marqueur de sélection (classes ≥ faits.MARQUEUR, perception CHRYS_MARQUEUR). Si, à chaque coup où
    le marqueur bouge, l'objet qu'il recouvrait bouge du même pas, sauf sous UNE action (le sélecteur) où il saute seul
    sur un autre objet : th.porteur = (marqueur, sélecteur), th.hotes = (classe, forme) portées ; les lois propres des hôtes et
    le faux saut du marqueur sont retirés (le porteur les explique)."""
    from chrysalide.arc3.logique.faits import MARQUEUR
    from chrysalide.arc3.logique.theorie import cells, porteuse
    boite = os.environ.get("CHRYS_PORTEUR_BOITE") == "1"
    for m in sorted({o[0] for tr, *_ in sources for e in tr.etats for o in e if o[0] >= MARQUEUR}):
        suit, saute, hotes, ok = 0, set(), set(), True
        for tr, *_ in sources:
            for t, a in enumerate(tr.actions):
                if isinstance(a, tuple):
                    continue
                m0 = [o for o in tr.etats[t] if o[0] == m]
                m1 = [o for o in tr.etats[t + 1] if o[0] == m]
                if len(m0) != 1 or len(m1) != 1 or (m0[0][2], m0[0][3]) == (m1[0][2], m1[0][3]):
                    continue
                d = (m1[0][2] - m0[0][2], m1[0][3] - m0[0][3])
                h0 = [o for o in tr.etats[t] if o[0] != m and (m0[0][2], m0[0][3]) in cells(o)]
                if not h0 and porteuse(tr.etats[t], m0[0]) is not None:  # pièce creuse (CHRYS_PORTEUR_BOITE, re86 N5)
                    h0 = [porteuse(tr.etats[t], m0[0])]
                if not h0:
                    ok = False
                    break
                h = max(h0, key=lambda o: len(o[1]))  # la pièce, pas une marque d'une case sous le marqueur
                # suivi jugé par recouvrement (≥ 80 % des cases) : l'hôte peut fusionner avec un point de sa couleur
                cs1 = set().union(*[cells(o) for o in tr.etats[t + 1] if o[0] == h[0]] or [set()])  # (re86)

                def garde(v, h=h, cs1=cs1, w=tr.taille[0], hh=tr.taille[1]):  # cases restées dans la grille seulement
                    vis = {(x, y) for x, y in cells(h, *v) if 0 <= x < w and 0 <= y < hh}  # (l'hôte peut sortir en partie)
                    return bool(vis) and len(vis & cs1) >= 0.8 * len(vis)
                if garde(d):
                    suit += 1
                    hotes.add((h[0], h[1]))
                elif boite and garde(d, cs1=set().union(*[cells(o) for o in tr.etats[t + 1] if o[0] < MARQUEUR] or [set()])):
                    suit += 1  # C (re86 N5, CHRYS_PORTEUR_BOITE) : l'hôte a suivi mais a été REPEINT (case de couleur)
                elif garde((0, 0)):
                    saute.add(a)
                    h1 = [o for o in tr.etats[t + 1] if o[0] != m and (m1[0][2], m1[0][3]) in cells(o)]
                    if not h1 and porteuse(tr.etats[t + 1], m1[0]) is not None:
                        h1 = [porteuse(tr.etats[t + 1], m1[0])]
                    hotes |= {(o[0], o[1]) for o in h1}
                    hotes.add((h[0], h[1]))
                else:
                    ok = False
                    break
        if ok and suit >= 2 and len(saute) == 1:
            sel = next(iter(saute))
            th.porteur, th.hotes = (m, sel), frozenset(hotes)
            ajouter_but_marques(th, sources)
            classes = {c for c, _ in hotes}
            th.poussables = frozenset(th.poussables - classes)  # poussée / poursuite : autres explications du même
            th.autonomes = {c: v for c, v in th.autonomes.items() if c not in classes}  # suivi, retirées
            for (c, a) in list(th.moves):
                if c in classes or (c == m and a == sel):
                    th.moves.pop((c, a))
                    th.moves_supposes.pop((c, a), None)
            if boite:  # re86 N5 : le marqueur suivi PARTOUT (pièce creuse) ; ses sauts sous le sélecteur empêchaient l'ASP
                pas = {}   # de lui donner des lois `move` (il prenait poussée + poursuite) → lois relues hors sélecteur
                for tr, *_ in sources:
                    for t, a in enumerate(tr.actions):
                        m0 = [o for o in tr.etats[t] if o[0] == m]
                        m1 = [o for o in tr.etats[t + 1] if o[0] == m]
                        if a != sel and not isinstance(a, tuple) and len(m0) == 1 and len(m1) == 1:
                            pas.setdefault(a, set()).add((m1[0][2] - m0[0][2], m1[0][3] - m0[0][3]))
                # sauts du sélecteur APPRIS : forme de la pièce quittée → forme de la pièce atteinte, et position du
                # marqueur dans celle-ci (pivot propre à la forme : la croix de re86 N5 n'est pas centrée sur sa boîte)
                regles = {}
                for tr, *_ in sources:
                    for t, a in enumerate(tr.actions):
                        m0 = [o for o in tr.etats[t] if o[0] == m]
                        m1 = [o for o in tr.etats[t + 1] if o[0] == m]
                        if a != sel or len(m0) != 1 or len(m1) != 1:
                            continue
                        h0, h1 = porteuse(tr.etats[t], m0[0]), porteuse(tr.etats[t + 1], m1[0])
                        if h0 is not None and h1 is not None:
                            regles.setdefault(h0[1], set()).add((h1[1], (m1[0][2] - h1[2], m1[0][3] - h1[3])))
                th.saut_sel = tuple((f0, *next(iter(v))) for f0, v in regles.items() if len(v) == 1)
                peint = set()  # cases d'un pixel sous la pièce quittée, qui prennent sa couleur au saut
                for tr, *_ in sources:
                    for t, a in enumerate(tr.actions):
                        m0 = [o for o in tr.etats[t] if o[0] == m]
                        h0 = porteuse(tr.etats[t], m0[0]) if a == sel and len(m0) == 1 else None
                        if h0 is None:
                            continue
                        apres = {(o[2], o[3]): o[0] for o in tr.etats[t + 1] if len(o[1]) == 1}
                        peint |= {o[0] for o in tr.etats[t] if len(o[1]) == 1 and o[0] < MARQUEUR and o[0] != h0[0]
                                  and (o[2], o[3]) in cells(h0) and apres.get((o[2], o[3])) == h0[0]}
                th.peint_sel = frozenset(peint)
                # ordre du sélecteur : le 1er (classe, centre y-x, centre x-y) qui prédit TOUS les sauts observés
                sauts = [(tr, t) for tr, *_ in sources for t, a in enumerate(tr.actions) if a == sel]
                for ordre in ("classe", "yx", "xy"):
                    th.ordre_sel = ordre
                    if all({o for o in th.pas(tr.etats[t], sel, tr.taille)[0] if o[0] == m}
                           == {o for o in tr.etats[t + 1] if o[0] == m} for tr, t in sauts):
                        break
                else:
                    th.ordre_sel = "classe"
                vus = {a: next(iter(v)) for a, v in pas.items() if len(v) == 1 and next(iter(v)) != (0, 0)}
                if vus:
                    th.moves.update({(m, a): d for a, d in vus.items()})
                    th.poussables = frozenset(th.poussables - {m})
                    th.autonomes = {c: v for c, v in th.autonomes.items() if c != m}
            return
CANON = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}  # (dx, dy) de chaque flèche ARC


def _completer(th, issues, sources, couleurs, traverse, prior_solide):
    # hypothèses nommées sur les flèches jamais vues réussir (révisables, listées par th.registre()) :
    # H_partage : une flèche fait la même chose à toutes les couleurs contrôlées ; H_oppose : la flèche opposée, l'opposé
    if prior_solide and th.moves:
        ctrl = sorted({c for c, _ in th.moves})
        for a in sorted({a for _, a in th.moves}):
            vs = {th.moves[(c, a)] for c in ctrl if (c, a) in th.moves}
            if len(vs) == 1:
                for c in ctrl:
                    if (c, a) not in th.moves:
                        th.moves[(c, a)], th.moves_supposes[(c, a)] = next(iter(vs)), "H_partage"
        for c in ctrl:
            for a, b in OPPOSEES.items():
                if (c, a) in th.moves and (c, b) not in th.moves:
                    v = th.moves[(c, a)]
                    th.moves[(c, b)], th.moves_supposes[(c, b)] = (-v[0], -v[1]), "H_oppose"
        if os.environ.get("CHRYS_SYMETRIE", "0") == "1":  # H_rotation (idée de Thomas, 19/10) : un déplacement vu
            # pour une flèche vaut, tourné, pour les 3 autres (convention ARC 1 haut, 2 bas, 3 gauche, 4 droite) ;
            # seulement si toutes les flèches vues (non supposées) sont alignées sur cette convention, même pas d
            for c in ctrl:
                vus = {a: th.moves[(c, a)] for a in CANON if (c, a) in th.moves and (c, a) not in th.moves_supposes}
                pas = {abs(v[0]) + abs(v[1]) for v in vus.values()}
                if vus and len(pas) == 1 and all(v == (CANON[a][0] * abs(v[0] + v[1]), CANON[a][1] * abs(v[0] + v[1]))
                                                  for a, v in vus.items()):
                    d = pas.pop()
                    for a, u in CANON.items():
                        if (c, a) not in th.moves:
                            th.moves[(c, a)], th.moves_supposes[(c, a)] = (u[0] * d, u[1] * d), "H_rotation"
                            if os.environ.get("CHRYS_SYM_TRACE"):
                                with open(os.environ["CHRYS_SYM_TRACE"], "a") as f:
                                    f.write(f"rot c{c} a{a} vus={vus}\n")
        for _, c, c2 in sorted(th.transforme):  # H_transforme : la classe transformée d'un mobile garde ses flèches
            for (c0, a), v in list(th.moves.items()):
                if c0 == c and (c2, a) not in th.moves:
                    th.moves[(c2, a)], th.moves_supposes[(c2, a)] = v, "H_transforme"
    for tr, *_ in sources:  # formes observées de chaque classe (pour créer un objet transformé)
        for e in tr.etats:
            for o in e:
                th.formes.setdefault(o[0], o[1])
    th.buts_motifs = buts_motifs([e for tr, *_ in sources for e in tr.etats])
    if os.environ.get("CHRYS_BUT_STATIQUE", "1") == "1":  # allumé par défaut (CW-331.3, porte 1 : PS +32/−1, ARC +2/0)
        th.buts_motifs = [*th.buts_motifs, *buts_statiques(th, sources)]
    if os.environ.get("CHRYS_COPIE", "1") == "1":  # C (CCM-140-C, avec D) : copier le modèle réduit affiché ; allumé
        # par défaut (CW-259) : 20 publics = A, PuzzleScript = A (CCM-210-B), T4 0 → 6 niveaux sous portes (CCM-162-C)
        th.buts_motifs = [*th.buts_motifs, *buts_copie(sources)]
    # autonomes : couleur poursuivie choisie par rejeu (meilleure exactitude sur les transitions vues)
    fl = sorted({c for c, _ in th.moves})
    for c in list(th.autonomes):
        options = [x for x in fl if x != c] or [None]
        def score(x, c=c):
            th.autonomes[c] = x
            return sum(rejeu(th, tr, 0, max(ts) + 1 if ts else 0, libre=False)[0] for tr, ts, _ in sources)
        meilleur = max(options, key=score)
        gain = score(meilleur)
        del th.autonomes[c]  # C (tr87) : sans ce poursuivant, le rejeu est-il aussi bon ? alors il n'explique rien
        sans = sum(rejeu(th, tr, 0, max(ts) + 1 if ts else 0, libre=False)[0] for tr, ts, _ in sources)
        if gain > sans or os.environ.get("CHRYS_POURSUITE_UTILE", "0") != "1":
            th.autonomes[c] = meilleur
    # but : vrai après chaque finale (rejouée depuis le dernier état), faux sur tous les états vus
    finales = [(tr, fin) for tr, _, fin in sources if fin is not None]
    th.but, th.buts_compatibles = None, []
    if finales:  # tous les buts compatibles (registre, pour l'exploration par réfutation) ; on retient le plus simple
        finaux = [(th.pas(monde_final(th, tr), tr.action_cases(fin), tr.taille)[0]) for tr, fin in finales]
        vus = [e for tr, _, _ in sources for e in tr.etats]
        for b in buts_candidats(th, couleurs):
            if all(Theorie._vrai(b, m) for m in finaux) and not any(Theorie._vrai(b, e) for e in vus):
                th.buts_compatibles.append(b)
        th.but = th.buts_compatibles[0] if th.buts_compatibles else None
    # mort : contact entre deux couleurs, vrai après chaque finale perdante, faux partout ailleurs
    pertes = [(tr, fin) for tr, _, fin, issue in issues if issue == "perdu"]
    th.mort = None
    if pertes:
        for a in sorted(couleurs):
            for b in sorted(couleurs):
                if a < b:
                    m = ("contact", a, b)
                    if all(Theorie._vrai(m, th.pas(tr.etats[-1], tr.action_cases(fin), tr.taille)[0]) for tr, fin in pertes) and not any(
                            Theorie._vrai(m, e) for tr, _, _, _ in issues for e in tr.etats):
                        th.mort = m
                        break
            if th.mort:
                break
    # prior : une couleur statique jamais traversée par un mobile est un mur (hors couleurs du but)
    if prior_solide and th.moves:
        mobiles = {c for c, _ in th.moves} | set(th.poussables) | set(th.autonomes)
        but = (set() if not th.but else {c for fam, b in th.but[1] for c in (*fam, b)} if th.but[0] == "paires"
               else set(th.but[1:]))
        consommees = {b for _, b in th.consomme}  # une couleur retirée par lien (porte) reste un mur tant qu elle est là
        th.murs_supposes = frozenset({c for c in couleurs if c not in mobiles | traverse | but | consommees} - th.solides)
        th.solides = frozenset(th.solides | th.murs_supposes)
    if os.environ.get("CHRYS_MARQUEUR", "1") == "1":  # défaut : allumé (CCM-130-C)
        trouver_porteur(th, sources)
    if os.environ.get("CHRYS_ENROULE", "0") == "1":
        trouver_enroulement(th, sources)
    # CW-349.1 : RETOUR, FANTOME, TENUE et MOTIF_FORME allumés par défaut (ARC 5 = 5, PuzzleScript 77 = 77)
    if os.environ.get("CHRYS_RETOUR", "1") == "1" or os.environ.get("CHRYS_FANTOME", "1") == "1":
        trouver_retour(th, sources)
    if os.environ.get("CHRYS_FANTOME", "1") == "1":
        trouver_fantome(th, sources)
    if os.environ.get("CHRYS_TENUE", "1") == "1":
        trouver_tenue(th, sources)
    if os.environ.get("CHRYS_MOTIF_FORME", "1") == "1" and th.bascule:  # C (ft09 N5) : allumé (CW-349.1)
        trouver_motif_formes(th, sources)
    if os.environ.get("CHRYS_CLIC_CONFIG", "1") == "1":  # C (dc22 N3) : allumé (CW-351.3)
        trouver_clic_configs(th, sources)
    if os.environ.get("CHRYS_SELECTION_CLIC", "0") == "1":  # C (ka59 N4, CCM-052-E) : éteint par défaut (CW-259)
        trouver_selection_clic(th, sources)
    if os.environ.get("CHRYS_BUT_EMBOITE", "0") == "1":  # E + C (ka59, CCM-054-E) : éteint par défaut (CW-259)
        th.but_emboite = but_emboite(th, sources)
    if os.environ.get("CHRYS_SANS_EFFET", "1") == "1":  # C (CW-354.2) : allumé par défaut (CW-363.1)
        trouver_sans_effet(th, sources)
    if os.environ.get("CHRYS_JAUGE", "0") == "1":  # C (CW-333) : éteint par défaut (CW-259)
        trouver_jauge(th, sources)
    if os.environ.get("CHRYS_SELECTION", "0") == "1" and not th.porteur:
        trouver_selection(th, sources)
    if os.environ.get("CHRYS_SELECTION", "0") == "1":
        th.debordent = trouver_debord(th, sources)
    if os.environ.get("CHRYS_BASCULE_FORME", "1") == "1" and th.motif and th.bascule:  # défaut : allumé (CCM-130-C)
        th.formes_bascule = formes_bascule(th, sources)
    th.teleports = trouver_teleports(th, sources)
    th.teleports_cases = trouver_teleports_cases(th, sources) if not th.teleports else {}
    if th.enroule:  # tr87 : les « téléportations » aux bords sont l'enroulement, déjà expliqué
        th.teleports_cases = {}
    if os.environ.get("CHRYS_PEINT_CONTACT", "0") == "1":  # C (re86 N5, CCM-270-C) : éteint par défaut (CW-259)
        trouver_peint_contact(th, sources)
    if len(th.buts_compatibles) > 1:  # rationalité du démonstrateur (planification inverse), murs supposés compris
        th.but = but_rationnel(th, [(tr, fin) for tr, _, fin in sources if fin is not None]) or th.but
    return th
