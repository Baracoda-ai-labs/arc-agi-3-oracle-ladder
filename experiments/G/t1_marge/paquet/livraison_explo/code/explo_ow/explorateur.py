"""Explorateur « à la OPINE-World », déterministe, sans LLM — remplaçant de agent_p1.generique.Explorateur.

Même interface : Explorateur(lab, journal, memoire, graine).jouer(budget) → 'victoire' | 'budget' ; attribut .aretes.

À chaque pas :
 1. le tableau des interactions (objet/type, action, contexte) est mis à jour avec l'effet observé ;
 2. on énumère les expériences possibles depuis l'état courant et depuis les états connus atteignables (style
    Go-Explore, par le graphe observé ou par le modèle de grille appris) :
      (a) interaction jamais essayée, (b) interaction aux effets incohérents, (c) plan vers un but candidat
      (pousser une pièce sur une cible, atteindre une tuile rare, rapprocher un mobile d'un partenaire de même forme,
      faire ressembler une toile à un modèle) ;
    chacune est notée utilité / (coût pour atteindre + coût pour tester) ; un petit budget reste réservé à l'inconnu ;
 3. un but candidat n'est abandonné que s'il est réfuté (atteint sans victoire) ;
 4. RESET seulement après une défaite ou un blocage avéré (aucune expérience utile atteignable), au plus 2 par niveau.
La jauge et les compteurs sont masqués dans la clé d'état ; une expérience dont le coût dépasserait la réserve
estimée n'est pas choisie.
"""
import hashlib, random
from collections import deque, Counter
import numpy as np

from .buts import Buts
from .perception import objets, types_au_pixel
from .table import Table, U_JAMAIS
from .grille import Grille, DIR, bfs_cases, chemin, sokoban

CLAVIER = (1, 2, 3, 4, 5, 7)
MAX_CLICS = 48
PAR_JEU = {}          # jeu -> connaissances conservées d'un niveau à l'autre (table, grille)
U_BUT = 0.9
INCONNU_TOUS = 12     # une décision sur 12 réservée à l'inconnu (si aucune expérience forte n'est en vue)
MAX_RESET_BLOCAGE = 8


def sig_court(t):
    return hashlib.sha1(repr(t).encode()).hexdigest()[:8]


def type_action(a, im=None):
    if isinstance(a, tuple):
        c = int(im[a[2], a[1]]) if im is not None else -1
        return f'clic:c{c}'
    return f'k{a}'


