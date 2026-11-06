"""Exploration générique de jeu inconnu (aucune famille de mécanismes, aucune couleur codée).

Graphe d'états observés (image sans bord ni pixels « compteurs ») ; dans chaque état, actions candidates =
touches disponibles + clics au centre de chaque objet (composante connexe non fond). On essaie d'abord les actions
non essayées de l'état courant, ordonnées par un a priori appris (taux d'effet par type d'action, mémoire inter-niveaux
et inter-jeux) ; sinon on retourne par le graphe vers l'état connu le plus proche qui a encore des actions non essayées.
Défaite → RESET compté, le graphe est conservé (les transitions mortelles sont évitées). Jamais d'abstention.
"""
import hashlib, os, random
from collections import deque, Counter
import numpy as np
from .objets import composantes

CLAVIER = (1, 2, 3, 4, 5, 7)


def effet_film(lab, im0, a, mode, deco=None):
    """C (CW-444/445 C1-F1, CHRYS_FILMS_P1) : le film du coup montre-t-il un événement (E, chrysalide/arc3/films.py) ?
    mode 1 : sortes nettes (couleur éphémère, trajet à positions intermédiaires, curseur) ; mode 2 : tout événement ;
    mode 3 : mode 1 moins les contrôles négatifs de CW-445 : trajet qui REVIENT au départ seul, cases transitoires toutes
    au bord (jauge), et animation DÉCORATIVE (même masque transitoire pour une autre action du même état, `deco`)."""
    film = lab.films.get('film_' + str(len(lab.rows)))
    if film is None or len(film) < 2:
        return False
    from .films_mesure import evenements, transitoires  # C (T1) : la version MESURÉE des films (le dépôt a bougé, F2 d'E)
    e = evenements(im0, list(film), (a[1], a[2]) if isinstance(a, tuple) else None)
    if mode == '3':
        aller = any(t['intermediaires'] and not t['revient'] for t in e['trajectoires'])
        net = bool(e['transitoires']['ephemeres']) or aller or any(x['sorte'] == 'curseur' for x in e['signaux'])
        if not net:
            return False
        _, tm = transitoires(np.asarray(im0), [np.asarray(x) for x in film])
        ys, xs = np.nonzero(tm)
        if len(ys) and np.all((ys <= 2) | (ys >= 61) | (xs <= 2) | (xs >= 61)):
            return False
        if deco is not None:
            vus = deco.setdefault(hashlib.sha1(np.asarray(im0).tobytes()).hexdigest(), {})
            sig = hashlib.sha1(tm.tobytes()).hexdigest()
            autres = {b for b, s2 in vus.items() if s2 == sig and b != repr(a)}
            vus[repr(a)] = sig
            if autres:
                return False
        return True
    nettes = (bool(e['transitoires']['ephemeres']) or any(t['intermediaires'] for t in e['trajectoires'])
              or any(x['sorte'] == 'curseur' for x in e['signaux']))
    if mode == '1':
        return nettes
    return (nettes or bool(e['transitoires']['cases']) or bool(e['contacts'])
            or any(x['sorte'] != 'retour_clic' for x in e['signaux']))
MAX_CLICS = 40


def fond(im):
    v, c = np.unique(im, return_counts=True)
    return int(v[np.argmax(c)])


def objets(im):
    bg = fond(im); out = []
    for c in np.unique(im):
        if c == bg:
            continue
        for cs in composantes(im == c):
            xs = np.array([x for x, y in cs]); ys = np.array([y for x, y in cs])
            mx, my = xs.mean(), ys.mean()
            k = int(np.argmin((xs - mx) ** 2 + (ys - my) ** 2))
            out.append(dict(c=int(c), n=len(cs), x=int(xs[k]), y=int(ys[k]),
                            bord=bool(xs.min() == 0 or ys.min() == 0 or xs.max() == 63 or ys.max() == 63)))
    return out


def type_action(a, im=None):
    if isinstance(a, tuple):
        c = int(im[a[2], a[1]]) if im is not None else -1
        return f'clic:c{c}'
    return f'k{a}'


