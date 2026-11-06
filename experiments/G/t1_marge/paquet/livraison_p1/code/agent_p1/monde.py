"""Modèle de planification v4 étendu par des hypothèses inventées (sans modifier le code v4).

État : (pos, routes, idx, record, bits, autos) — les 5 premiers champs sont ceux de la v4, `autos` est le tuple des
états d'objets autonomes (semantique.py). Hypothèses de porte (réparations liées à un certificat) :
  'franchissable' : les portes de bascule dessinées fermées laissent passer le joueur (rendu ≠ état).
La transition reprend `FantomeGeneral.step_state` ligne à ligne, avec des occupants étendus aux objets autonomes
dont l'hypothèse dit qu'ils occupent les dalles (portée M7).
"""
import time
from collections import deque
from .semantique import pas_objet, visible, etat_initial, INDETERMINE


class ModeleEtendu:
    def __init__(self, base, autos=(), portes=None):
        """base : FantomeGeneral (v4) ; autos : liste de (objet, programme) ; portes : dict d'hypothèses de porte."""
        self.b = base; self.autos = list(autos); self.portes = dict(portes or {})
        self.step = base.step; self.dirs = base.dirs; self.groups = base.groups
        self.goals = base.goals; self.triggers = base.triggers; self.doors = base.doors
        self.node_set = base.node_set; self.start = base.start; self.shape = base.shape
        self.blocked = getattr(base, 'blocked', set())

    def initial_depuis(self, s5, autos_etats=None):
        return tuple(s5) + (tuple(autos_etats) if autos_etats is not None else
                            tuple(etat_initial(o['pos0']) for o, p in self.autos),)

    # --- occupants, portes ---
    def occupants(self, p, routes, idx, autos):
        occ = {p} | {r[min(idx, len(r) - 1)] for r in routes}
        for (o, prog), st in zip(self.autos, autos):
            if st[2] and prog.get('portee_dalles'):
                occ.add(st[0])
        return occ

    def opened(self, p, routes, idx, bits, autos):
        from boucle_v4.contrats_v4 import porte
        occ = self.occupants(p, routes, idx, autos); out = set()
        for g, group in enumerate(self.groups):
            occupied = any(t in occ for t in group['triggers'])
            kind = group['kind']
            if kind == 'portal' or porte(kind, occupied, bool(bits & (1 << g))):
                out.add(g)
            elif kind == 'toggle' and self.portes.get('franchissable'):
                out.add(g)
        return out

    def fermees(self, p, routes, idx, bits, autos):
        op = self.opened(p, routes, idx, bits, autos)
        return {d for d, g in self.doors.items() if g not in op}

    def _ctx(self, a, eff, p, q, fav, fap, origine):
        return dict(action=a, effectif=eff, joueur_avant=p, joueur_apres=q, pas=self.step, noeuds=self.node_set,
                    origine=origine, portes_fermees_avant=fav, portes_fermees_apres=fap)

    def _autos_pas(self, autos, a, eff, p, q, fav, fap):
        out = []
        for (o, prog), st in zip(self.autos, autos):
            ns = pas_objet(prog, st, self._ctx(a, eff, p, q, fav, fap, o['pos0']))
            if ns == INDETERMINE:
                return INDETERMINE
            out.append(ns)
        return tuple(out)

    # --- transition ---
    def step_state(self, s, a):
        from boucle_v4.contrats_v4 import ajouter_memoire
        p, routes, idx, record, bits, autos = s
        fav = self.fermees(p, routes, idx, bits, autos)
        if a == 5:
            rs = ajouter_memoire(routes, (self.start,) + record, self.b.capacity, self.b.overflow) if record else routes
            na = self._autos_pas(autos, 5, False, p, self.start, fav, fav)
            if na == INDETERMINE:
                return None
            return self.start, rs, 0, (), (0 if self.b.reset_bits else bits), na
        dx, dy = self.dirs[a - 1]; q = p[0] + dx, p[1] + dy
        bloque = (p, a) in self.blocked or q not in self.node_set or \
            (q in self.doors and self.doors[q] not in self.opened(p, routes, idx, bits, autos))
        if bloque:
            na = self._autos_pas(autos, a, False, p, p, fav, fav)
            if na == INDETERMINE:
                return None
            return p, routes, idx, record, bits, na
        ni = min(idx + 1, max(map(len, routes)) - 1) if routes else 0
        # objets autonomes : déplacement d'abord, destruction jugée après l'état des portes
        na = self._autos_pas(autos, a, True, p, q, fav, set())
        if na == INDETERMINE:
            return None
        before = self.occupants(p, routes, idx, autos); after = self.occupants(q, routes, ni, na)
        for g, group in enumerate(self.groups):
            if group['kind'] == 'toggle' and any(t in after for t in group['triggers']) and \
                    not any(t in before for t in group['triggers']):
                bits ^= 1 << g
        fap = self.fermees(q, routes, ni, bits, na)
        na2 = []
        for (o, prog), st in zip(self.autos, na):
            if st[2] and prog['destruction'] in ('porte_fermee', 'bloque_et_ecrase') and st[0] in fap:
                st = (st[0], st[1], False, st[3], st[4])
            na2.append(st)
        na = tuple(na2)
        if q in self.doors and self.doors[q] not in self.opened(q, routes, ni, bits, na):
            return None
        for group in self.groups:
            if group['kind'] == 'portal' and q in group['doors'] and any(t in after for t in group['triggers']):
                ds = group['doors']; q = ds[(ds.index(q) + 1) % len(ds)]
        memo = getattr(self.b, 'memo_transitions', None)
        if memo:
            k = (p, a, bits, frozenset(t for t in self.triggers if t in before))
            if k in memo:
                q = memo[k]     # transition déjà observée : l'observation prime sur la loi (exception enregistrée)
        return q, routes, ni, record + (q,), bits, na

    def observation(self, s):
        """Ce que l'hypothèse prédit de visible : pose joueur, poses des objets autonomes, portes fermées."""
        if s is None:
            return ('mort',)
        p, routes, idx, record, bits, autos = s
        fap = self.fermees(p, routes, idx, bits, autos)
        vis = tuple(visible(prog, st, dict(portes_fermees_apres=fap)) for (o, prog), st in zip(self.autos, autos))
        return (p, vis, tuple(sorted(fap)))

    # --- planification ---
    def _cle(self, s):
        p, routes, idx, record, bits, autos = s
        ak = tuple((st[0], st[2], st[3]) + ((st[1],) if prog['effet'] == 'route_latente' else ())
                   for (o, prog), st in zip(self.autos, autos))
        return p, idx, bits, ak

    def nav(self, s, cible, maxsteps=80, deadline=None):
        """BFS bornée en profondeur et en nœuds (compteur partagé self._noeuds / self._max_noeuds)."""
        todo = deque([(s, ())]); seen = {self._cle(s)}; local = 0
        dans_solve = getattr(self, '_dans_solve', False)
        while todo:
            local += 1
            if dans_solve:
                self._noeuds += 1
                if self._noeuds > self._max_noeuds:
                    return None
            elif local > 50000:
                return None
            cur, path = todo.popleft()
            if (cur[0] in cible) if isinstance(cible, (set, frozenset)) else cur[0] == cible:
                return cur, list(path)
            if len(path) >= maxsteps:
                continue
            for a in range(1, 5):
                ns = self.step_state(cur, a)
                if ns is None:
                    continue
                k = self._cle(ns)
                if k not in seen:
                    seen.add(k); todo.append((ns, path + (a,)))
        return None

    def solve(self, s, seconds=None, max_vies=3, maxsteps=80, max_noeuds=150000):
        """Recherche par vies : chaque vie = navigation vers une dalle/cible puis ACTION5 (fantôme), dernière vie = BFS
        complète vers le but. Rend dict(status, actions)."""
        self._noeuds = 0; self._max_noeuds = max_noeuds; deadline = None   # bornes en nœuds, jamais en secondes
        self._dans_solve = True
        try:
            return self._solve(s, max_vies, maxsteps, max_noeuds, deadline)
        finally:
            self._dans_solve = False

    def _solve(self, s, max_vies, maxsteps, max_noeuds, deadline):
        cibles = set(self.triggers)
        for pt, g in self.triggers.items():
            if self.groups[g]['kind'] == 'toggle':
                for dx, dy in self.dirs:
                    q = pt[0] + dx, pt[1] + dy
                    if q in self.node_set:
                        cibles.add(q)
        front = [(s, [])]; vus = set(); n = 0
        for vie in range(max_vies + 1):
            nouveaux = []
            for cur, path in front:
                if self._noeuds > max_noeuds:
                    return dict(status='NOEUDS', nodes=n, noeuds=self._noeuds)
                r = self.nav(cur, set(self.goals), maxsteps, deadline); n += 1
                if r is not None:
                    return dict(status='SAT', actions=path + r[1], nodes=n, vies=vie)
                if vie == max_vies:
                    continue
                for c in sorted(cibles):
                    r = self.nav(cur, c, maxsteps, deadline); n += 1
                    if r is None or not r[1]:
                        continue
                    ns = self.step_state(r[0], 5)
                    if ns is None:
                        continue
                    k = (tuple(ns[1]), self._cle(ns))
                    if k in vus:
                        continue
                    vus.add(k); nouveaux.append((ns, path + r[1] + [5]))
            nouveaux.sort(key=lambda t: len(t[1]))
            front = nouveaux[:40]
            if not front:
                break
        return dict(status='NO_PLAN_BOUNDED', nodes=n)

    def simuler_seq(self, s, seq):
        """Observations prédites après chaque action de seq (s'arrête à la mort)."""
        out = []
        for a in seq:
            s = self.step_state(s, a) if s is not None else None
            out.append(self.observation(s))
            if s is None:
                break
        return out, s