class ExplorateurOW:
    def __init__(self, lab, journal, memoire=None, graine=0):
        from agent_p1.generique import Memoire
        self.lab = lab; self.j = journal; self.mem = memoire or Memoire(); self.rng = random.Random(graine)
        cj = PAR_JEU.setdefault(getattr(lab, 'game', '?'), dict(table=Table(), prior=Table(), grille=Grille(),
                                                                 refutes=set(), niveau=None))
        if cj['niveau'] != (id(lab), getattr(lab, 'level', 0)):
            # nouveau niveau : le tableau du niveau précédent devient un a priori (on re-teste à bas coût les touches
            # et objets, car un niveau peut ajouter un contexte : sélection, deuxième pièce...)
            cj['prior'].fusionner(cj['table']); cj['table'] = Table(); cj['niveau'] = (id(lab), getattr(lab, 'level', 0))
            cj['refutes'] = set()
        self.table = cj['table']; self.prior = cj['prior']; self.g = cj['grille']; self.refutes = cj['refutes']
        self.g.pos = None
        self.compteurs = set(); self.aretes = {}; self.supposees = {}; self.cands = {}; self.imgs = {}
        self.objs = {}; self.valeur = {}; self.scores = {}; self.buts = Buts(lab.image); self.deltas = {}
        self.ctx = '-'; self.plan = []; self.plan_info = None; self.n_choix = 0
        self.resets_blocage = 0; self.dernier_nouveau = 0; self.compose = {}
        self.stats = Counter(); self.tabou = Counter()
        eco = getattr(lab, 'economy', None)
        self.ligne_jauge = getattr(eco, 'y', None) if getattr(eco, 'valid', False) else None
        if self.g.gab is not None:
            self.g.pos = self.g.localiser(lab.image, None)
        self.k_init = self.cle(lab.image)

    # ================================================================ perception d'état
    def masque(self, im):
        m = im.copy()
        m[0, :] = m[-1, :] = 0; m[:, 0] = m[:, -1] = 0
        if self.ligne_jauge is not None:
            m[self.ligne_jauge, :] = 0
        for (x, y) in self.compteurs:
            m[y, x] = 0
        return m

    def cle(self, im):
        return hashlib.sha1(self.masque(im).tobytes()).hexdigest()[:16]

    def lignes_masquees(self):
        s = {0, 63}
        if self.ligne_jauge is not None:
            s.add(self.ligne_jauge)
        s |= {y for x, y in self.compteurs}
        return s

    def objets_etat(self, k, im):
        if k not in self.objs:
            self.objs[k] = objets(im)
        return self.objs[k]

    def candidats(self, k, im):
        dispo = self.lab.actions_disponibles or list(range(1, 8))
        out = [a for a in CLAVIER if a in dispo]
        if 6 in dispo:
            obs = sorted(self.objets_etat(k, im), key=lambda o: (o['bord'], o['n'] > 400, o['abs'] != 'A1', o['n']))
            vus = set()
            for o in obs:
                p = (o['x'], o['y'])
                if p in vus:
                    continue
                vus.add(p); out.append(('clic', o['x'], o['y']))
                if len(out) >= MAX_CLICS + 6:
                    break
        return out

    # ================================================================ clés du tableau des interactions
    def cles_action(self, a, k, im, ctx):
        """Clés de la plus spécifique à la plus générale, par abstraction concurrente."""
        if isinstance(a, tuple):
            ts = types_au_pixel(im, a[1], a[2], self.objets_etat(k, im)) or [('pixel', int(im[a[2], a[1]]))]
            col = ('col', int(im[a[2], a[1]]))
            return [[(t, 'clic', ctx), (t, 'clic'), (col, 'clic')] for t in ts]
        return [[(('k', a), ctx), (('k', a),)]]

    def utilite_avec_prior(self, chaine, clic, grille=False, u_gen=0.25):
        r = self.table.utilite(chaine, rien=('rien', 'bloque'), u_gen=u_gen)
        if r[1] != 'a_jamais' or not len(self.prior):
            return r
        rp = self.prior.utilite(chaine, rien=('rien', 'bloque'), u_gen=u_gen)
        if rp[1] == 'a_jamais':
            return r
        if rp[1] == 'predit_mort' or grille:
            return rp                                   # la mort et la physique des tuiles se transfèrent
        if clic:
            return (0.25 * (0.3 if rp[2] in ('rien', 'bloque') else 1.0), 'a_generalise_niveau', rp[2])
        return (0.5 if rp[2] in ('rien', 'bloque') else 0.6, 'a_nouveau_niveau', rp[2])

    def utilite_action(self, a, k, im, ctx):
        chaines = self.cles_action(a, k, im, ctx)
        res = [self.utilite_avec_prior(c, isinstance(a, tuple)) for c in chaines]
        # abstraction qui explique de façon cohérente → on lui fait confiance (ARGA : concurrence des abstractions)
        coh = [r for r, c in zip(res, chaines) if self.table.statut(c[-1])[0] == 'coherent']
        if coh:
            return min(coh, key=lambda r: r[0])
        return max(res, key=lambda r: r[0])

    def signature(self, im0, im1, a, mort):
        if mort:
            return 'mort'
        d = self.masque(im0) != self.masque(im1)
        n = int(d.sum())
        if n == 0:
            return 'rien'
        b = 'p' if n <= 4 else 'm' if n <= 20 else 'g' if n <= 120 else 'G'
        paires = Counter(zip(im0[d].tolist(), im1[d].tolist())).most_common(3)
        loc = ''
        if isinstance(a, tuple):
            x, y = a[1], a[2]
            loc = 'L' if d[max(0, y - 2):y + 3, max(0, x - 2):x + 3].any() else 'D'
        return f'{b}{loc}:' + ','.join(f'{p}>{q}' for (p, q), _ in sorted(paires))

    # ================================================================ grille
    def grille_ok(self):
        """Le modèle de grille n'est utilisé que s'il prédit bien : sinon (monde non « contrôlé sur grille »),
        retour au graphe d'états."""
        if not (self.g.pret() and self.g.pos is not None):
            return False
        n = sum(self.g.issues.values())
        if n >= 8:
            bons = sum(self.g.issues.get(e, 0) for e in ('avance', 'bloque', 'pousse', 'mort')) + \
                0.5 * sum(self.g.issues.get(e, 0) for e in ('avance+', 'bloque+'))
            if bons / n < 0.6:
                return False
        return True

    def tuiles(self, im):
        return self.g.tuiles(im, self.lignes_masquees())

    def classer_grille(self, a, c0, tu0, tu1, mort):
        """Effet d'une touche directionnelle dans le monde en grille."""
        if mort:
            return 'mort'
        c1 = self.g.cellule() if self.g.pos is not None else None
        d = self.g.dcell(a); f = (c0[0] + d[0], c0[1] + d[1]); fb = (f[0] + d[0], f[1] + d[1])
        chg = {c for c in tu0 if tu1.get(c) != tu0[c]}
        if c1 is None:
            return 'perdu'
        if c1 == c0:
            return 'bloque' if not (chg - {c0}) else 'bloque+'
        if c1 == f:
            T = tu0.get(f)
            if fb in tu0 and tu1.get(fb) != tu0.get(fb) and fb in chg:
                if tu1.get(fb) == T or (tu1.get(fb) not in (None,) and T != tu0.get(fb)):
                    self.compose[tu1.get(fb)] = self.compose.get(T, T)
                    return 'pousse'
            return 'avance' if not (chg - {c0, f}) else 'avance+'
        return 'saut'

    def cles_grille(self, T, a, Tb):
        return [(('T', T), a, ('Tb', Tb)), (('T', T), a), (('T', T), '*')]

    def types_franchissables(self):
        """Classe des types de tuiles d'après l'effet dominant (niveau courant prioritaire sur l'a priori)."""
        cl = {}
        for tab in (self.prior, self.table):
            for cle, it in tab.e.items():
                if len(cle) == 2 and cle[1] == '*' and isinstance(cle[0], tuple) and cle[0][0] == 'T':
                    T = cle[0][1]; top = it.effets.most_common(1)[0][0]
                    if 'mort' in it.effets:
                        cl[T] = 'mur'
                    elif top in ('avance', 'avance+'):
                        cl[T] = 'ok'
                    elif top == 'pousse':
                        cl[T] = 'pous'
                    elif top in ('bloque', 'bloque+'):
                        cl[T] = 'mur'
        ok = {t for t, c in cl.items() if c == 'ok'}; pous = {t for t, c in cl.items() if c == 'pous'}
        mur = {t for t, c in cl.items() if c == 'mur'}
        return ok, pous, mur

    def candidats_grille(self, im):
        """Expériences et buts planifiés sur le modèle de grille : liste de (score, plan, info)."""
        if not self.g.pret() or self.g.pos is None:
            return []
        tu = self.tuiles(im); c0 = self.g.cellule()
        if c0 not in tu:
            return []
        ok, pous, mur = self.types_franchissables()
        dirs = {a: self.g.dcell(a) for a in DIR if self.g.dcell(a)}
        if not dirs:
            return []
        passable = dict(dirs=dirs, ok=lambda c: c in tu and tu[c] in ok)
        dist, pred = bfs_cases(c0, passable)
        out = []
        for c, L in dist.items():
            for a, (dx, dy) in dirs.items():
                f = (c[0] + dx, c[1] + dy)
                if f not in tu or f == c0:
                    continue
                T = tu[f]; Tb = tu.get((f[0] + dx, f[1] + dy))
                # le contexte (tuile derrière, direction) ne compte vraiment que pour les pièces poussables
                u, cat, ef = self.utilite_avec_prior(self.cles_grille(T, a, Tb), False, grille=True,
                                                     u_gen=0.25 if T in pous else 0.04)
                if T in ok and f in dist and cat.startswith('connu'):
                    continue                                    # simple navigation
                if u <= 0.02 or self.tabou[(c, a, f)] >= 2:
                    continue                                    # (tabou : expérience déjà tentée 2 fois sans effet sur le tableau)
                plan = (chemin(pred, c0, c) if c != c0 else []) + [a]
                out.append((u / (len(plan) + 1.0), plan, dict(cat=cat, T=T[:6], a=a, cible=f)))
        # buts candidats : pousser des pièces poussables sur des tuiles rares (réfutables)
        cnt = Counter(tu.values())
        sol = max(ok, key=lambda t: cnt.get(t, 0)) if ok else None
        acteur_t = tu.get(c0)
        boites_types = pous | {t for t, p in self.compose.items() if p in pous}
        boites = [c for c, t in tu.items() if t in boites_types]
        if boites and len(boites) <= 12:
            cibles_types = [t for t, n in cnt.items() if t not in boites_types and t not in mur and t != sol
                            and t != acteur_t and n <= max(3, 2 * len(boites))]
            for U in cibles_types:
                key = ('pousser', U)
                if key in self.refutes:
                    continue
                cibles = [c for c, t in tu.items() if t == U]
                libre = lambda c: c in tu and (tu[c] in ok or tu[c] == U or tu[c] in boites_types or c == c0)
                r = sokoban(c0, boites, cibles, libre, dirs)
                if r:
                    plan, cov = r
                    out.append((U_BUT * (1 + cov) / (len(plan) + 1.0) * 2, plan,
                                dict(cat='c_but_pousser', U=U[:6], couvertes=cov, but=key,
                                     objectif=min(len(cibles), len(boites)))))
        return out

    # ================================================================ graphe d'états (Go-Explore)
    def frontiere(self, k0, max_etats=400):
        todo = deque([(k0, [])]); vus = {k0: []}
        while todo and len(vus) < max_etats:
            k, ch = todo.popleft()
            ar = dict(self.supposees.get(k, {})); ar.update(self.aretes.get(k, {}))
            for a, k2 in ar.items():
                if k2 in ('mort', None) or k2 in vus:
                    continue
                vus[k2] = ch + [a]; todo.append((k2, ch + [a]))
        return vus

    def candidats_graphe(self, k0, grille_active):
        """Go-Explore sur le graphe observé, guidé par le tableau des interactions et par les estimateurs de progrès.
        Utiles = actions non essayées dans l'état dont l'utilité (tableau) dépasse un seuil (pas « rien » ni « mort »
        prédits). Règle d'escalade : on explore ici si l'état courant vaut au moins la meilleure frontière (−0,02),
        sinon on rejoint la frontière de meilleure valeur (moins 0,01 par coup de trajet, plus l'utilité attendue)."""
        chemins = self.frontiere(k0)
        vcur = self.valeur.get(k0, 0.0)
        par_etat = {}
        for k, ch in chemins.items():
            if k not in self.cands:
                continue
            if grille_active and k != k0:
                continue
            im = self.imgs[k]; L = len(ch)
            ctx = self.ctx if L == 0 else self.ctx_de(ch[-1], self.imgs.get(k))
            best = None
            for a in self.cands[k]:
                if a in self.aretes.get(k, {}):
                    continue
                if grille_active and a in DIR and self.g.dcell(a) is not None:
                    continue
                u, cat, ef = self.utilite_action(a, k, im, ctx)
                if u < 0:
                    continue
                if ef is not None and ef not in ('rien', 'bloque') and cat.startswith(('connu', 'a_gen')):
                    u += 0.12                       # arête inconnue à effet prédit : peut ouvrir un état nouveau
                if u < 0.03:
                    continue
                t = type_action(a, im)
                esc = self.deltas.get(t)
                # (c) but candidat « progrès » : un type d'action qui vient de rapprocher un estimateur de son but
                # est poursuivi en priorité (escalade), tant qu'il n'est pas démenti
                p = u + (4.0 * sum(esc[-3:]) / len(esc[-3:]) + (0.9 if esc[-1] > 1e-9 else 0.0) if esc else 0.0) \
                    + 0.3 * self.mem.taux(t) - (0.3 if a == 7 else 0.0)
                if best is None or p > best[0]:
                    best = (p, a, cat)
            if best:
                par_etat[k] = (best, ch)
        if not par_etat:
            return []
        vmax = max(self.valeur.get(k, 0.0) for k in par_etat)
        if k0 in par_etat and vcur >= vmax - 0.02:
            (p, a, cat), _ = par_etat[k0]
            return [((p / 2.0) if grille_active else (1.0 + p), [a], dict(cat=cat, a=str(a), L=0))]
        def sc(k):
            (p, a, cat), ch = par_etat[k]
            return self.valeur.get(k, 0.0) - 0.01 * len(ch) + 0.05 * p / (len(ch) + 1)
        k = max(par_etat, key=sc)
        (p, a, cat), ch = par_etat[k]
        return [(0.5 + sc(k), ch + [a], dict(cat='retour_' + cat, a=str(a), L=len(ch)))]

    def ctx_de(self, a, im):
        if isinstance(a, tuple):
            return 'clic:' + str(int(im[a[2], a[1]])) if im is not None else 'clic'
        return f'k{a}'

    # ================================================================ décision
    def choisir(self):
        im = self.lab.image; k = self.cle(im); self.n_choix += 1
        if k not in self.cands:
            self.cands[k] = self.candidats(k, im); self.imgs[k] = im.copy()
        if k not in self.valeur:
            self.evaluer(k, im)
        if self.plan:
            return self.plan.pop(0), 'plan:' + self.plan_info.get('cat', '?')
        grille_active = self.grille_ok()
        cands = self.candidats_grille(im) if grille_active else []
        if grille_active and not any(c[0] > 0.004 for c in cands):
            grille_active = False                 # le modèle de grille n'a plus rien à proposer : graphe complet
        cands += self.candidats_graphe(k, grille_active)
        # petit budget pour l'inconnu : une action jamais essayée dans cet état, même si le tableau la prédit
        meilleur = max((c[0] for c in cands), default=0.0)
        if self.n_choix % INCONNU_TOUS == 0 and (meilleur < 0.3 or not grille_active):
            non = [a for a in self.cands[k] if a not in self.aretes.get(k, {})
                   and self.utilite_action(a, k, im, self.ctx)[1] != 'predit_mort']
            if non:
                return self.rng.choice(non), 'inconnu_reserve'
        cands = [c for c in cands if self.admissible(c[1])] or cands
        if cands:
            sc, plan, info = max(cands, key=lambda c: (c[0], -len(c[1]), self.rng.random()))
            if sc > 0.004 or info.get('cat', '').startswith('c_'):
                self.plan = list(plan[1:]); self.plan_info = info; self.plan_cible = info
                self.stats[info.get('cat', '?')] += 1
                return plan[0], f"{info.get('cat')}:{round(sc, 3)}"
        # blocage avéré : rien d'utile atteignable
        # blocage avéré : rien d'utile n'est atteignable d'ici, mais l'état initial a encore des expériences utiles
        # (mouvements irréversibles) → RESET (compté), borné par niveau
        if self.resets_blocage < MAX_RESET_BLOCAGE and k != self.k_init and self.k_init in self.cands:
            if self.candidats_graphe(self.k_init, False) or self.n_init_utiles():
                return 0, 'reset_blocage'
        eff = [a for a, k2 in self.aretes.get(k, {}).items() if k2 not in ('mort', k)]
        if eff:
            return self.rng.choice(eff), 'graphe_epuise_aleatoire'
        return self.rng.choice(self.cands[k] or [1]), 'graphe_epuise_aleatoire'

    def evaluer(self, k, im):
        try:
            sc = self.buts.scores(im)
        except Exception:
            sc = {}
        self.scores[k] = sc; self.valeur[k] = self.buts.valeur(sc)
        return self.valeur[k]

    def admissible(self, plan):
        eco = getattr(self.lab, 'economy', None)
        try:
            if eco is not None and getattr(eco, 'valid', False) and getattr(eco, 'alive', np.array([])).any():
                return eco.admissible([a for a in plan])
        except Exception:
            pass
        return True

    # ================================================================ boucle
    def jouer(self, budget_niveau, actions_deja=0):
        lab = self.lab; erreurs = 0
        while len(lab.rows) < budget_niveau:
            if lab.finished and not lab.won:
                lab.reset_apres_defaite(); self.j.ecrire('reset', step=len(lab.rows), raison='defaite')
                self.apres_reset(); continue
            if erreurs >= 5:
                # filet de sécurité : l'explorateur générique P1 finit le niveau (jamais d'abstention)
                from agent_p1.generique import Explorateur
                self.j.ecrire('repli_generique', step=len(lab.rows))
                return Explorateur(lab, self.j, self.mem, self.rng.randrange(1000)).jouer(budget_niveau)
            try:
                a, pourquoi = self.choisir()
            except Exception as e:
                erreurs += 1; self.j.ecrire('erreur_explo_ow', step=len(lab.rows), message=str(e)[:300])
                self.plan = []
                a, pourquoi = self.rng.choice(self.lab.actions_disponibles or [1]), 'erreur'
                if a == 6:
                    a = ('clic', self.rng.randrange(64), self.rng.randrange(64))
                if a == 0:
                    a = 1
            if a == 0:
                self.resets_blocage += 1
                lab.reset_apres_defaite('RESET_blocage'); self.j.ecrire('reset', step=len(lab.rows), raison='blocage')
                self.apres_reset(); continue
            try:
                self.pas(a, pourquoi)
            except Exception as e:
                erreurs += 1; self.j.ecrire('erreur_explo_ow', step=len(lab.rows), message=str(e)[:300])
                self.plan = []
            if lab.won:
                return 'victoire'
        return 'budget'

    def n_init_utiles(self):
        return 0

    def apres_reset(self):
        self.plan = []; self.ctx = '-'; self.dernier_nouveau = len(self.lab.rows)
        self.k_init = self.cle(self.lab.image)
        if self.g.gab is not None:
            self.g.pos = self.g.localiser(self.lab.image, None)

    def pas(self, a, pourquoi):
        lab = self.lab
        im0 = lab.image.copy(); k0 = self.cle(im0)
        grille_avant = self.grille_ok() and a in DIR and self.g.dcell(a) is not None
        if grille_avant:
            c0 = self.g.cellule(); tu0 = self.tuiles(im0)
        lab.play(a, 'explo_ow:' + pourquoi)
        im1 = lab.image; mort = lab.finished and not lab.won
        diff = np.argwhere(im0 != im1)
        if 0 < len(diff) <= 8:
            for y, x in diff:
                if min(x, y, 63 - x, 63 - y) <= 2:
                    self.compteurs.add((int(x), int(y)))
        k1 = 'mort' if mort else self.cle(im1)
        # ---- grille : apprentissage du contrôlé puis effet dans le monde en grille
        if a in DIR and not mort:
            self.g.observer_touche(a, im0, im1)
        if grille_avant:
            tu1 = self.tuiles(im1) if not mort else tu0
            ef = self.classer_grille(a, c0, tu0, tu1, mort)
            d = self.g.dcell(a); f = (c0[0] + d[0], c0[1] + d[1]); fb = (f[0] + d[0], f[1] + d[1])
            T = tu0.get(f); self.dernier = (c0, f, (T or '')[:6], ef)
            gen = self.table.e.get((('T', T), '*'))
            if ef in ('avance+', 'bloque+') and (gen is None or gen.effets.get(ef, 0) == 0):
                self.table.epoque += 1                  # effet de bord d'un genre nouveau : le monde a pu changer
            self.g.issues[ef] = self.g.issues.get(ef, 0) + 1
            if T is not None:
                self.table.noter(self.cles_grille(T, a, tu0.get(fb)), ef)
            self.tabou[(c0, a, f)] += 1
            if self.plan and self.plan_info and ef in ('bloque', 'saut', 'perdu', 'mort', 'bloque+'):
                self.plan = []                        # prédiction démentie : on replanifie
            self.verifier_but(tu1 if not mort else None)
        # ---- tableau général (toujours : clés globales de l'action, même quand la grille a classé l'effet)
        if True:
            ef = self.signature(im0, im1, a, mort)
            if isinstance(a, tuple) and 'D:' in ef and not any(
                    self.table.e.get(c[-1]) and self.table.e[c[-1]].effets.get(ef) for c in self.cles_action(a, k0, im0, self.ctx)):
                self.table.epoque += 1
            for chaine in self.cles_action(a, k0, im0, self.ctx):
                self.table.noter(chaine, ef)
            if self.plan:
                attendu = None
                # en mode graphe le plan suit des arêtes connues : un écart invalide le plan
                ar = self.aretes.get(k0, {}).get(a) or self.supposees.get(k0, {}).get(a)
                if ar is not None and ar != k1:
                    self.plan = []
        # ---- graphe
        if k1 != 'mort' and k1 not in self.valeur:
            self.evaluer(k1, im1)
        if k1 != 'mort' and self.buts.refuter_si_atteint(self.scores.get(k1, {}), lab.won):
            self.valeur = {kk: self.buts.valeur(sc) for kk, sc in self.scores.items()}   # but réfuté : on réévalue
            self.j.ecrire('but_refute', step=len(lab.rows), refutes=sorted(self.buts.refutes))
        if k1 != 'mort' and k1 not in self.cands:
            self.dernier_nouveau = len(lab.rows)
        self.aretes.setdefault(k0, {})[a] = k1
        effet = k1 != k0
        self.mem.noter(type_action(a, im0), effet, victoire=lab.won)
        if effet and k1 != 'mort':
            inv = {1: 2, 2: 1, 3: 4, 4: 3}.get(a) if not isinstance(a, tuple) else None
            if inv:
                self.supposees.setdefault(k1, {}).setdefault(inv, k0)
            if 7 in (lab.actions_disponibles or []):
                self.supposees.setdefault(k1, {}).setdefault(7, k0)
            dv = self.valeur.get(k1, 0.0) - self.valeur.get(k0, 0.0)
            self.deltas.setdefault(type_action(a, im0), []).append(dv)
            self.ctx = self.ctx_de(a, im0)
        if k1 == 'mort':
            self.plan = []
        self.j.ecrire('explo_ow', step=len(lab.rows), action=a, pourquoi=pourquoi, effet=effet,
                      etats=len(self.aretes), interactions=len(self.table), victoire=lab.won,
                      grille=bool(self.g.pret()), progres=round(self.valeur.get(k1, 0.0), 3) if k1 != 'mort' else None)

    def verifier_but(self, tu1):
        """Réfutation : un plan de but terminé, objectif atteint, sans victoire → le but est abandonné."""
        info = self.plan_info or {}
        if self.plan or not info.get('but') or self.lab.won:
            return
        if info.get('couvertes', 0) >= info.get('objectif', 99):
            self.refutes.add(info['but'])
        self.plan_info = None

    def bilan(self):
        b = self.table.bilan(); b.update(etats=len(self.aretes), grille=bool(self.g.pret()),
                                         resets_blocage=self.resets_blocage, refutes=len(self.refutes),
                                         choix=dict(self.stats))
        return b
