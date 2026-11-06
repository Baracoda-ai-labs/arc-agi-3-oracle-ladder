# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — une théorie = un jeu de règles du vocabulaire de B (déplacement, collision, poussée, consommation,
lien, agent autonome) avec ses paramètres ; `pas()` la rejoue sur un monde d'objets, `rendu()` en refait l'image en cases.
Toutes les propriétés portent sur la COULEUR (vocabulaire : `solide(J) :- obj(J,C,_), couleur_solide(C)`).
Le monde garde les objets cachés (recouverts) : c'est ce qui permet le rejeu exact quand le joueur passe sur une case."""
import os
from dataclasses import dataclass, field, replace
from itertools import pairwise

import numpy as np

ORDRE_POURSUITE = ((1, 0), (-1, 0), (0, 1), (0, -1))


def cells(o, dx=0, dy=0):
    return {(o[2] + a + dx, o[3] + b + dy) for a, b in o[1]}


_FORMES = {}


VIRTUEL = 1024  # classe de l'objet virtuel de sélection cachée (aucune case : ni dessiné, ni occupant)
MEM_TRAJET, MEM_FANTOME, MEM_JAUGE, ECRASE, SEL_CLIC = 1025, 1026, 1027, 1028, 1029
FIGE = 8192  # classe provisoire des objets non sélectionnés (selection_clic), jamais rendue
OUVERT = 4096  # porte « tenue » ouverte : classe OUVERT + c (gardée, ni dessinée ni bloquante), g50t dalle → porte  # objets virtuels de la boucle temporelle (g50t) : trajet enregistré, fantôme (chemin, k)
_CHEMINS = {}  # identifiant → tuple de pas (dx, dy) ; partagé, les identifiants sont des hachages des chemins


def cle_objet(o):
    """Clé de tri déterministe d'un objet ; la forme triée est mémorisée (le tri revient à chaque pas du BFS)."""
    f = _FORMES.get(o[1])
    if f is None:
        f = _FORMES[o[1]] = tuple(sorted(o[1]))
    return o[0], o[2], o[3], f


