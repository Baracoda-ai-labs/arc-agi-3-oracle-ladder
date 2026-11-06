# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — boucle « clé, porte, jauge » sortie du script ls20_cle (CW-145), SANS ÉTAT CACHÉ : tout est
recalculé depuis l'historique vu par l'agent (images et actions), comme l'interface `MoteurFormel.proposer`.
Rôles appris sur un niveau réussi (rien de propre à un jeu) :
  - INDICATEUR = objet non mobile que le modificateur transforme (`transforme(M, C, C2)` avec C non mobile) ;
  - PORTE = objet du but ; dans un nouveau niveau, la case de même « type » (cadre et couleurs), prise ENTIÈRE ;
  - MODIFICATEUR = M, retrouvé par son apparence ; JAUGE = couleur dont le nombre de pixels baisse le plus.
Politique : passer sur le modificateur jusqu'à ce que dessin(indicateur) corresponde à dessin(porte) (à la rotation
près, sens appris), puis aller à la porte, sans vider la jauge (BFS sur position, énergie, passages, recharges prises ;
recharges à usage unique, optimisme sur les candidats jamais touchés). Aucun plan tenable → exploration (une vie).
Surprise (le modèle s'est trompé de case) → réinduction sur le niveau courant, prior = théorie apprise."""
from collections import Counter, deque
from dataclasses import dataclass, field

import numpy as np

from chrysalide.arc3.logique import temps
from chrysalide.arc3.logique.correspond import aliaser, correspond, dessin
from chrysalide.arc3.logique.induction import classes_inconnues, induire
from chrysalide.arc3.logique.theorie import cells


def signature(c):
    k = {v: k for k, v in temps.CLASSES.items()}.get(c)
    return None if k is None else (k[1] if k[0] == "statique" else k)


def bloc(g, x, y, s, ox, oy):
    return g[oy + y * s:oy + (y + 1) * s, ox + x * s:ox + (x + 1) * s]


def _zone(g, y0, x0, garder):
    vu, pile = {(y0, x0)}, [(y0, x0)]
    while pile:
        y, x = pile.pop()
        for q in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= q[0] < g.shape[0] and 0 <= q[1] < g.shape[1] and q not in vu and garder(g[q]):
                vu.add(q)
                pile.append(q)
    ys, xs = [p[0] for p in vu], [p[1] for p in vu]
    return g[min(ys):max(ys) + 1, min(xs):max(xs) + 1], (min(ys), min(xs), max(ys), max(xs))


def zone_non_fond(g, y0, x0, fond):
    """Composante 4-connexe de pixels ≠ fond contenant (y0, x0) → pixels de sa boîte."""
    return _zone(np.asarray(g), y0, x0, lambda v: v != fond)[0]


def zone_couleurs(g, y0, x0, palette):
    """Composante 4-connexe des pixels de `palette` contenant (y0, x0) → (pixels, boîte (y0, x0, y1, x1))."""
    return _zone(np.asarray(g), y0, x0, lambda v: int(v) in palette)


def deplacer_mobile(monde, mob, pos):
    return tuple(sorted([o for o in monde if o is not mob] + [(mob[0], mob[1], pos[0], pos[1])],
                        key=lambda o: (o[0], o[2], o[3])))


def localiser(g, gabarit, s, ox, oy, taille, pres=None):
    """Case dont le bloc ressemble le plus au gabarit du mobile (part de pixels égaux), de préférence près de `pres`."""
    g = np.asarray(g)
    meilleur, best = None, -1.0
    for y in range(taille[1]):
        for x in range(taille[0]):
            b = bloc(g, x, y, s, ox, oy)
            if b.shape != gabarit.shape:
                continue
            sc = float((b == gabarit).mean()) - (0.01 * (abs(x - pres[0]) + abs(y - pres[1])) if pres else 0)
            if sc > best:
                meilleur, best = (x, y), sc
    return meilleur if best >= 0.5 else None


def plan_ressource(thb, monde, taille, mob, actions, porte, mods_pos, rech_pos, passages, energie, plein, limite=400000,
                   interdits=frozenset(), franchissables=frozenset()):
    """BFS sur (position du mobile, énergie, passages restants, recharges prises) ; transitions de position données par
    le modèle induit ; un pas effectif coûte 1 ; entrer sur un modificateur compte un passage (modulo 4) ; une recharge
    non prise remet l'énergie à plein (usage unique). But : sur la porte avec 0 passage restant et de l'énergie.
    `energie=None` : exploration sans contrainte d'énergie (on accepte de perdre la vie pour apprendre)."""
    cache = {}

    def suivant(pos, a):
        if (pos, a) not in cache:
            w2, _ = thb.pas(deplacer_mobile(monde, mob, pos), a, taille)
            p2 = next(((o[2], o[3]) for o in w2 if o[0] == mob[0]), pos)
            v = getattr(thb, "moves", {}).get((mob[0], a))
            if p2 == pos and v is not None and (pos[0] + v[0], pos[1] + v[1]) in franchissables:
                p2 = (pos[0] + v[0], pos[1] + v[1])  # case de la porte ou du modificateur : on y entre (CCM-060-C)
            cache[(pos, a)] = p2
        return cache[(pos, a)]

    finie = energie is not None
    depart = ((mob[2], mob[3]), energie if finie else plein, passages, frozenset())
    parent = {depart: None}
    file = deque([depart])
    while file and len(parent) < limite:
        etat = file.popleft()
        pos, e, k, pris = etat
        for a in actions:
            p2 = suivant(pos, a)
            if p2 == pos or (pos, a) in interdits:
                continue
            e2, k2, pris2 = (e - 1 if finie else e), (k - 1) % 4 if p2 in mods_pos else k, pris  # exploration :
            # l'énergie ne compte pas (sinon chaque valeur négative fait un état neuf et la recherche s'épuise)
            if p2 in rech_pos and p2 not in pris:
                e2, pris2 = plein, pris | {p2}
            if p2 == porte and k2 == 0 and (e2 > 0 or not finie):  # exploration : on accepte d'y arriver à vide
                chemin = [a]
                while parent[etat] is not None:
                    etat, a2 = parent[etat]
                    chemin.append(a2)
                return chemin[::-1]
            if e2 <= 0 and finie:
                continue
            n = (p2, e2, k2, pris2)
            if n not in parent:
                parent[n] = (etat, a)
                file.append(n)
    return None


@dataclass
class Roles:
    """Ce qu'un niveau réussi a appris (théorie + rôles) ; transféré tel quel aux niveaux suivants."""
    th: object
    ctrl: set
    sig_m: object
    ind_case: tuple
    type_porte: tuple
    c_jauge: int
    lignes_jauge: list
    ech: tuple  # (s, ox, oy)

    def jauge(self, g):
        return int((np.asarray(g)[self.lignes_jauge] == self.c_jauge).sum())


def apprendre(segs):
    """`segs` : segments du niveau réussi ({grilles, actions, finale, issue}), le dernier finit le niveau.
    → (Roles, None) ou (None, raison)."""
    from chrysalide.arc3.logique.abstraction import induire_abstraction
    _, th, _, src = induire_abstraction(segs, temporelles=True, echelles=True)
    tr1 = src[-1][0]
    ctrl = {c for c, _ in th.moves}
    regles = [(m, c, c2) for m, c, c2 in th.transforme if c not in ctrl]
    if not regles or th.but is None or not hasattr(tr1, "s"):
        return None, "pas d'indicateur, de but ou d'échelle appris"
    ind_cls = {c for _, c, _ in regles} | {c2 for _, _, c2 in regles}
    ind_case = next(c for e in tr1.etats for o in e if o[0] in ind_cls for c in cells(o))
    px, py = next((o[2], o[3]) for e in tr1.etats for o in e if o[0] == th.but[2])
    g0, g1 = np.asarray(segs[-1]["grilles"][0]), np.asarray(segs[-1]["grilles"][-1])
    s, ox, oy = tr1.s, tr1.ox, tr1.oy
    p1 = bloc(g1, px, py, s, ox, oy)
    c_jauge = max(range(16), key=lambda c: int((g0 == c).sum()) - int((g1 == c).sum()))
    lignes = [r for r in range(g0.shape[0]) if (g0[r] == c_jauge).sum() != (g1[r] == c_jauge).sum()]
    return Roles(th, ctrl, signature(regles[0][0]), ind_case, (int(p1[0, 0]), frozenset(np.unique(p1).tolist())),
                 c_jauge, lignes, (s, ox, oy)), None


@dataclass
class Carnet:
    """Mémoire portée d'un niveau à l'autre, recalculable depuis les niveaux joués (`lire_niveau`)."""
    recharges: set = field(default_factory=set)  # classes vues recharger la jauge
    sens: int | None = None  # sens de rotation du dessin par le modificateur
    gabarit: object = None  # dessin du mobile (pour le suivre quand il se mêle aux cases)


def _porte(roles, g):
    s, ox, oy = roles.ech
    t0, pal = roles.type_porte
    h, w = (g.shape[0] - oy) // s, (g.shape[1] - ox) // s
    cases = [(x, y) for y in range(h) for x in range(w)
             if (b := bloc(g, x, y, s, ox, oy)).shape == (s, s) and (b[0] == t0).all() and (b[:, 0] == t0).all()
             and set(np.unique(b).tolist()) == pal and len(np.unique(b[1:-1, 1:-1])) > 1]
    if not cases:
        return None
    zone, (zy0, zx0, zy1, zx1) = zone_couleurs(g, oy + cases[0][1] * s + s // 2, ox + cases[0][0] * s + s // 2, pal)
    boite = {(x, y) for x in range((zx0 - ox) // s, (zx1 - ox) // s + 1) for y in range((zy0 - oy) // s, (zy1 - oy) // s + 1)}
    return zone, (((zx0 + zx1) // 2 - ox) // s, ((zy0 + zy1) // 2 - oy) // s), boite


def _cle(roles, g):
    s, ox, oy = roles.ech
    g = np.asarray(g)
    fond = int(np.bincount(g.ravel()).argmax())
    x, y = roles.ind_case
    return zone_non_fond(g, oy + y * s + s // 2, ox + x * s + s // 2, fond)


def mobiles_niveau(roles, th, tr, part=0.6):
    """Classes qui se déplacent comme le mobile appris (vecteur de `th.moves` pour l'action jouée) dans ce niveau : le
    mobile peut changer d'apparence d'un niveau à l'autre (ls20 niveau 3 : classe inconnue, 10 coups sans le voir)."""
    vec = {a: v for (c, a), v in th.moves.items() if c in roles.ctrl}
    bons, vus = Counter(), Counter()
    for t, a in enumerate(tr.actions):
        v = vec.get(a)
        if v is None:
            continue
        avant = {(o[2], o[3]): o[0] for o in tr.etats[t] if len(o[1]) <= 2}
        apres = {(o[2], o[3]): o[0] for o in tr.etats[t + 1] if len(o[1]) <= 2}
        for (x, y), c in avant.items():
            if apres.get((x, y)) == c:
                continue  # n'a pas bougé
            vus[c] += 1
            bons[c] += apres.get((x + v[0], y + v[1])) == c
    return {c for c, n in bons.items() if n >= 2 and n >= part * vus[c]}


def lire_niveau(roles, carnet, grilles, actions, th=None):
    """Relit un niveau (en cours ou fini) : positions du mobile, surprises, recharges, vies perdues, sens, coût par pas.
    Met à jour `carnet` (recharges, sens, gabarit) ; renvoie les observations du niveau."""
    s, ox, oy = roles.ech
    th = th or roles.th
    tr = temps.traj_temps(grilles, actions, grille=True)
    ctrl = roles.ctrl | {c for c, _ in th.moves} | mobiles_niveau(roles, th, tr)
    vus = [next(((o[2], o[3]) for o in e if o[0] in ctrl), None) for e in tr.etats]
    k = next((i for i, p in enumerate(vus) if p is not None), None)
    if k is not None:  # gabarit repris à chaque niveau, à la 1re image où le mobile est reconnu par sa classe
        carnet.gabarit = bloc(np.asarray(grilles[k]), vus[k][0], vus[k][1], s, ox, oy).copy()
    pos = list(vus)
    if k is not None:  # puis relu dans TOUTES les images du niveau où sa classe manque (avant comme après k) :
        for i in range(k - 1, -1, -1):  # ls20 L3, le mobile remonte un couloir de même apparence que lui
            pos[i] = localiser(grilles[i], carnet.gabarit, s, ox, oy, tr.taille, pos[i + 1]) or pos[i + 1]
        for i in range(k + 1, len(pos)):
            if pos[i] is None:
                pos[i] = localiser(grilles[i], carnet.gabarit, s, ox, oy, tr.taille, pos[i - 1]) or pos[i - 1]
    j = [roles.jauge(g) for g in grilles]
    obs = {"tr": tr, "pos": pos, "ctrl": ctrl, "cout": 1, "surprises": [], "pas_recharge": set(), "vies": 0}
    depart = pos[0]
    cles = [_cle(roles, g) for g in grilles]
    for t, a in enumerate(actions):
        if 0 < j[t] - j[t + 1] <= 20:
            obs["cout"] = max(obs["cout"], j[t] - j[t + 1])
        if carnet.sens is None and dessin(cles[t]) != dessin(cles[t + 1]):
            carnet.sens = next((d for d in (1, -1) if dessin(np.rot90(cles[t], d)) == dessin(cles[t + 1])), None)
        if pos[t] is None or pos[t + 1] is None:
            continue
        mob = next((o for o in tr.etats[t] if o[0] in ctrl), (min(ctrl), frozenset({(0, 0)}), *pos[t]))
        w2, _ = th.pas(deplacer_mobile(tr.etats[t], mob, pos[t]), a, tr.taille)
        prevu = next(((o[2], o[3]) for o in w2 if o[0] == mob[0]), pos[t])
        if j[t + 1] > j[t]:  # jauge remontée : recharge, ou vie perdue (renvoyé au départ)
            obs.setdefault("exclus", set()).add(t)
            if pos[t + 1] == depart and prevu != depart:
                obs["vies"] += 1
                obs["pas_recharge"].add(prevu)
            else:
                carnet.recharges |= {o[0] for o in tr.etats[t] if (o[2], o[3]) == pos[t + 1] and o[0] not in ctrl}
            continue
        if prevu == pos[t + 1]:
            obs["pas_recharge"].add(prevu)  # case atteinte sans recharge : ce n'est pas une recharge
        else:
            obs["surprises"].append((pos[t], a, prevu, pos[t + 1]))
    return obs


def ecarts_mobile(th, obs):
    """Transitions (t) où la position prédite du mobile diffère de l'observée (hors vies perdues et recharges) : le juge
    des réparations. La comparaison objet par objet ne convient pas ici : le dessin du mobile se mêle aux cases."""
    tr, pos, ctrl, out = obs["tr"], obs["pos"], obs["ctrl"], set()
    exclus = obs.get("exclus", set())
    for t, a in enumerate(tr.actions):
        if pos[t] is None or pos[t + 1] is None or t in exclus:
            continue
        mob = next((o for o in tr.etats[t] if o[0] in ctrl), (min(ctrl), frozenset({(0, 0)}), *pos[t]))
        w2, _ = th.pas(deplacer_mobile(tr.etats[t], mob, pos[t]), a, tr.taille)
        if next(((o[2], o[3]) for o in w2 if o[0] == mob[0]), pos[t]) != pos[t + 1]:
            out.add(t)
    return out


def reparer_blocages(th, obs, roles):
    """Étage 2, liste fermée, sans LLM : pour chaque surprise du mobile, lois candidates gardées seulement si elles
    réduisent les écarts de position du mobile sur tout le niveau SANS en créer (même esprit que `verifier_loi`) :
    bloqué alors qu'un pas était prévu → `fond_solide` (case vide) ou `solide c` ; avancé alors qu'un blocage était
    prévu → `fond_solide` faux (case vide) ou `non_solide c` ; arrivé ailleurs → `teleporte_case` de la case visée."""
    from chrysalide.arc3.logique.verifier import appliquer
    tr, mc, ajout = obs["tr"], min(roles.ctrl), []
    ecarts = ecarts_mobile(th, obs)
    for q, a, _, vu in obs["surprises"]:
        v = th.moves.get((mc, a)) or next((th.moves[(c, a)] for c in roles.ctrl if (c, a) in th.moves), None)
        t = next((t for t in sorted(ecarts) if obs["pos"][t] == q and tr.actions[t] == a), None)
        if v is None or t is None:
            continue
        cible = (q[0] + v[0], q[1] + v[1])
        sur = sorted({o[0] for o in tr.etats[t] if cible in cells(o) and o[0] not in obs["ctrl"]})
        if vu == q:
            cands = ([("fond_solide", True)] if not sur else []) + [("solide", c) for c in sur]
        elif vu == cible:
            cands = ([("fond_solide", False)] if not sur else []) + [("non_solide", c) for c in sur]
        else:
            cands = [("teleporte_case", cible[0], cible[1], vu[0] - cible[0], vu[1] - cible[1])]
        for loi in cands:
            th2 = appliquer(th, loi)
            th2.hors_jeu = th.hors_jeu
            e2 = ecarts_mobile(th2, obs)
            if e2 < ecarts:  # strictement moins d'écarts, aucun nouveau
                th, ecarts = th2, e2
                ajout.append(loi)
                break
    return th, ajout


def proposer(roles, carnet, grilles, actions, limite=400000):
    """Plan (codes d'action) pour finir le niveau courant, depuis son historique. → (plan | None, infos)."""
    th = roles.th
    obs = lire_niveau(roles, carnet, grilles, actions)
    brutes = list(obs["surprises"])  # avant toute réinduction ou réparation
    infos = {"surprises": len(obs["surprises"]), "vies_perdues": obs["vies"]}
    if obs["surprises"] and carnet.gabarit is not None:  # réinduction sur ce niveau, joueur replacé par son gabarit
        tr = obs["tr"]
        mc = min(roles.ctrl)
        tr.etats = [tuple(o for o in e if o[0] not in roles.ctrl and (o[2], o[3]) != p)
                    + (((mc, frozenset({(0, 0)}), p[0], p[1]),) if p else ()) for e, p in zip(tr.etats, obs["pos"],
                                                                                         strict=True)]
        th2, _ = induire([(tr, None, None)], anciennes=th)
        th2.but = th2.but or th.but
        th = th2
        obs = lire_niveau(roles, carnet, grilles, actions, th=th)  # surprises relues dans le nouveau modèle
        infos["reinduction"] = {"saut": dict(th.saut), "teleports": dict(th.teleports),
                                "teleports_cases": dict(th.teleports_cases)}
    if obs["surprises"]:  # étage 2, liste fermée : un pas bloqué sans raison → case vide ou objet solide, vérifiés
        th, reparees = reparer_blocages(th, obs, roles)
        if reparees:
            infos["lois_ajoutees"] = reparees
            obs = lire_niveau(roles, carnet, grilles, actions, th=th)
    infos["surprises_restantes"] = len(obs["surprises"])
    infos["_surprises"] = list(obs["surprises"])
    tr = obs["tr"]
    monde = tr.etats[-1]
    g, g0 = np.asarray(grilles[-1]), np.asarray(grilles[0])
    pt = _porte(roles, g0)
    if pt is None:
        return None, {**infos, "refus": "porte introuvable"}
    zone_porte, porte, boite_porte = pt
    ctrl = obs["ctrl"]
    p = obs["pos"][-1]
    if p is None:  # mobile invisible (collé à une zone de même apparence, ou bloqué) : coup discriminant, une direction
        essayees = Counter()  # pas encore essayée depuis le dernier changement perçu
        for t in range(len(actions) - 1, -1, -1):
            if tr.etats[t + 1] != tr.etats[t]:
                break
            essayees[actions[t]] += 1
        dirs = sorted({a for (c, a) in th.moves if c in roles.ctrl and a in (1, 2, 3, 4)}) or [1, 2, 3, 4]
        a = min(dirs, key=lambda d: (essayees[d], d))
        return [a], {**infos, "mode": "chercher_mobile", "plan": 1, "_th": th,
                     "_prevu": (None, monde, tr.taille, set())}
    mob = next((o for o in monde if o[0] in ctrl and (o[2], o[3]) == p), (min(roles.ctrl), frozenset({(0, 0)}), *p))
    monde = tuple(o for o in monde if (o[2], o[3]) != p or o is mob) + (() if mob in monde else (mob,))
    thb, alias = aliaser(th, monde, signature)
    thb.hors_jeu = tr.exclues
    cle = _cle(roles, g)
    sens_k = [carnet.sens] if carnet.sens else [1, -1]
    tours = next((k for k in range(4) if any(correspond(zone_porte, np.rot90(cle, d * k)) for d in sens_k)), None)
    reste = roles.jauge(g) // obs["cout"]
    plein = max(1, max(roles.jauge(x) for x in grilles) // obs["cout"])
    vus = {q for q in obs["pos"] if q}
    mods_pos = {(o[2], o[3]) for o in monde if signature(o[0]) == roles.sig_m}
    franchissables = frozenset(boite_porte | mods_pos)  # la porte et le modificateur : cases où l'on DOIT entrer,
    # rendues franchissables CASE PAR CASE (lever leurs classes rendait franchissables tous les murs de même apparence :
    # 484 pas contre un mur dans E2E4, CCM-150-A)
    inconnues = classes_inconnues(th, monde) - alias - {o[0] for o in monde if (o[2], o[3]) == porte}
    touchees = {o[0] for o in monde if (o[2], o[3]) in vus and o[0] not in ctrl}
    petits = {(o[2], o[3]) for o in monde if len(o[1]) <= 2 and o[0] not in ctrl and o[0] not in thb.solides
              and (o[2], o[3]) not in mods_pos and (o[2], o[3]) != porte and o[0] not in touchees}
    rech_pos = ({(o[2], o[3]) for o in monde if o[0] in carnet.recharges} or petits
                or {(o[2], o[3]) for o in monde if o[0] in inconnues and o[0] not in ctrl}) - obs["pas_recharge"]
    vues = {}
    for q, a, _, _ in obs["surprises"]:
        vues[(q, a)] = vues.get((q, a), 0) + 1
    for q, a, _, vu in brutes:  # un pas resté SANS EFFET deux fois au même endroit est interdit, même si une loi
        if vu == q:  # réparée prétend l'expliquer (CCM-150-A, point 1)
            vues[(q, a, "sans_effet")] = vues.get((q, a, "sans_effet"), 0) + 1
    interdits = frozenset(k[:2] for k, n in vues.items() if n >= 2)  # même surprise deux fois : transition interdite
    infos["sans_effet_interdits"] = sum(1 for k, n in vues.items() if len(k) == 3 and n >= 2)
    actions_dispo = sorted({a for _, a in thb.moves})
    k = tours if tours is not None else 0
    plan = plan_ressource(thb, monde, tr.taille, mob, actions_dispo, porte, mods_pos, rech_pos, k, reste, plein,
                          limite=limite, interdits=interdits, franchissables=franchissables)
    mode = "ressource"
    if not plan:
        plan = plan_ressource(thb, monde, tr.taille, mob, actions_dispo, porte, mods_pos, rech_pos, k, None, plein,
                              limite=limite, interdits=interdits, franchissables=franchissables)
        mode = "exploration"
    infos.update(mode=mode, tours=tours, reste=reste, plein=plein, recharges_candidates=len(rech_pos),
                 correspond=correspond(zone_porte, cle), plan=None if not plan else len(plan))
    infos["_th"], infos["_prevu"] = thb, (mob, monde, tr.taille, set(rech_pos))
    return plan, infos


def prevoir(infos, plan):
    """Positions du mobile prévues par le modèle le long du plan (pour arrêter l'exécution à la 1re divergence)."""
    thb, (mob, monde, taille, _) = infos["_th"], infos["_prevu"]
    if mob is None:
        return [None] * len(plan)
    pos, out = (mob[2], mob[3]), []
    for a in plan:
        w2, _ = thb.pas(deplacer_mobile(monde, mob, pos), a, taille)
        pos = next(((o[2], o[3]) for o in w2 if o[0] == mob[0]), pos)
        out.append(pos)
    return out


def residus(roles, carnet, grilles, actions, th=None):
    """Résidu d'un niveau dans les mots de l'ontologie (CW-155, lot 3 de B) : une ligne par transition où le modèle
    s'est trompé de case pour le mobile : état (objets, jauge), action, prédit (et la loi qui l'explique), observé."""
    th = th or roles.th
    obs = lire_niveau(roles, carnet, grilles, actions, th=th)
    tr, out = obs["tr"], []
    noms = {1: "haut", 2: "bas", 3: "gauche", 4: "droite", 5: "espace", 7: "annuler"}
    for q, a, prevu, vu in obs["surprises"]:
        t = next(t for t in range(len(actions)) if obs["pos"][t] == q and actions[t] == a and obs["pos"][t + 1] == vu)
        cible = (q[0] + th.moves.get((min(roles.ctrl), a), (0, 0))[0], q[1] + th.moves.get((min(roles.ctrl), a), (0, 0))[1])
        sur = sorted({o[0] for o in tr.etats[t] if cible in cells(o) and o[0] not in roles.ctrl})
        loi = ("bloque par " + ",".join(f"c{c}" for c in sur if c in th.solides) if prevu == q and sur
               else "fond_solide" if prevu == q else f"move {th.moves.get((min(roles.ctrl), a))}")
        out.append({"t": t, "mobile": q, "action": noms.get(a, a), "predit": prevu, "loi": loi, "observe": vu,
                    "deplacement_observe": (vu[0] - q[0], vu[1] - q[1]), "case_visee": cible,
                    "classes_case_visee": sur, "jauge": roles.jauge(grilles[t]),
                    "objets": sorted((o[0], o[2], o[3], len(o[1])) for o in tr.etats[t])})
    return out


def buts_candidats_lignes(th):
    """Buts compatibles énumérés par l'ASP (choix du but, CW-155), en lignes, avec celui retenu par la rationalité."""
    return {"candidats": [str(b) for b in sorted(th.buts_compatibles or [], key=str)], "retenu": str(th.but),
            "transforme": [str(r) for r in sorted(th.transforme)], "moves": {str(k): v for k, v in th.moves.items()}}
