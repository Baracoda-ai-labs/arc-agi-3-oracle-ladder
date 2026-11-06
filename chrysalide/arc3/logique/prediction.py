# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — PRÉDICTION AVEC « JE NE SAIS PAS » (CW-224, critique d'architecture de ChatGPT, chantier 2).
La théorie induite prédit le coup suivant, mais une prédiction n'est ACCEPTÉE que si chaque relation qu'elle utilise a été
OBSERVÉE dans le passé (provenance) ; sinon le moteur s'abstient.
- déplacement : la loi (classe, action) → vecteur doit avoir été vue (pas une hypothèse H_partage/H_oppose) ;
- passabilité, par (classe mobile, classe visée ou fond) : « démontrée » (déjà vu entrer), « bloquée » (déjà vu buter sur
  elle avec ce vecteur), sinon « inconnue » → abstention. Un objet immobile n'est PAS un mur (H_mur n'est qu'une hypothèse) ;
- événement (objet qui change de classe, disparaît, apparaît, hors mobile) : accepté seulement si la même sorte
  d'événement (classe → classe, ou classe retirée) a déjà été observée ; sinon abstention.
Rien ne regarde le coup à venir : la connaissance est construite sur les transitions passées seulement."""
from collections import Counter

from chrysalide.arc3.logique.faits import apparier
from chrysalide.arc3.logique.theorie import cells


class Connaissance:
    """Ce que les transitions passées DÉMONTRENT (et non ce que la théorie suppose)."""

    def __init__(self, tr, ts):
        self.taille, self.exclues = tr.taille, tr.exclues
        self.moves, self.entre, self.bloque, self.evenements = set(), set(), set(), set()
        self.reste = set()  # (classe, action) : déjà vue RESTER sur place sous cette action
        self.support = Counter()  # (classe, action, vecteur) : nombre de fois observé
        comptes = [Counter(o[0] for o in tr.etats[t]) for t in [*ts, max(ts, default=-1) + 1] if 0 <= t < len(tr.etats)]
        self.instables = {c for c in set().union(*comptes) if len({cc.get(c, 0) for cc in comptes}) > 1} if comptes \
            else set()  # classes dont le NOMBRE d'objets a varié (sprite composite, fusion, occultation)
        for t in ts:
            e0, e1, a = tr.etats[t], tr.etats[t + 1], tr.actions[t]
            if isinstance(a, tuple):
                continue
            paires, _ = apparier(e0, e1)
            occ = {}
            for o in e0:
                for c in cells(o):
                    occ.setdefault(c, set()).add(o[0])
            for i, j in paires:
                o = e0[i]
                if j is None:
                    self.evenements.add(("retire", o[0]))
                    continue
                d = (e1[j][2] - o[2], e1[j][3] - o[3])
                if e1[j][0] != o[0]:
                    self.evenements.add(("change", o[0], e1[j][0]))
                if d == (0, 0):
                    self.reste.add((o[0], a, o[2], o[3]))  # par position : une immobilité vaut pour son contexte
                if d != (0, 0):
                    self.moves.add((o[0], a, d))
                    self.support[(o[0], a, d)] += 1
                    for c in cells(o, *d) - cells(o):
                        for k in occ.get(c, {self.lieu(c)}) - {o[0]}:
                            self.entre.add((o[0], k))  # le mobile est entré sur une case de cette classe (ou du fond)
            for i, o in enumerate(e0):
                j = next((jj for ii, jj in paires if ii == i), None)
                if j is None or (e1[j][2], e1[j][3]) != (o[2], o[3]):
                    continue
                for v in {d for (c, aa, d) in self.moves if c == o[0] and aa == a}:  # n'a pas bougé alors qu'il sait
                    for c in cells(o, *v) - cells(o):  # bouger ainsi : ce qu'il visait l'a bloqué (dans ce contexte)
                        for k in occ.get(c, {self.lieu(c)}) - {o[0]}:
                            self.bloque.add((o[0], k, v))

    def lieu(self, c):
        """Case sans objet : « bord » hors de la grille ou dans la zone hors jeu (jauge), sinon « fond »."""
        x, y = c
        w, h = self.taille
        return "bord" if not (0 <= x < w and 0 <= y < h) or (y, x) in self.exclues else "fond"

    def passabilite(self, mobile, cible, v):
        if (mobile, cible, v) in self.bloque:  # déjà entré ET déjà bloqué : dépend d'un contexte invisible (sp80, CCM-094-C)
            return "contradictoire" if (mobile, cible) in self.entre else "bloquee"
        return "demontree" if (mobile, cible) in self.entre else "inconnue"


def predire(th, conn, monde, action, taille):
    """→ (monde prédit, None) si chaque relation utilisée est démontrée ; sinon (None, raison de l'abstention)."""
    if isinstance(action, tuple):
        return None, "clic : non couvert (v1)"
    pred = th.pas(monde, action, taille)[0]
    portees = {c for c, _ in getattr(th, "hotes", ())} if getattr(th, "porteur", None) else set()
    selectionnables = set(th.selection[1]) if getattr(th, "selection", None) else set()
    if portees and action == th.porteur[1]:  # sélecteur : le saut du marqueur doit avoir été vu ≥ 2 fois
        if sum(n for (c, a, _), n in conn.support.items() if c == th.porteur[0] and a == action) < 2:
            return None, f"saut du marqueur vu moins de 2 fois (a{action})"
        return pred, None
    occ = {}
    for o in monde:
        for c in cells(o):
            occ.setdefault(c, set()).add(o[0])
    for c in {o[0] for o in monde} & ({cc for cc, _ in th.moves} | {cc for cc, _, _ in conn.moves}):
        vus = {d for (cc, aa, d) in conn.moves if cc == c and aa == action}
        if c in conn.instables or c in portees or c in th.autonomes:  # nombre variable, hôte porté par le marqueur, ou
            continue  # poursuivant autonome (il suit sa cible, pas les flèches : ar25 N2) : hors contrat, pas une abstention
        if len(vus) > 1:  # le même coup a déjà donné plusieurs déplacements : dépend d'un contexte inconnu
            return None, f"déplacement variable (c{c}, a{action})"
        immobile = {(x, y) for (cc, aa, x, y) in conn.reste if cc == c and aa == action}
        if (c, action) not in th.moves and (len(immobile) < 3 or vus):  # sans effet vu à ≥ 3 places, jamais vu bouger
            return None, f"effet de l'action inconnu (c{c}, a{action})"
    for (c, a), v in th.moves.items():
        if a != action or not any(o[0] == c for o in monde):
            continue
        if (c, a, v) not in conn.moves:
            return None, f"déplacement supposé (c{c}, a{a})"
        if conn.support[(c, a, v)] < 2:  # une loi vue une seule fois n'est pas encore démontrée
            return None, f"déplacement vu une fois (c{c}, a{a})"
        for o in monde:
            if o[0] != c:
                continue
            if (c, a, o[2], o[3]) in conn.reste and c not in selectionnables:  # déjà vu RESTER ici sous ce coup
                return None, f"immobilité déjà vue ici (c{c}, a{a})"
            for p in cells(o, *v) - cells(o):
                for k in occ.get(p, {conn.lieu(p)}) - {c}:
                    ps = conn.passabilite(c, k, v)
                    if ps == "contradictoire" and c in selectionnables:  # immobile car NON sélectionnée, pas bloquée
                        ps = "demontree"
                    if ps in ("inconnue", "contradictoire"):
                        return None, f"passabilité {ps} (c{c} → {k})"
    paires, _ = apparier(monde, pred)
    for i, j in paires:
        if j is None:
            if ("retire", monde[i][0]) not in conn.evenements:
                return None, f"disparition jamais vue (c{monde[i][0]})"
        elif pred[j][0] != monde[i][0] and ("change", monde[i][0], pred[j][0]) not in conn.evenements:
            return None, f"transformation jamais vue (c{monde[i][0]} → c{pred[j][0]})"
    return pred, None


def garder(th, tr, plan, k=3):
    """Prise de main courte (CW-224) : préfixe du plan, au plus `k` coups, dont CHAQUE prédiction enchaînée est acceptée
    (connaissance = toutes les transitions passées de `tr`). → (préfixe, raison de l'arrêt ou None)."""
    th.hors_jeu = tr.exclues
    conn, monde, garde = Connaissance(tr, range(len(tr.actions))), th.avec_selection(tr.etats[-1], tr.actions), []
    for a in plan[:k]:
        pred, raison = predire(th, conn, monde, a, tr.taille)
        if pred is None:
            return garde, raison
        garde.append(a)
        monde = pred
    return garde, None


def mobiles_stables(th, tr):
    """Classes du contrat : celles dont la théorie a une loi de déplacement, moins celles dont le nombre d'objets varie."""
    return {c for c, _ in th.moves} - Connaissance(tr, range(len(tr.actions))).instables


def rejeu_contrat(th, tr, mobiles=None):
    """Rejeu recalé (chaque pas part de l'état observé) jugé sur le CONTRAT seul (CW-235.1, modèle partiel) : positions
    des mobiles stables. Les clics sont jugés aussi. → (exactes, total, 1er écart, mobiles)."""
    mob = mobiles_stables(th, tr) if mobiles is None else mobiles
    ok, premier = 0, None
    for t, a in enumerate(tr.actions):
        pred, _ = th.pas(tr.etats[t], a, tr.taille)
        if contrat(pred, mob) == contrat(tr.etats[t + 1], mob):
            ok += 1
        elif premier is None:
            premier = t
    return ok, len(tr.actions), premier, mob


def contrat(monde, mobiles):
    """Contrat limité (critique ChatGPT : position / occupation, le reste déclaré inconnu) : positions des objets des
    classes mobiles. C'est la seule partie de l'état que la prédiction ACCEPTÉE engage."""
    return frozenset((o[0], o[2], o[3]) for o in monde if o[0] in mobiles)  # la forme reste « inconnue » (sk48, re86)


def categorie(monde, obs, action, mobiles):
    """Catégorie de la transition OBSERVÉE (CW-224) : déplacement libre, collision, interaction, rien."""
    if set(monde) == set(obs):
        return "collision" if not isinstance(action, tuple) and mobiles else "rien"
    paires, nouveaux = apparier(monde, obs)
    autre = bool(nouveaux) or any(j is None or obs[j][0] != monde[i][0] or (monde[i][0] not in mobiles and (
        obs[j][2], obs[j][3]) != (monde[i][2], monde[i][3])) for i, j in paires)
    return "interaction" if autre else "deplacement"


def compter(lignes):
    """Agrège les lignes {categorie, acceptee, juste} : couverture et exactitude des acceptées, par catégorie."""
    par = {}
    for x in lignes:
        par.setdefault(x["categorie"], Counter())
        c = par[x["categorie"]]
        c["n"] += 1
        c["acceptees"] += x["acceptee"]
        c["justes"] += x["acceptee"] and x["juste"]
    tot = Counter()
    for c in par.values():
        tot.update(c)
    par["TOTAL"] = tot
    return {k: {"n": c["n"], "couverture": round(c["acceptees"] / c["n"], 3) if c["n"] else 0.0,
                "exactitude": round(c["justes"] / c["acceptees"], 3) if c["acceptees"] else None}
            for k, c in par.items()}


def cases_inconnues(tr):
    """C (CCM-137-C, dc22) : cases (ligne, colonne) de la vue couvertes par un objet MOBILE dans le dernier état et
    jamais vues dégagées (sans mobile dessus) sur aucune image du niveau. Ce qui y apparaîtra quand le mobile partira
    est INCONNU (CW-224) : une porte ne doit pas compter ces cases comme une divergence."""
    mobiles = {c for c, _, _ in Connaissance(tr, range(len(tr.actions))).moves}
    if not mobiles or not tr.etats:
        return frozenset()
    vues = set()
    for e in tr.etats:
        couvert = {cel for o in e if o[0] in mobiles for cel in cells(o)}
        w, h = tr.taille
        vues |= {(x, y) for x in range(w) for y in range(h)} - couvert
    sous = {cel for o in tr.etats[-1] if o[0] in mobiles for cel in cells(o)}
    return frozenset((y, x) for x, y in sous - vues)