@dataclass
class Theorie:
    moves: dict = field(default_factory=dict)        # (couleur, action) -> (dx, dy)
    solides: frozenset = frozenset()
    murs_supposes: frozenset = frozenset()            # hypothèse nommée H_mur (prior révisable) : sous-ensemble de solides
    moves_supposes: dict = field(default_factory=dict)  # (couleur, action) -> nom de l'hypothèse (H_partage, H_oppose)
    poussables: frozenset = frozenset()
    consomme: frozenset = frozenset()                 # (couleur qui recouvre, couleur retirée)
    lie: frozenset = frozenset()                      # (couleur retirée, couleur déclencheuse épuisée)
    autonomes: dict = field(default_factory=dict)     # couleur -> couleur poursuivie
    motif: frozenset = frozenset()                    # clic : décalages (dx, dy) des objets de même forme basculés
    bascule: dict = field(default_factory=dict)       # clic : couleur -> couleur suivante
    zone: int | None = None                           # clic : seuls les objets dans la boîte d'un objet de cette couleur
    derives: dict = field(default_factory=dict)       # miroir : classe D -> (classe source, sens 'x'|'y'|'xy', 2·axe)
    teleports_cases: dict = field(default_factory=dict)  # case (x, y) -> D : arriver sur cette case décale de D
    teleports: dict = field(default_factory=dict)     # classe K -> décalage D : arriver sur K déplace encore de D
    saut: dict = field(default_factory=dict)          # (couleur, action) -> 2·V : si le pas V est bloqué, sauter à 2·V
    transforme: frozenset = frozenset()               # (M, C, C2) : un mobile atterrit sur M → objets C deviennent C2
    formes: dict = field(default_factory=dict)        # classe -> forme observée (pour créer un objet transformé)
    hors_jeu: frozenset = frozenset()                 # cases (ligne, colonne) de jauge de la trajectoire courante : à
    #                                                   fixer par l'appelant (tr.exclues), elles dépendent du niveau
    annule: int | None = None                         # action « annuler » (UNDO) : revient à l'état précédent
    hotes: frozenset = frozenset()                    # (classe, forme) qui ont porté le marqueur
    clic_configs: tuple = ()                          # ((bouton, avant, après), …) : le clic sur le bouton (objet) remplace
                                                      # les objets « avant » par « après » et inversement ; ou (bouton,
                                                      # "echange", P, Q) : échange les objets d'une case en P et Q (dc22)
    motif_formes: tuple = ()                          # ((forme cliquée, {(dx, dy) 2×centre, forme basculée}), …) (ft09 N5)
    formes_bascule: frozenset = frozenset()          # clic : formes déjà vues basculer (vide = toutes ; ft09 N3)
    obligations: dict = field(default_factory=dict)   # but → obligations (CW-251, but comme contrat)
    selection: tuple | None = None                    # (sélecteur, (classes dans l'ordre), index initial) : sélection
                                                      # CACHÉE (re86 N2) ; objet virtuel (VIRTUEL, ∅, index, 0)
    debordent: frozenset = frozenset()                # classes vues sortir EN PARTIE de la grille (re86)
    enroule: dict = field(default_factory=dict)       # classe → (axe 0=x 1=y, min, max) : enroulement (tr87)
    porteur: tuple | None = None                      # (classe marqueur, action sélecteur) : l'objet sous le marqueur le suit (re86)
    ordre_sel: str = "classe"                         # ordre des hôtes sous le sélecteur : classe, ou centre "yx" / "xy" (re86 N5)
    saut_sel: tuple = ()                              # ((forme de départ, forme d'arrivée, décalage du marqueur), …) appris (re86 N5)
    peint_sel: frozenset = frozenset()                # classes d'une case que la pièce quittée sous le sélecteur repeint (re86 N5)
    retour: tuple = ()                                # ((classe, action, x, y), …) : sous l'action, le mobile revient au départ (g50t)
    fantome: tuple | None = None                      # (joueur, action boucle, classe fantôme, x0, y0) : boucle temporelle (g50t)
    tenue: tuple = ()                                 # ((porte, dalle), …) : porte absente tant qu'un mobile occupe la dalle
    selection_clic: tuple = ()                        # (classe, x0, y0) : un clic sur un objet de la classe le sélectionne ;
                                                      # les flèches ne déplacent que lui ; objet virtuel (SEL_CLIC, ∅, x, y)
    glisse: tuple = ()                                # (distance max, classes traversées) : objet poussé par le
                                                      # sélectionné au clic, glisse jusqu'à l'obstacle (ka59, CCM-041-G)
    peint_contact: frozenset = frozenset()            # (classe, forme) « palette » : une pièce posée dessus en prend la couleur (re86)
    marqueur_sel: tuple = ()                          # (classe, cases, dx, dy, classes vues) : marqueur de sélection dans le trou du
                                                      # sélectionné (ka59 sous CREUX), redessiné à chaque pas, sans loi propre
    sans_effet: frozenset = frozenset()               # {(action, {(classe, x, y) des mobiles})} : coup vu SANS EFFET là
    portes_cases: tuple = ()                          # ((classe, cases), …) : ces cases bloquent tant que la classe les occupe
    tenue_cases: tuple = ()                           # ((classe, R, A, S), …) : tant qu'un mobile occupe S, R part et A arrive
    _dalles: dict = field(default_factory=dict, compare=False, repr=False)  # cases de chaque dalle (cachée sous un mobile)
    fond_solide: bool = False                         # on n'entre que sur des cases couvertes par un objet (ls20)
    desel: dict = field(default_factory=dict)         # sélection exclusive : couleur sélectionnée -> couleur au repos
    exclusif: bool = False                            # clic : sélection exclusive, les autres « contrôlés » rebasculent
    but: tuple | None = None                          # ('sortie', cm, cs) | ('remplir', cd, cs) | ('absent', c, c)
    buts_compatibles: list = field(default_factory=list)  # buts concurrents non réfutés (registre)
    buts_motifs: list = field(default_factory=list)  # candidats motif_rel vus dans le niveau (CW-228, ft09)
    mort: tuple | None = None                         # ('contact', ca, cb) : perdu si deux objets se recouvrent
    jauge: tuple = ()                                 # (coups restants à la dernière image vue, rythme) : chaque action
                                                      # consomme un coup, défaite à 0 ; objet virtuel (MEM_JAUGE, ∅, reste, 0)

    def n_regles(self):
        return (len(self.moves) - len(self.moves_supposes) + len(self.solides - self.murs_supposes) + len(self.poussables) + len(self.consomme) + len(self.lie)
                + len(self.autonomes) + len(self.motif) + len(self.bascule) + (self.zone is not None) + self.exclusif
            + len(self.desel) + len(self.derives) + len(self.transforme) + len(self.saut) + self.fond_solide)

    def registre(self):
        """Hypothèses nommées non prouvées par les transitions (CW-065.4) : à réfuter en priorité si on explore."""
        r = {f"H_mur(c{c})": "statique jamais traversé = mur" for c in sorted(self.murs_supposes)}
        r.update({f"{h}(c{c},a{a})": f"move {self.moves[(c, a)]} supposé" for (c, a), h in sorted(self.moves_supposes.items())})
        if len(self.buts_compatibles) > 1:
            r["H_but"] = f"{len(self.buts_compatibles)} buts compatibles, le plus simple retenu : {self.but}"
        return r

    def pour_but(self, but):
        """Copie de la théorie visant `but`, avec H_mur levée sur les couleurs du but (règle de B, CW-078) :
        une sortie jamais traversée n'est pas un mur quand on fait l'hypothèse qu'il faut l'atteindre."""
        cs = ({c for fam, b in but[1] for c in (*fam, b)} if but[0] == "paires"
              else {k for k, _ in but[1]} if but[0] in ("marques", "copie") else set(but[1:]))
        retire = self.murs_supposes & cs
        return replace(self, but=but, solides=self.solides - retire, murs_supposes=self.murs_supposes - retire)

    def reviser_mur(self, c):
        """Une observation montre la couleur c traversée : on retire l'hypothèse H_mur(c)."""
        self.solides, self.murs_supposes = self.solides - {c}, self.murs_supposes - {c}

    def couches(self):
        """Ordre de dessin (haut d'abord) : déplacés aux flèches, puis autonomes, poussables, statiques."""
        fl = {c for c, _ in self.moves} | ({self.fantome[2]} if self.fantome else set())  # fantôme : couche du joueur
        mk = self.marqueur_sel[0] if self.marqueur_sel else None  # marqueur de sélection : au-dessus de sa pièce
        return lambda c: 4 if c == mk else 3 if c in fl else 2 if c in self.autonomes else 1 if c in self.poussables else 0

    def texte(self):
        r = [f"move(c{c},a{a},{v[0]},{v[1]})." + (f" [{self.moves_supposes[(c, a)]}]" if (c, a) in self.moves_supposes else "")
             for (c, a), v in sorted(self.moves.items())]
        r += [f"solide(c{c})." if c not in self.murs_supposes else f"solide(c{c}) [H_mur]." for c in sorted(self.solides)] + [f"poussable(c{c})." for c in sorted(self.poussables)]
        r += [f"consomme(c{a},c{b})." for a, b in sorted(self.consomme)] + [f"lie(c{a},c{b})." for a, b in sorted(self.lie)]
        r += [f"poursuit(c{a},c{b})." for a, b in sorted(self.autonomes.items())]
        r += [f"motif({dx},{dy})." for dx, dy in sorted(self.motif)]
        r += [f"bascule(c{a},c{b})." for a, b in sorted(self.bascule.items())]
        r += [f"retour(c{c},a{a},{x},{y})." for c, a, x, y in self.retour]
        r += [f"fantome(c{self.fantome[0]},a{self.fantome[1]},c{self.fantome[2]})."] if self.fantome else []
        r += [f"tenue(c{p},c{d})." for p, d in self.tenue]
        r += [f"tenue_cases(c{p},{len(r_)},{len(a_)},{len(s_)})." for p, r_, a_, s_ in self.tenue_cases]
        r += [f"porte_cases(c{p},{len(cs)})." for p, cs in self.portes_cases]
        r += [f"sans_effet({len(self.sans_effet)})."] if self.sans_effet else []
        r += [f"selection_clic(c{self.selection_clic[0]})."] if self.selection_clic else []
        r += [f"jauge({self.jauge[0]},{self.jauge[1]:g})."] if self.jauge else []
        r += [f"motif_forme({len(f)},{len(d)})." for f, d in self.motif_formes]
        r += [f"clic_config(c{b[0]},{len(r_) if r_ != 'echange' else 'echange'})." for b, r_, *_ in self.clic_configs]
        r += [f"zone(c{self.zone})."] if self.zone is not None else []
        r += ["exclusif."] if self.exclusif else []
        r += [f"desel(c{a},c{b})." for a, b in sorted(self.desel.items())]
        r += ["fond_solide."] if self.fond_solide else []
        r += [f"annule(a{self.annule})."] if self.annule is not None else []
        r += [f"porteur(c{self.porteur[0]},a{self.porteur[1]})."] if self.porteur else []
        r += [f"transforme(c{m},c{c},c{c2})." for m, c, c2 in sorted(self.transforme)]
        r += [f"saut(c{c},a{a},{v[0]},{v[1]})." for (c, a), v in sorted(self.saut.items())]
        r += [f"teleporte(c{k},{d[0]},{d[1]})." for k, d in sorted(self.teleports.items())]
        r += [f"teleporte_case({p[0]},{p[1]},{d[0]},{d[1]})." for p, d in sorted(self.teleports_cases.items())]
        r += [f"miroir(c{d},c{v[0]},{v[1]},{v[2] / 2:g})." for d, v in sorted(self.derives.items(), key=str)
              if not isinstance(d, tuple)]
        r += [f"reflet(c{d[1]},{'+'.join(f'c{c}' for c in sorted(v[0]))},{v[1]},{v[2] / 2:g})."
              for d, v in sorted(self.derives.items(), key=str) if isinstance(d, tuple)]
        for nom, x in (("but", self.but), ("mort", self.mort)):
            if x and x[0] == "paires":
                r.append(f"{nom}(" + " et ".join(f"{'|'.join(f'c{c}' for c in fam)} sur c{b}" for fam, b in x[1]) + ").")
            elif x and x[0] == "sortie_si":
                r.append(f"{nom}(sortie,c{x[1]},c{x[2]}) si c{x[3]}.")
            elif x:
                r.append(f"{nom}({x[0]},c{x[1]},c{x[2]}).")
        return " ".join(r)

    # --- dynamique ---------------------------------------------------------------------------------------------
    def couleurs_dynamiques(self):
        """Couleurs qui peuvent bouger, disparaître ou changer ; les autres objets sont un décor fixe."""
        return ({c for c, _ in self.moves} | set(self.poussables) | set(self.autonomes) | {c for c, _ in self.hotes}
                | {c for _, a, b in self.transforme for c in (a, b)}
                | {c for p in self.consomme | self.lie for c in p} | set(self.bascule) | set(self.bascule.values()))

    def _pas_selection_clic(self, monde, action, taille, fixe, precedent):
        """C (ka59 N4, CCM-052-E ; CHRYS_SELECTION_CLIC) : un clic sur un objet de la classe c le SÉLECTIONNE (aucune case ne
        change) ; sous les autres actions, les objets de c non sélectionnés sont figés (classe provisoire FIGE + c) et le
        sélectionné suit les lois de c ; sa position est gardée dans l'objet virtuel SEL_CLIC."""
        c, x0, y0 = self.selection_clic
        fam = lambda k: (k - 512) % 16 if 512 <= k < 1024 else k % 16 if k >= 16 else k
        v = [o for o in monde if o[0] == SEL_CLIC]
        seuls = [o for o in monde if o[0] == c]
        # sans état caché (monde recalé sur une image) : la pièce qui porte le marqueur de sélection, sinon le seul objet
        # de c (jumeau séparé par la perception), sinon le piloté de départ
        marque = []
        if self.marqueur_sel and not v:
            k, _cs, dx, dy = self.marqueur_sel[:4]
            pos = {(o[2], o[3]) for o in monde if o[0] < 1024 and fam(o[0]) == fam(k) and len(o[1]) == len(_cs)}
            marque = [o for o in monde if o[0] < 1024 and fam(o[0]) == fam(c) and len(o[1]) > 1 and (o[2] + dx, o[3] + dy) in pos]
        sx, sy = ((v[0][2], v[0][3]) if v else (marque[0][2], marque[0][3]) if len(marque) == 1
                  else (seuls[0][2], seuls[0][3]) if len(seuls) == 1 else (x0, y0))
        # jumeau perçu de la classe (542 = 14 immobile à ka59, image réelle) : c'est une pièce comme les autres
        monde = tuple((c, *o[1:]) if o[0] != c and o[0] < 1024 and fam(o[0]) == fam(c) and len(o[1]) > 1 else o for o in monde)
        reste = [o for o in monde if o[0] != SEL_CLIC]
        if self.marqueur_sel:  # le marqueur n'a pas de loi : retiré, puis redessiné dans le trou du sélectionné
            reste = _sans_marqueur(reste, c, self.marqueur_sel[0])
        if isinstance(action, tuple):
            cl = [o for o in reste if o[0] == c and _sous_clic(o, action[1], action[2])]
            if cl:
                if self.marqueur_sel:  # le marqueur REMPLACE le contenu du trou de la pièce cliquée (ka59 : le 5 de B)
                    reste = [o for o in reste if o[0] >= 1024 or not _enclos(cl[0], o)]
                return tuple(sorted([*reste, *self._marqueur(cl[0][2], cl[0][3]),
                                     (SEL_CLIC, frozenset(), cl[0][2], cl[0][3])], key=cle_objet)), False
        if self.glisse and (c, action) in self.moves:  # CCM-041-G : le sélectionné pousse une autre pièce → elle glisse
            g = self._glisser(reste, c, sx, sy, self.moves[(c, action)], taille)
            if g is not None:
                return tuple(sorted([*g, *self._marqueur(sx, sy), (SEL_CLIC, frozenset(), sx, sy)], key=cle_objet)), True
        figes = [(FIGE + c, o[1], o[2], o[3]) if o[0] == c and (o[2], o[3]) != (sx, sy) else o for o in reste]
        self._dans_sel_clic = True
        try:
            res, bouge = self.pas(tuple(sorted(figes, key=cle_objet)), action, taille, fixe, precedent)
        finally:
            self._dans_sel_clic = False
        apres = [o for o in res if o[0] == c]
        if len(apres) == 1:
            sx, sy = apres[0][2], apres[0][3]
        out = [(c, *o[1:]) if o[0] == FIGE + c else o for o in res]
        return tuple(sorted([*out, *self._marqueur(sx, sy), (SEL_CLIC, frozenset(), sx, sy)], key=cle_objet)), bouge

    def _glisser(self, objs, c, sx, sy, d, taille):
        """La pièce sélectionnée (sx, sy) avance de d sur une autre pièce de c : celle-ci glisse par pas de d, jusqu'à
        glisse[0] cases au plus, tant qu'elle reste dans la grille et ne recouvre que des classes traversées (glisse[1]) ;
        le contenu de son trou la suit ; le sélectionné ne bouge pas. → objets, ou None si pas de poussée."""
        dmax, trav = self.glisse[:2]
        par_classe = dict(self.glisse[3]) if len(self.glisse) > 3 else {}  # distance max par famille poussée
        poussees = {c} | set(self.glisse[2] if len(self.glisse) > 2 else ())  # pièces de c, et autres classes vues glisser
        s = next((o for o in objs if o[0] == c and (o[2], o[3]) == (sx, sy)), None)
        if s is None or d == (0, 0):
            return None
        devant = {(x + d[0], y + d[1]) for x, y in cells(s)}  # contact AUX CASES : un creux de la croix laisse entrer
        p = next((o for o in objs if o[0] in poussees and o is not s and cells(o) & devant), None)
        if p is None:
            return None
        fp = (p[0] - 512) % 16 if 512 <= p[0] < 1024 else p[0] % 16 if p[0] >= 16 else p[0]
        dmax = par_classe.get(fp, dmax)
        passagers = [o for o in objs if o is not p and o[0] < 1024 and _enclos(p, o)]
        autres = [o for o in objs if o is not p and o is not s and o not in passagers and o[0] < 1024]
        occ = {}
        for o in autres:
            for z in cells(o):
                occ.setdefault(z, set()).add(o[0])
        w, h = taille
        pas, k = abs(d[0]) + abs(d[1]), 0
        siennes = cells(p)  # fond solide (ka59) : chaque case d'arrivée doit être sur un objet traversé (ou sur elle-même)
        prolonge = self.glisse[4] if len(self.glisse) > 4 else frozenset()
        while True:
            if (k + 1) * pas > dmax:  # au-delà de la base : seulement tant qu'il chevauche une classe prolongeante (c15)
                ici = {c2 for x, y in cells(p) for c2 in occ.get((x + d[0] * k, y + d[1] * k), ())}
                if not (ici & prolonge) or (k + 1) * pas > 3 * dmax:
                    break
            cs = {(x + d[0] * (k + 1), y + d[1] * (k + 1)) for x, y in cells(p)}
            if any(not (0 <= x < w and 0 <= y < h) or occ.get((x, y), set()) - trav
                   or self.fond_solide and not occ.get((x, y)) and (x, y) not in siennes for x, y in cs):
                break
            k += 1
        if k == 0:
            return objs
        bouge = {id(o) for o in [p, *passagers]}
        return [(o[0], o[1], o[2] + d[0] * k, o[3] + d[1] * k) if id(o) in bouge else o for o in objs]

    def _marqueur(self, sx, sy):
        if not self.marqueur_sel:
            return []
        k, cs, dx, dy = self.marqueur_sel[:4]
        return [(k, cs, sx + dx, sy + dy)]

    def cle_sans_effet(self, monde, action, taille=None):
        """CW-355 : (action, positions des mobiles, CONTEXTE PERTINENT). Le contexte = objets non mobiles posés sur les
        cases d'arrivée prévues (une porte qui s'ouvre le change), plus l'état caché (sélection, trajet, phase…). S'il
        change, le coup redevient permis : pénalité contextuelle, pas interdiction par position."""
        mob = {c for c, _ in self.moves}
        pos = frozenset((o[0], o[2], o[3]) for o in monde if o[0] in mob)
        if taille is None:
            return action, pos, None
        garde, self.sans_effet = self.sans_effet, frozenset()
        try:
            pred, _ = self.pas(monde, action, taille)
        finally:
            self.sans_effet = garde
        dest = {z for o in pred if o[0] in mob for z in cells(o)} - {z for o in monde if o[0] in mob for z in cells(o)}
        ctx = frozenset((o[0], o[2], o[3], o[1]) for o in monde
                        if o[0] not in mob and (o[0] >= 1024 or cells(o) & dest))
        return action, pos, ctx

    def pas(self, monde, action, taille, fixe=None, precedent=None):
        if self.selection_clic and not getattr(self, "_dans_sel_clic", False):
            return self._pas_selection_clic(monde, action, taille, fixe, precedent)
        if self.sans_effet and not isinstance(action, tuple) and self.cle_sans_effet(monde, action, taille) in self.sans_effet:
            return monde, False  # C (CW-354.2, CHRYS_SANS_EFFET) : ce coup, d'ici, a été vu sans effet dans le vrai jeu
        if self.fantome and not isinstance(action, tuple):
            res = self._pas_fantome(monde, action, taille, fixe, precedent)
        else:
            res = self._pas_base(monde, action, taille, fixe, precedent)
        res = self._tenir(res) if self.tenue else res
        res = self._tenir_cases(res) if self.tenue_cases else res
        res = self._peindre(monde, res) if self.peint_contact else res
        # le compteur de jauge n'entre dans l'état que sur demande (CHRYS_JAUGE_ETAT=1) : sinon chaque coup crée un état
        # neuf, les états du planificateur ne fusionnent plus (CCM-249-B : −11 % de coups) ; la réserve est tenue par F
        # (`economie_plan.resserrer`, CCM-235-C) et par le programme exporté (etat « jauge »)
        return self._consommer(monde, res) if self.jauge and os.environ.get("CHRYS_JAUGE_ETAT") == "1" else res

    def _peindre(self, monde, res):
        """C (re86 N5, CHRYS_PEINT_CONTACT) : une pièce (plus d'une case) qui vient d'arriver sur un objet « palette » en
        prend la couleur et garde sa forme ; sa classe = l'hôte de cette couleur et de cette forme s'il existe, sinon une
        classe de forme neuve (496 + couleur, rendue dans la couleur)."""
        out, bouge = res
        avant = set(monde)
        pal = [p for p in out if (p[0], p[1]) in self.peint_contact and p in avant]
        neuf = []
        for o in out:
            if o in avant or len(o[1]) < 2 or o[0] >= 512 or (o[0], o[1]) in self.peint_contact:
                neuf.append(o)
                continue
            cs = cells(o)
            ks = {p[0] % 16 if p[0] >= 16 else p[0] for p in pal if cells(p) & _voisinage(cs)}  # contact (8 voisins)
            k0 = o[0] % 16 if o[0] >= 16 else o[0]
            if len(ks) != 1 or k0 in ks:
                neuf.append(o)
                continue
            k = ks.pop()
            c = next((c for c, f in self.hotes if f == o[1] and (c % 16 if c >= 16 else c) == k), None)
            neuf.append((c if c is not None else 496 + k if o[0] >= 256 else k, *o[1:]))
        return tuple(sorted(neuf, key=cle_objet)), bouge

    def _classes_hotes(self, monde):
        """Classes hôtes du porteur : celles apprises, plus toute classe d'un objet qui a la FORME d'un hôte (pièce repeinte
        par peint_contact)."""
        classes = {c for c, _ in self.hotes}
        if self.peint_contact:
            formes = {f for _, f in self.hotes}
            classes |= {o[0] for o in monde if o[0] < 1024 and o[1] in formes}
        return classes

    def _consommer(self, monde, res):
        """C (CW-333, re86 et g50t) : la jauge perd un coup par action ; compteur caché, initialisé à jauge[0] (réserve à
        l'image où la théorie est employée) quand le monde n'en porte pas encore. La défaite à 0 est lue par meurt()."""
        m, bouge = res
        avant = next((o[2] for o in monde if o[0] == MEM_JAUGE), self.jauge[0])
        out = tuple(sorted([o for o in m if o[0] != MEM_JAUGE] + [(MEM_JAUGE, frozenset(), avant - 1, 0)], key=cle_objet))
        return out, bouge

    def _tenir_cases(self, res):
        """C (g50t, CCM-021-G : la porte est une PARTIE de l'objet porte + fil, et elle pivote) : la classe p alterne entre
        deux configurations fixes de cases, fermée (B) et ouverte (O) : tant qu'un mobile occupe une case de S, les cases
        R = B − O sont retirées et A = O − B ajoutées ; sinon l'inverse. La classe p est redessinée d'un seul objet."""
        monde, bouge = res
        mob = {c for c, _ in self.moves} | set(self.poussables) | ({self.fantome[2]} if self.fantome else set())
        occ = {z for o in monde if o[0] in mob for z in cells(o)}
        out = list(monde)
        for p, r_cases, a_cases, s_cases in self.tenue_cases:
            ouverte = bool(occ & s_cases)
            ens = {z for o in out if o[0] == p for z in cells(o)}
            cible = (ens - r_cases) | a_cases if ouverte else (ens - a_cases) | r_cases
            if cible == ens or not cible:
                continue
            x0, y0 = min(x for x, _ in cible), min(y for _, y in cible)
            out = [o for o in out if o[0] != p] + [(p, frozenset((x - x0, y - y0) for x, y in cible), x0, y0)]
        # g50t (partie réelle du 21/10, GAME_OVER) : une porte qui se referme sur le joueur l'écrase → défaite (meurt)
        joueur = {z for o in out if o[0] in {c for c, _ in self.moves} for z in cells(o)}
        for p, cs in self.portes_cases:
            if cs & joueur & {z for o in out if o[0] == p for z in cells(o)}:
                out.append((ECRASE, frozenset(), 0, 0))
                break
        out = tuple(sorted(out, key=cle_objet))
        return out, bouge or out != monde

    def _tenir(self, res):
        """C (CHRYS_TENUE) : après les lois, chaque porte tenue est ouverte (classe OUVERT + p, ni dessinée ni bloquante)
        tant qu'un mobile (joueur, poussable, fantôme) occupe une case de sa dalle, refermée sinon."""
        monde, bouge = res
        mob = {c for c, _ in self.moves} | set(self.poussables) | ({self.fantome[2]} if self.fantome else set())
        occ = {z for o in monde if o[0] in mob for z in cells(o)}
        out = list(monde)
        for p, d in self.tenue:
            dalle = {z for o in monde if o[0] == d for z in cells(o)} or set(self._dalles.get(d, ()))
            if dalle:
                self._dalles[d] = frozenset(dalle)
            ouverte = bool(occ & dalle)
            out = [(OUVERT + p, *o[1:]) if ouverte and o[0] == p else (p, *o[1:]) if not ouverte and o[0] == OUVERT + p
                   else o for o in out]
        out = tuple(sorted(out, key=cle_objet))
        return out, bouge or out != monde

    def _pas_fantome(self, monde, action, taille, fixe, precedent):
        """C (g50t N1, CHRYS_FANTOME) : boucle temporelle. Chaque pas EFFECTIF du joueur s'ajoute au trajet (mémoire
        virtuelle) ; sous l'action de boucle, le joueur revient au départ (loi `retour`), les fantômes existants repartent
        du départ et un fantôme nouveau reçoit le trajet ; à chaque autre coup, chaque fantôme rejoue un pas de son chemin
        (puis reste). Les fantômes sont redessinés depuis (départ + somme des k premiers pas) : aucun appariement."""
        cj, boucle, cg, x0, y0 = self.fantome
        mem = [o for o in monde if o[0] == MEM_TRAJET]
        rec = _CHEMINS.get(mem[0][2], ()) if mem else ()
        fants = [(o[2], o[3]) for o in monde if o[0] == MEM_FANTOME]
        base = tuple(o for o in monde if o[0] not in (MEM_TRAJET, MEM_FANTOME))
        j0 = [o for o in base if o[0] == cj]
        res, _ = self._pas_base(base, action, taille, fixe, precedent)
        j1 = [o for o in res if o[0] == cj]
        forme = j0[0][1] if j0 else (j1[0][1] if j1 else frozenset({(0, 0)}))
        if action == boucle and rec:  # trajet vide : la boucle ne fait rien (g50t, films : SPACE sans pas → 1 image)
            plein = len(fants) >= 1  # emplacements pleins → tous s'effacent, sans nouveau fantôme ; sinon un fantôme
            fants = []               # reçoit le trajet (1 emplacement : le fantôme alterne d'une boucle à l'autre)
            if not plein:
                pid = hash(rec) & 0xFFFFFFFF
                _CHEMINS[pid] = rec
                fants.append((pid, 0))
            rec = ()
        elif action == boucle:
            pass
        else:
            d = (j1[0][2] - j0[0][2], j1[0][3] - j0[0][3]) if len(j0) == 1 and len(j1) == 1 else (0, 0)
            if d != (0, 0):  # un « tic » par pas EFFECTIF du joueur (g50t, films : coup bloqué → le fantôme ne bouge pas)
                rec = (*rec, d)
                fants = [(pid, min(k + 1, len(_CHEMINS.get(pid, ())))) for pid, k in fants]
        rid = hash(rec) & 0xFFFFFFFF
        _CHEMINS[rid] = rec
        dessin = []
        for pid, k in fants:
            pas_ = _CHEMINS.get(pid, ())[:k]
            dessin.append((cg, forme, x0 + sum(d[0] for d in pas_), y0 + sum(d[1] for d in pas_)))
        out = [o for o in res if not (o[0] == cg and o[1] == forme)] + dessin + [(MEM_TRAJET, frozenset(), rid, 0)]
        out += [(MEM_FANTOME, frozenset(), pid, k) for pid, k in fants]
        return tuple(sorted(out, key=cle_objet)), True

    def _pas_base(self, monde, action, taille, fixe=None, precedent=None):
        if self.selection and not isinstance(action, tuple):
            res = self._pas_selection(monde, action, taille, fixe, precedent)
        elif self.porteur and not isinstance(action, tuple):
            res = self._pas_porteur(monde, action, taille, fixe, precedent)
        else:
            res = self._pas(monde, action, taille, fixe, precedent)
        if self.retour and not isinstance(action, tuple):  # C (g50t N1, CHRYS_RETOUR) : retour à la position de départ
            cible = {c: (x, y) for c, a, x, y in self.retour if a == action}
            if cible:
                m2 = tuple(sorted(((o[0], o[1], *cible[o[0]]) if o[0] in cible else o for o in res[0]), key=cle_objet))
                return m2, res[1] or m2 != res[0]
        return res

    def _pas_porteur(self, monde, action, taille, fixe, precedent):
        """C (CCM-102-C, CHRYS_MARQUEUR) : marqueur de sélection. Sous l'action sélecteur, le marqueur saute au centre de
        l'hôte suivant (objets des classes hôtes, ordre (classe, y, x), cyclique) ; sous les autres actions, l'objet qui
        porte le marqueur le suit (même pas, s'il reste dans la grille)."""
        m, sel = self.porteur
        mk = [o for o in monde if o[0] == m]
        if len(mk) != 1:
            return self._pas(monde, action, taille, fixe, precedent)
        mk = mk[0]
        classes = self._classes_hotes(monde)
        portee = {c: min((len(f) for cc, f in self.hotes if cc == c), default=0) for c in classes}  # forme portée, à 80 %
        hotes = sorted((o for o in monde if o[0] in classes and o[0] != m and len(o[1]) >= 0.8 * portee[o[0]]),  # près (un
                       key=lambda o: (o[0], o[3], o[2]))  # hôte peut avoir fusionné avec un point de sa couleur)
        porte = porteuse(monde, mk, classes)
        if action == sel:
            autres = [o for o in hotes if o != porte]
            if porte is None or not autres:
                return monde, False
            if self.peint_sel and porte is not None:  # la pièce quittée tamponne sa couleur sur les cases qu'elle couvre
                sous = cells(porte)
                monde = tuple(sorted(((porte[0], *o[1:]) if len(o[1]) == 1 and o[0] in self.peint_sel
                                      and (o[2], o[3]) in sous else o for o in monde), key=cle_objet))
            if self.saut_sel:  # ordre et point d'arrivée APPRIS sur les sauts vus (forme → forme suivante, décalage)
                regle = {f0: (f1, d) for f0, f1, d in self.saut_sel}.get(porte[1])
                h2 = next((o for o in autres if regle and o[1] == regle[0]), None)
                if h2 is not None:
                    nm = (m, mk[1], h2[2] + regle[1][0], h2[3] + regle[1][1])
                    return tuple(sorted([o for o in monde if o != mk] + [nm], key=cle_objet)), True
            cle = cle_objet if self.ordre_sel == "classe" else (lambda o, k=self.ordre_sel: _centre(o)[::-1] if k == "yx" else _centre(o))
            autres = sorted(autres, key=cle)
            h2 = next((o for o in autres if cle(o) > cle(porte)), autres[0])  # suivant, cyclique
            xs, ys = [x for x, _ in h2[1]], [y for _, y in h2[1]]
            nm = (m, mk[1], h2[2] + (min(xs) + max(xs)) // 2, h2[3] + (min(ys) + max(ys)) // 2)
            return tuple(sorted([o for o in monde if o != mk] + [nm], key=cle_objet)), True
        res, bouge = self._pas(monde, action, taille, fixe, precedent)
        nmk = [o for o in res if o[0] == m]
        if porte is None or len(nmk) != 1 or (nmk[0][2], nmk[0][3]) == (mk[2], mk[3]):
            return res, bouge
        d = (nmk[0][2] - mk[2], nmk[0][3] - mk[3])  # l'hôte suit, même s'il sort en partie de la grille (re86)
        res = [o for o in res if o != porte] + [(porte[0], porte[1], porte[2] + d[0], porte[3] + d[1])]
        return tuple(sorted(res, key=cle_objet)), True

    def avec_selection(self, monde, actions):
        """Monde complété par l'objet virtuel de sélection à l'issue de `actions` (index initial + appuis du sélecteur)."""
        if not self.selection or any(o[0] == VIRTUEL for o in monde):
            return monde
        sel, classes, i0 = self.selection
        k = (i0 + sum(1 for a in actions if a == sel)) % len(classes)
        return tuple(sorted([*monde, (VIRTUEL, frozenset(), k, 0)], key=cle_objet))

    def _pas_selection(self, monde, action, taille, fixe, precedent):
        """C (re86 N2 ; CHRYS_SELECTION) : sélection CACHÉE. Sous le sélecteur, l'index passe à la classe suivante ;
        sous une autre action, seules les lois de la classe sélectionnée s'appliquent (les autres classes sélectionnables
        ne bougent pas)."""
        sel, classes, i0 = self.selection
        v = [o for o in monde if o[0] == VIRTUEL]
        k = v[0][2] if v else i0
        reste = tuple(o for o in monde if o[0] != VIRTUEL)
        if action == sel:
            return tuple(sorted([*reste, (VIRTUEL, frozenset(), (k + 1) % len(classes), 0)], key=cle_objet)), True
        gele = frozenset(c for i, c in enumerate(classes) if i != k)
        res, bouge = self._pas(reste, action, taille, fixe, precedent, gele=gele)
        return tuple(sorted([*res, (VIRTUEL, frozenset(), k, 0)], key=cle_objet)), bouge

    def _pas(self, monde, action, taille, fixe=None, precedent=None, gele=frozenset()):
        """Monde suivant ; `monde` est un tuple d'objets (couleur, forme, x, y). Renvoie (monde', a_bouge).
        Une table d'occupation case → objets évite les comparaisons objet contre objet (planification rapide).
        `fixe` (planification) : {case: couleurs} du décor statique, absent de `monde`.
        `precedent` : monde d'avant le coup précédent (seule l'action « annuler » s'en sert)."""
        if isinstance(action, tuple):
            return self.clic(monde, action[1], action[2]), False
        if action == self.annule and action is not None:
            return (precedent if precedent is not None else monde), False
        w, h = taille
        objs = list(monde)
        occ = {}
        for k, o in enumerate(objs):
            for c in cells(o):
                occ.setdefault(c, set()).add(k)

        hj = self.hors_jeu

        def dans(cs):
            return all(0 <= x < w and 0 <= y < h and (y, x) not in hj for x, y in cs)

        def sur(cs, sauf):
            return {k for c in cs for k in occ.get(c, ()) if k not in sauf}

        vide = frozenset()

        def decor(cs, couleurs):
            return fixe is not None and any(fixe.get(c, vide) & couleurs for c in cs)

        bouges = set()

        def deplacer(k, v):
            bouges.add(k)
            o = objs[k]
            for c in cells(o):
                occ[c].discard(k)
            objs[k] = (o[0], o[1], o[2] + v[0], o[3] + v[1])
            for c in cells(objs[k]):
                occ.setdefault(c, set()).add(k)

        bloquants = self.solides | self.poussables
        bouge = False

        def libre_vers(i, v):
            """Le pas v de l'objet i est-il possible sans pousser (grille, décor, fond solide, objets solides) ?"""
            cible = cells(objs[i], *v)
            if objs[i][0] in self.debordent:  # peut sortir en partie de la grille (re86) : il en reste au moins une case
                cible = {(x, y) for x, y in cible if 0 <= x < w and 0 <= y < h}
                if not cible:
                    return False
            if not dans(cible) or decor(cible, self.solides):
                return False
            if self.fond_solide and any(not (occ.get(c, set()) - {i}) and not (fixe and c in fixe) for c in cible):
                return False
            for p, cs in self.portes_cases:  # g50t : seules les cases de PORTE de la classe bloquent (pas le fil, la dalle)
                if objs[i][0] != p and any(objs[j][0] == p for c in cible & cs for j in occ.get(c, ())):
                    return False
            return not any(objs[j][0] in self.solides for j in sur(cible, {i}) if objs[j][0] != objs[i][0])

        for i in range(len(objs)):
            o = objs[i]
            v = self.moves.get((o[0], action)) if o[0] not in gele else None
            if not v:
                continue
            if o[0] in self.enroule:  # tr87 : au-delà de l'intervalle, la classe revient à l'autre bout (enroulement)
                axe, mini, maxi = self.enroule[o[0]]
                p = o[2 + axe] + v[axe]
                if p > maxi or p < mini:
                    d = (mini if p > maxi else maxi) - o[2 + axe]
                    v = (d, 0) if axe == 0 else (0, d)
            ok = libre_vers(i, v)
            pousses = []
            if ok:
                cible = cells(o, *v)
                pousses = [j for j in sur(cible, {i}) if objs[j][0] != o[0] and objs[j][0] in self.poussables]
                for j in pousses:
                    cj = cells(objs[j], *v)
                    if not dans(cj) or decor(cj, bloquants) or any(objs[k][0] in bloquants for k in sur(cj, {i, j})):
                        ok = False
            if not ok:
                v2 = self.saut.get((o[0], action))  # saut : pas normal bloqué, case à 2·V libre
                if v2 and libre_vers(i, v2):
                    deplacer(i, v2)
                    bouge = True
                continue
            for j in pousses:
                deplacer(j, v)
            sous = {objs[q][0] for q in sur(cells(o, *v), {i})} | ({c for p in cells(o, *v) for c in fixe.get(p, ())}
                                                                    if fixe else set())
            d = next((self.teleports[k] for k in sous if k in self.teleports), None) or self.teleports_cases.get(
                (o[2] + v[0], o[3] + v[1]))
            deplacer(i, (v[0] + d[0], v[1] + d[1]) if d else v)  # téléportation : on arrive décalé de D
            bouge = True
        avant_tr = {c for c, *_ in objs}  # classes présentes avant transformation (pour les liens, CCM-083-C)
        # transformation par modificateur : un objet qui a bougé atterrit sur un objet de classe M
        if self.transforme and bouges:
            arrivee = {c for k in bouges for c in cells(objs[k])}
            sur = {o[0] for k, o in enumerate(objs) if k not in bouges and cells(o) & arrivee}
            if fixe:
                sur |= {c for p in arrivee for c in fixe.get(p, ())}
            regles = {c: c2 for m, c, c2 in self.transforme if m in sur}
            soi = {c for m, c, _ in self.transforme if m == c and m in sur}  # l'objet sur lequel on se pose change sur
            objs = [(regles[o[0]], o[1] if o[0] in soi else self.formes.get(regles[o[0]], o[1]), o[2], o[3])  # place,
                    if o[0] in regles else o for o in objs]  # même forme (interrupteur pressé)
        # consommation, puis liens (une couleur déclencheuse épuisée retire la couleur liée)
        if self.consomme or self.lie:
            avant = {c for c, *_ in objs} | avant_tr
            retires = set()
            for cm, cr in self.consomme:
                cm_cells = {c for o in objs if o[0] == cm for c in cells(o)}
                retires |= {k for k, o in enumerate(objs) if o[0] == cr and cells(o) & cm_cells}
            objs = [o for k, o in enumerate(objs) if k not in retires]
            reste = {c for c, *_ in objs}
            objs = [o for o in objs if not any(o[0] == cd and ct in avant and ct not in reste for cd, ct in self.lie)]
        # agents autonomes : un pas glouton vers la couleur poursuivie, seulement si le joueur a bougé
        if bouge and self.autonomes:
            for i, o in enumerate(objs):
                cp = self.autonomes.get(o[0])
                if cp is None:
                    continue
                cibles = [p for p in objs if p[0] == cp]
                if not cibles:
                    continue
                p = cibles[0]
                meilleur, d0 = o, abs(o[2] - p[2]) + abs(o[3] - p[3])
                for dx, dy in ORDRE_POURSUITE:
                    q = (o[0], o[1], o[2] + dx, o[3] + dy)
                    cq = cells(q)
                    if not dans(cq) or decor(cq, bloquants) or any(objs[k][0] in bloquants for k in range(len(objs))
                                           if k != i and cells(objs[k]) & cq):
                        continue
                    d = abs(q[2] - p[2]) + abs(q[3] - p[3])
                    if d < d0:
                        meilleur, d0 = q, d
                objs[i] = meilleur
        return tuple(sorted(self.deriver(objs, taille), key=cle_objet)), bouge

    def deriver(self, objs, taille):
        """Objets dérivés (vocabulaire : rotation/miroir), recalculés après chaque coup :
        miroir D = source ∪ reflet(source) (un seul objet) ; reflet D = reflet(classes mobiles) − cases occupées."""
        if not self.derives:
            return objs
        objs = list(objs)
        for d, v in self.derives.items():
            if isinstance(d, tuple):
                continue
            src, sens, a2 = v
            for k, o in enumerate(objs):
                if o[0] != d:
                    continue
                s_cells = {c for p in objs if p[0] == src for c in cells(p)}
                tout = s_cells | reflet(s_cells, sens, a2, taille)
                if tout:
                    objs[k] = (o[0], frozenset((x - o[2], y - o[3]) for x, y in tout), o[2], o[3])
        for d, v in self.derives.items():
            if not isinstance(d, tuple):
                continue
            classe, (src, sens, a2, atom) = d[1], v
            s_cells = {c for p in objs if p[0] in src for c in cells(p)}
            autres = {c for p in objs if p[0] not in src and p[0] != classe for c in cells(p)}
            cs = reflet(s_cells, sens, a2, taille) - autres
            objs = [p for p in objs if p[0] != classe]
            if atom:
                objs += [(classe, frozenset({(0, 0)}), x, y) for x, y in cs]
            else:
                objs += [o for o in _composantes(classe, cs)]
        return objs

    def clic(self, monde, x, y):
        objs = list(monde)
        cl = [o for o in objs if (x, y) in cells(o)]
        if self.clic_configs and cl:  # C (dc22 N3, CHRYS_CLIC_CONFIG) : bouton → bascule de configuration
            neuf = self._clic_config(monde, cl[0])
            if neuf is not None:
                return neuf
        par_forme = dict(self.motif_formes)
        if cl and cl[0][1] in par_forme:  # C (ft09 N5, CHRYS_MOTIF_FORME) : le voisinage dépend de la forme cliquée
            o, dec = cl[0], par_forme[cl[0][1]]
            c2 = _centre2(o)
            for k, j in enumerate(objs):
                cj = _centre2(j)
                if j[0] in self.bascule and (cj[0] - c2[0], cj[1] - c2[1], j[1]) in dec:
                    objs[k] = (self.bascule[j[0]], j[1], j[2], j[3])
            return tuple(sorted(objs, key=cle_objet))
        if not cl or not self.motif:
            return monde
        o = cl[0]
        if self.formes_bascule and o[1] not in self.formes_bascule:  # forme jamais vue basculer (interface) : sans effet
            return monde
        if self.zone is not None:
            bo = _boite(o)
            if not any(z[0] == self.zone and len(z[1]) > len(o[1]) and _contient(_boite(z), bo) for z in objs):
                return monde
        touches = set()
        for k, j in enumerate(objs):
            if j[1] == o[1] and (j[2] - o[2], j[3] - o[3]) in self.motif and j[0] in self.bascule:
                objs[k] = (self.bascule[j[0]], j[1], j[2], j[3])
                touches.add(k)
        ctrl = {c for c, _ in self.moves}  # « contrôlé » = couleur qui a des règles de flèches
        if self.exclusif and any(objs[k][0] in ctrl for k in touches):  # le clic vient de SÉLECTIONNER un objet
            for k, j in enumerate(objs):
                if k not in touches and j[0] in ctrl and j[0] in self.desel:
                    objs[k] = (self.desel[j[0]], j[1], j[2], j[3])
        return tuple(sorted(objs, key=cle_objet))

    def _clic_config(self, monde, bouton):
        """Première règle du bouton applicable : « avant » présent en entier (ou « après », sens inverse), aucun mobile
        sur les cases touchées, cible absente. Échange : les objets d'une case posés en P et en Q changent de place."""
        ens = set(monde)
        mob = {c for c, _ in self.moves}
        occ = {z for o in monde if o[0] in mob for z in cells(o)}
        for r in self.clic_configs:
            if r[0] != bouton:
                continue
            if r[1] == "echange":
                p, q = r[2], r[3]
                en_p = [o for o in monde if len(o[1]) == 1 and (o[2], o[3]) == p]
                en_q = [o for o in monde if len(o[1]) == 1 and (o[2], o[3]) == q]
                if not en_p or not en_q:
                    continue
                autres = [o for o in monde if o not in en_p and o not in en_q]
                out = autres + [(o[0], o[1], *q) for o in en_p] + [(o[0], o[1], *p) for o in en_q]
                return tuple(sorted(out, key=cle_objet))
            for av, ap in ((r[1], r[2]), (r[2], r[1])):
                if av <= ens and not (ap & ens) and not (occ & {z for o in av | ap for z in cells(o)}):
                    return tuple(sorted((ens - av) | ap, key=cle_objet))
        return None

    def meurt(self, monde):
        if self.jauge and any(o[0] == MEM_JAUGE and o[2] <= 0 for o in monde):
            return True
        if any(o[0] == ECRASE for o in monde):
            return True
        return bool(self.mort) and self._vrai(self.mort, monde)

    def atteint(self, monde):
        return bool(self.but) and self._vrai(self.but, monde)

    @staticmethod
    def _vrai(cond, monde):
        if cond[0] == "present":  # sous-but de la régression : un objet de la classe obtenue existe
            return any(o[0] == cond[1] for o in monde)
        if cond[0] == "sortie_si":  # but conditionnel : sortie atteinte ET un objet de la classe requise existe
            _, a, b, k = cond
            return Theorie._vrai(("sortie", a, b), monde) and any(o[0] == k for o in monde)
        if cond[0] == "emboite" and len(cond) > 3:  # CCM-044-G : cible-moule → n'accepte que la classe de son objet
            _, a, b, exige = cond
            ex = dict(exige)
            pieces = [o for o in monde if o[0] in b]
            c2 = [(o[0], bx[0] + bx[2], bx[1] + bx[3]) for o, bx in ((o, _boite(o)) for o in pieces)]
            moules = set(ex.values())  # une classe qui a son moule ne remplit pas une autre cible
            return bool(a) and all(any(max(abs(px - cx), abs(py - cy)) <= 2 for k, px, py in c2
                                       if (k == ex[(cx, cy)] if (cx, cy) in ex else k not in moules)) for cx, cy in a)
        kind, a, b = cond
        if kind == "emboite":  # E (CCM-054/055-E), CHRYS_BUT_EMBOITE : chaque cible creuse (centre 2× fixe, lu au départ)
            pieces = [o for o in monde if o[0] in b]             # porte en son centre (à 1 case près) le centre d'une pièce
            c2s = [(bx[0] + bx[2], bx[1] + bx[3]) for bx in (_boite(o) for o in pieces)]
            return bool(a) and all(any(max(abs(px - cx), abs(py - cy)) <= 2 for px, py in c2s) for cx, cy in a)
        if kind == "centre":  # E (CCM-042-E), CHRYS_BUT_CENTRE : centre de la boîte d'un a (≥ 3 cases) à ≤ 1 case d'un b
            petits = [o for o in monde if o[0] == b and len(o[1]) <= 2]  # (≤ 2 cases) distinct ; g50t : point de sortie
            for o in monde:
                if o[0] != a or len(o[1]) < 3:
                    continue
                bx = _boite(o)
                cx2, cy2 = bx[0] + bx[2], bx[1] + bx[3]  # 2 × centre
                if any(p is not o and any(max(abs(2 * x - cx2), abs(2 * y - cy2)) <= 2 for x, y in cells(p)) for p in petits):
                    return True
            return False
        if kind == "modele":
            # Modèle visible : égalité de silhouettes à translation près, palette libre.
            def silhouette(c):
                ps = {p for o in monde if o[0] == c for p in cells(o)}
                if not ps: return None
                x0, y0 = min(x for x,y in ps), min(y for x,y in ps)
                return frozenset((x-x0,y-y0) for x,y in ps)
            ref = silhouette(b)
            return ref is not None and silhouette(a) == ref
        if kind == "motif_rel":
            return motif_relatif(monde, a, b)
        if kind == "marques":
            return marques_manquantes(monde, a, b == "couleur") == 0
        if kind == "copie":
            return copie_ecarts(monde, a) == 0
        if kind == "paires":
            return all(Theorie._vrai(("remplir_fam", fam, c), monde) for fam, c in a)
        if kind == "remplir_fam":
            ca = set().union(*[cells(o) for o in monde if o[0] in a]) if any(o[0] in a for o in monde) else set()
            bs = [o for o in monde if o[0] == b]
            return bool(bs) and all(cells(o) <= ca for o in bs)
        if kind == "ancre":  # superpose (vocabulaire) : un objet a calé sur le coin haut-gauche d'un objet b
            ancres = {(o[2], o[3]) for o in monde if o[0] == b}
            return any((o[2], o[3]) in ancres for o in monde if o[0] == a)
        if kind == "absent":
            return not any(o[0] == a for o in monde)
        ca = set().union(*[cells(o) for o in monde if o[0] == a]) if any(o[0] == a for o in monde) else set()
        bs = [o for o in monde if o[0] == b]
        if kind in ("sortie", "contact"):
            return any(cells(o) & ca for o in bs)
        return bool(bs) and all(cells(o) <= ca for o in bs)

    def rendu(self, monde, taille, fond):
        w, h = taille
        g = np.full((h, w), fond, dtype=int)
        couche = self.couches()
        porte = set()
        if self.porteur:  # re86 : la pièce qui porte le marqueur est dessinée au-dessus des autres hôtes (CCM-245-A)
            mk = {(o[2], o[3]) for o in monde if o[0] == self.porteur[0]}
            classes = self._classes_hotes(monde)
            porte = {i for i, o in enumerate(monde) if o[0] in classes and cells(o) & mk}
        for _, o in sorted(enumerate(monde), key=lambda io: (couche(io[1][0]), io[0] in porte)):
            if o[0] >= OUVERT:  # porte tenue ouverte : pas dessinée
                continue
            for x, y in cells(o):
                if 0 <= x < w and 0 <= y < h:
                    g[y, x] = o[0] % 16 if o[0] >= 16 else o[0]  # détail reclassé (faits.details) : sa vraie couleur
        return g


VOISINS8 = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx, dy) != (0, 0)]