class Memoire:
    """A priori d'actions : taux d'effet et participation aux victoires, par type. Persistant entre niveaux (même jeu,
    poids plein) et entre jeux (a priori faible : ramené à 2 observations équivalentes au début d'un nouveau jeu)."""
    def __init__(self, d=None):
        self.d = d or {}; self.d.setdefault('global', {}); self.jeu = None

    def changer_jeu(self, jeu):
        self.jeu = jeu; self.d.setdefault(jeu, {})

    def taux(self, t):
        g = self.d['global'].get(t, [0, 0, 0]); j = self.d.get(self.jeu, {}).get(t, [0, 0, 0]) if self.jeu else [0, 0, 0]
        k = min(2.0, g[0]) / g[0] if g[0] else 0.0          # a priori inter-jeux plafonné à 2 observations
        n = j[0] + k * g[0]; e = j[1] + k * g[1]; v = j[2] + k * g[2]
        return (e + 1) / (n + 2) + 0.5 * v / (n + 2)

    def noter(self, t, effet, victoire=False):
        for cle in ('global', self.jeu):
            if cle is None:
                continue
            e = self.d.setdefault(cle, {}).setdefault(t, [0, 0, 0]); e[0] += 1; e[1] += int(effet); e[2] += int(victoire)


class Explorateur:
    def __init__(self, lab, journal, memoire=None, graine=0):
        self.lab = lab; self.j = journal; self.mem = memoire or Memoire(); self.rng = random.Random(graine)
        self.compteurs = set()          # pixels qui changent seuls (jauge, horloge)
        self.aretes = {}                # clé -> {action: clé suivante | 'mort'}
        self.cands = {}; self.vues = Counter(); self.trace = []
        from .progres import Progres
        self.progres = Progres(lab.image); self.valeur = {}
        self.supposees = {}             # arêtes inverses supposées (flèche opposée, annuler), vérifiées à l'usage
        self.deltas = {}                # type d'action -> derniers écarts de progrès observés
        self.deco = {}                  # C (F1, mode 3) : état -> {action: masque transitoire}

    # -------------------------------------------------- perception
    def masque(self, im):
        m = im.copy()
        if os.environ.get('CHRYS_F_CLE') == 'bande3':  # F (CW-454, CCM-051-F) : bord de 3 px (jauges, compteurs collés)
            m[:3, :] = m[-3:, :] = 0; m[:, :3] = m[:, -3:] = 0
        else:
            m[0, :] = m[-1, :] = 0; m[:, 0] = m[:, -1] = 0
        for (x, y) in self.compteurs:
            m[y, x] = 0
        return m

    def cle(self, im):
        return hashlib.sha1(self.masque(im).tobytes()).hexdigest()[:16]

    def candidats(self, im):
        dispo = self.lab.actions_disponibles or list(range(1, 8))
        out = [a for a in CLAVIER if a in dispo]
        if 6 in dispo:
            obs = sorted(objets(im), key=lambda o: (o['bord'], o['n'] > 400, -self.mem.taux(f"clic:c{o['c']}"), o['n']))
            vus = set()
            for o in obs:
                k = (o['x'], o['y'])
                if k in vus:
                    continue
                vus.add(k); out.append(('clic', o['x'], o['y']))
                if len(out) >= MAX_CLICS + 6:
                    break
        return out

    # -------------------------------------------------- choix
    def priorite(self, a, im):
        t = type_action(a, im)
        p = self.mem.taux(t)
        d = self.deltas.get(t)
        if d:
            p += 4.0 * sum(d[-3:]) / len(d[-3:])      # escalade : préférer ce qui a récemment fait progresser
        if a == 7:
            p -= 0.3                     # annuler sert surtout de retour, pas d'exploration
        p = p + self.rng.random() * 1e-3
        if os.environ.get('CHRYS_G_NOUV') == '1':  # G (CW-448/449, CCM-066-G) : un coup non essayé dont l'arête inverse
            k = self.cle(im)                         # supposée ramène à un état déjà vu passe après les autres
            if a in self.supposees.get(k, {}) and a not in self.aretes.get(k, {}):
                p -= 50.0
        return p

    def frontieres(self, k0):
        """États connus atteignables qui ont des actions non essayées : {clé: chemin}."""
        todo = deque([(k0, [])]); vus = {k0}; out = {}
        while todo:
            k, ch = todo.popleft()
            if any(a not in self.aretes.get(k, {}) for a in self.cands.get(k, [])):
                out[k] = ch
            aretes = dict(self.supposees.get(k, {})); aretes.update(self.aretes.get(k, {}))
            for a, k2 in aretes.items():
                if k2 in ('mort', None) or k2 == k or k2 in vus:
                    continue
                vus.add(k2); todo.append((k2, ch + [a]))
        return out

    def chemin_vers_frontiere(self, k0):
        """Meilleur d'abord : valeur de progrès (estimateurs génériques) moins 0,01 par coup de trajet."""
        fr = self.frontieres(k0)
        if not fr:
            return None
        k = max(fr, key=lambda k: (self.valeur.get(k, 0.0) - 0.01 * len(fr[k]), -len(fr[k])))
        return fr[k] or None

    def choisir(self):
        im = self.lab.image; k = self.cle(im)
        if k not in self.cands:
            self.cands[k] = self.candidats(im)
        if k not in self.valeur:
            self.valeur[k] = self.progres.evaluer(im)[0]
        non = [a for a in self.cands[k] if a not in self.aretes.get(k, {})]
        ch = self.chemin_vers_frontiere(k)
        if ch and ch[0] in self.supposees.get(k, {}) and ch[0] not in self.aretes.get(k, {}):
            return ch[0], 'vers_meilleure_frontiere(inverse_suppose)'
        if non and (not ch or self.valeur[k] >= max(self.valeur.get(kk, 0.0) for kk in self.frontieres(k)) - 0.02):
            return max(non, key=lambda a: self.priorite(a, im)), 'exploration_nouvelle'
        if ch:
            return ch[0], 'vers_meilleure_frontiere'
        if ch:
            return ch[0], 'retour_frontiere'
        eff = [a for a, k2 in self.aretes.get(k, {}).items() if k2 not in ('mort', k)]
        if eff:
            return self.rng.choice(eff), 'graphe_epuise_aleatoire'
        return self.rng.choice(self.cands[k] or [1]), 'graphe_epuise_aleatoire'

    # -------------------------------------------------- boucle
    def jouer(self, budget_niveau, actions_deja=0):
        """Joue jusqu'à victoire du niveau, fin de partie gagnée, ou budget épuisé. Rend la raison."""
        lab = self.lab
        while len(lab.rows) < budget_niveau:
            if lab.finished and not lab.won:
                lab.reset_apres_defaite(); self.j.ecrire('reset', step=len(lab.rows)); continue
            mode_t1 = os.environ.get('CHRYS_P1_MOTEUR')
            if mode_t1 in ('observe', 'joue'):  # C (T1, CW-455) : relève de MoteurC au franchissement de 40/80/120 coups
                from .releve_moteur import DECLENCHEURS, tenter
                faits = lab.__dict__.setdefault('_t1_faits', set())
                seuils = [t for t in DECLENCHEURS if len(lab.rows) >= t and t not in faits]
                if seuils:
                    faits.update(seuils)
                    if tenter(self, mode_t1) == 'victoire_moteur':
                        return 'victoire_moteur'
                    if lab.finished or len(lab.rows) >= budget_niveau:
                        continue
            a, pourquoi = self.choisir()
            im0 = lab.image.copy(); k0 = self.cle(im0)
            lab.play(a, 'generique:' + pourquoi)
            im1 = lab.image
            diff = np.argwhere(im0 != im1)
            if 0 < len(diff) <= 4:      # petit changement près du bord : jauge/horloge, pas un état du jeu
                for y, x in diff:
                    if min(x, y, 63 - x, 63 - y) <= 2:
                        self.compteurs.add((int(x), int(y)))
            k1 = 'mort' if (lab.finished and not lab.won) else self.cle(im1)
            if k1 != 'mort' and k1 not in self.valeur:
                self.valeur[k1] = self.progres.evaluer(im1)[0]
            self.aretes.setdefault(k0, {})[a] = k1
            effet = k1 != k0
            mode = os.environ.get('CHRYS_FILMS_P1')
            effet_memo = effet or (k1 != 'mort' and mode in ('1', '2', '3') and effet_film(lab, im0, a, mode, self.deco))
            self.mem.noter(type_action(a, im0), effet_memo, victoire=lab.won)
            if effet and k1 != 'mort':
                inv = {1: 2, 2: 1, 3: 4, 4: 3}.get(a) if not isinstance(a, tuple) else None
                if inv:
                    self.supposees.setdefault(k1, {}).setdefault(inv, k0)
                if 7 in (self.lab.actions_disponibles or []):
                    self.supposees.setdefault(k1, {}).setdefault(7, k0)
                dv = self.valeur.get(k1, 0.0) - self.valeur.get(k0, 0.0)
                self.deltas.setdefault(type_action(a, im0), []).append(dv)
            self.trace.append((k0, a, k1))
            self.j.ecrire('generique', step=len(lab.rows), action=a, pourquoi=pourquoi, effet=effet,
                          etats=len(self.aretes), victoire=lab.won,
                          progres=round(self.valeur.get(k1, 0.0), 3) if k1 != 'mort' else None)
            if lab.won:
                for (kk, aa, kk2) in self.trace[-20:]:
                    pass
                return 'victoire'
        return 'budget'