def centres_motifs(col, marques):
    """Cases isolées (couleur hors `marques`) entourées de 8 cases de marques : centres de cibles (ft09, CW-228)."""
    return [z for z, k in col.items() if k not in marques
            and all(col.get((z[0] + dx, z[1] + dy)) in marques for dx, dy in VOISINS8)]


def _sous_clic(o, x, y):
    """Le clic (x, y) tombe sur l'objet o : sur une de ses cases, ou dans un trou qu'il enclot (ka59 sous CREUX : le pixel
    du trou d'une pièce reste un objet à part, CCM-067-D ; le clic au centre de la pièce la désigne)."""
    cs = cells(o)
    if (x, y) in cs:
        return True
    xs, ys = [a for a, _ in cs], [b for _, b in cs]
    if not (min(xs) < x < max(xs) and min(ys) < y < max(ys)) or len(cs) < 8:
        return False
    vu, pile = {(x, y)}, [(x, y)]  # remplissage depuis le clic : enclos s'il n'atteint pas le bord de la boîte
    while pile:
        a, b = pile.pop()
        for na, nb in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
            if (na, nb) in vu or (na, nb) in cs:
                continue
            if not (min(xs) <= na <= max(xs) and min(ys) <= nb <= max(ys)):
                return False
            vu.add((na, nb))
            pile.append((na, nb))
    return True


def _voisinage(cs):
    """Cases de cs et leurs 8 voisines (contact)."""
    return {(x + dx, y + dy) for x, y in cs for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


def _enclos(hote, o):
    """o est entièrement dans un trou qu'enclot hote (aucune de ses cases sur l'hôte)."""
    ch = cells(hote)
    return all((x, y) not in ch and _sous_clic(hote, x, y) for x, y in cells(o))


def _sans_marqueur(objs, c, k):
    """Retire les objets de la couleur du marqueur k enclos dans un hôte de la famille c (c, FIGE + c, jumeaux 512 + c)."""
    fam = lambda v: (v - 512) % 16 if 512 <= v < 1024 else v % 16 if v >= 16 else v
    hotes = [o for o in objs if o[0] in (c, FIGE + c) or fam(o[0]) == fam(c) and o[0] < 1024]
    return [o for o in objs if not (o[0] < 1024 and fam(o[0]) == fam(k) and any(_enclos(h, o) for h in hotes if h is not o))]


def marques_manquantes(monde, groupes, couleur=False):
    """But `marques` (C, re86 ; CCM-102-C) : groupes = ((couleur, cases), …), marques d'une case relevées au DÉBUT du
    niveau ; chacune doit être recouverte par une pièce (objet de plus d'une case, hors marqueur), quelle qu'elle soit
    (re86 N1 : la croix 11 couvre aussi une marque 4). `couleur` (CCM-059-E, « paires colorées ») : la pièce doit avoir
    la COULEUR de la marque. → nombre de marques non couvertes (0 = but ; distance A*)."""
    couvert = {}
    for o in monde:
        if len(o[1]) > 1 and o[0] < 512:
            for c in cells(o):
                couvert.setdefault(c, set()).add(o[0] % 16 if o[0] >= 16 else o[0])
    return sum(1 for k, cs in groupes for c in cs if c not in couvert or couleur and k >= 0 and k not in couvert[c])


def copie_ecarts(monde, groupes):
    """But `copie` (C, CCM-140-C) : groupes = ((couleur, cases), …) ; nombre de cases qui ne montrent pas encore la couleur
    du modèle (objet du dessus, comme au rendu : le dernier de la liste)."""
    col = {}
    for o in monde:
        for c in cells(o):
            col[c] = o[0]
    return sum(1 for k, cs in groupes for c in cs if col.get(c) != k)


def motif_ecarts(monde, meme, autre):
    """Nombre de contraintes de `motif_rel` non satisfaites (distance A* ; None sans cible)."""
    col = {}
    for o in monde:
        for c in cells(o):
            col[c] = o[0]
    zs = centres_motifs(col, {meme, autre})
    if not zs:
        return None
    n = 0
    for z in zs:
        for dx, dy in VOISINS8:
            m, q = col[(z[0] + dx, z[1] + dy)], col.get((z[0] + 4 * dx, z[1] + 4 * dy))
            n += q is None or (q == col[z]) != (m == meme)
    return n


def motif_relatif(monde, meme, autre):
    """But `motif_rel(meme, autre)` (CW-228, ft09 ; B : CCM-138-B) : chaque cible = une case centre entourée de 8 marques ;
    la marque en (dx, dy) désigne la case à (dx, dy)·P du centre (P = côté du motif + 1 = 4, pas des tuiles) ; marque
    `meme` → cette case a la couleur du centre, marque `autre` → une autre couleur. Faux sans cible."""
    col = {}
    for o in monde:
        for c in cells(o):
            col[c] = o[0]
    zs = centres_motifs(col, {meme, autre})
    if not zs:
        return False
    for z in zs:
        k = col[z]
        for dx, dy in VOISINS8:
            m, q = col[(z[0] + dx, z[1] + dy)], col.get((z[0] + 4 * dx, z[1] + 4 * dy))
            if q is None or (q == k) != (m == meme):
                return False
    return True


def monde_final(th, tr):
    """Monde après la dernière transition, rejoué librement (garde les objets cachés) si ce rejeu finit exact ;
    sinon le dernier état observé."""
    monde = tr.etats[0]
    for a in tr.actions:
        monde, _ = th.pas(monde, a, tr.taille)
    if egal(th.rendu(monde, tr.taille, tr.fond), tr.cases[-1], tr.exclues):
        return monde
    return etat_complet(tr.etats)


def etat_complet(etats):
    """Dernier état + objets CACHÉS (complétion amodale au niveau objets) : un objet disparu alors que ses cases venaient
    d'être couvertes par un objet ARRIVÉ à ce coup, et dont la place est toujours couverte, est remis (une cible sous une
    caisse posée ; pas un joueur transformé, que le décor déjà là « couvre »)."""
    dernier = list(etats[-1])
    occ = {c for o in dernier for c in cells(o)}
    vus = set(dernier)
    caches = {}
    for e0, e1 in pairwise(etats):
        avant = set(e0)
        couv1 = {c for o in e1 if o not in avant for c in cells(o)}  # couvert par un objet qui VIENT d'arriver
        for o in e0:
            if o not in e1 and cells(o) <= couv1:
                caches[o] = True
            elif o in e1:
                caches.pop(o, None)
    for o in caches:
        if o not in vus and cells(o) <= occ:
            dernier.append(o)
    return tuple(sorted(dernier, key=cle_objet))


def _composantes(classe, cs):
    """Composantes 4-connexes d'un ensemble de cases, en objets (classe, forme, x, y)."""
    reste, out = set(cs), []
    while reste:
        pile, comp = [reste.pop()], []
        while pile:
            x, y = pile.pop()
            comp.append((x, y))
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q in reste:
                    reste.remove(q)
                    pile.append(q)
        x0, y0 = min(x for x, _ in comp), min(y for _, y in comp)
        out.append((classe, frozenset((x - x0, y - y0) for x, y in comp), x0, y0))
    return out


def reflet(cs, sens, a2, taille):
    """Reflet de l'ensemble de cases `cs` par l'axe x = a2/2 (sens 'x'), y = a2/2 ('y'), ou les deux ('xy'), dans la grille."""
    w, h = taille
    if sens == "x":
        r = {(a2 - x, y) for x, y in cs}
    elif sens == "y":
        r = {(x, a2 - y) for x, y in cs}
    else:
        r = {(a2 - x, a2 - y) for x, y in cs}
    return {(x, y) for x, y in r if 0 <= x < w and 0 <= y < h}


def _centre(o):
    """Centre (x, y) de la boîte d'un objet."""
    b = _boite(o)
    return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2


def _centre2(o):
    """Deux fois le centre de la boîte (entier : centres de boîtes de tailles différentes comparables)."""
    b = _boite(o)
    return b[0] + b[2], b[1] + b[3]


def porteuse(monde, mk, classes=None):
    """Pièce qui porte le marqueur `mk` : celle qui couvre sa case ; C (re86 N5, CHRYS_PORTEUR_BOITE=1) : sinon, la pièce
    CREUSE (plus d'une case) dont la boîte contient le marqueur (marqueur posé au centre vide), la plus petite boîte."""
    import os
    m, c = mk[0], (mk[2], mk[3])
    ok = [o for o in monde if o[0] != m and (classes is None or o[0] in classes)]
    p = next((o for o in ok if c in cells(o)), None)
    if p is not None or os.environ.get("CHRYS_PORTEUR_BOITE") != "1":
        return p
    boites = [(o, _boite(o)) for o in ok if len(o[1]) > 1]
    dedans = [(o, b) for o, b in boites if b[0] <= c[0] <= b[2] and b[1] <= c[1] <= b[3]]
    return min(dedans, key=lambda ob: (ob[1][2] - ob[1][0]) * (ob[1][3] - ob[1][1]))[0] if dedans else None


def _boite(o):
    cs = cells(o)
    return min(x for x, _ in cs), min(y for _, y in cs), max(x for x, _ in cs), max(y for _, y in cs)


def _contient(b, c):
    return b[0] <= c[0] and b[1] <= c[1] and c[2] <= b[2] and c[3] <= b[3]


def egal(g_pred, g_obs, exclues):
    m = g_pred != np.asarray(g_obs)
    return not any(not ((r, c) in exclues) for r, c in zip(*np.nonzero(m), strict=True))


def rejeu(theo, traj, debut=0, fin=None, libre=True):
    """Rejeu exact au niveau cases sur les transitions [debut, fin). libre=True : le monde prédit n'est jamais recalé sur
    l'observation (le plus strict, garde les objets cachés) ; sinon recalé à chaque pas. Renvoie (exactes, total, 1er écart)."""
    fin = len(traj.actions) if fin is None else fin
    monde, ok, premier = traj.etats[debut], 0, None
    for t in range(debut, fin):
        if not libre:
            monde = traj.etats[t]
        monde, _ = theo.pas(monde, traj.actions[t], traj.taille)
        if egal(theo.rendu(monde, traj.taille, traj.fond), traj.cases[t + 1], traj.exclues):
            ok += 1
        elif premier is None:
            premier = t
    return ok, fin - debut, premier
