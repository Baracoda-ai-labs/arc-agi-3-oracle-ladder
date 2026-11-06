"""Boucle réelle : observation → contradiction → invention → filtrage → expérience → vérification → bibliothèque → plan.

Réutilise sans les modifier : Laboratoire (exécution, comptage, jauge), FantomeGeneral (perception v4, transition v4),
contrats_v4 (portes, mémoire). Ajoute : suivi de tous les objets, inventeur, modèles étendus, choix d'expériences.

Modes (ablations) : 'complet' (risque+plan), 'gain_info', 'aleatoire', 'sans_experience', 'parametres'.
La référence sans inventeur est l'agent v4 lui-même (`boucle_v4.agent_fantome.run`), lancé par `ablations.py`.
"""
import sys, time, json, math, traceback
from pathlib import Path
from collections import Counter

ASTRA = Path(__file__).resolve().parents[3] / 'references/astra4/livraison_astra4/ajouts'
sys.path.insert(0, str(ASTRA))
from boucle_v4.fantome_general import FantomeGeneral  # noqa: E402
from boucle_v4.laboratoire import Laboratoire  # noqa: E402
from boucle_v4.economie import BudgetInconnu  # noqa: E402
from boucle_v4.contrats_v4 import ajouter_memoire  # noqa: E402

from . import objets as O  # noqa: E402
from .mutations import contexte_causal, generer, generer_parametres_seuls  # noqa: E402
from .classement import evaluer, classes_equivalence  # noqa: E402
from .simulation import etat_final  # noqa: E402
from .monde import ModeleEtendu  # noqa: E402
from .hypotheses import Hypothese, programme, nouveaute  # noqa: E402
from .experiences import choisir  # noqa: E402
from .journal import Journal, sha_code  # noqa: E402
from .superviseur import superviser, Memoire  # noqa: E402
from .bibliotheque import Bibliotheque  # noqa: E402

MODES = ('complet', 'gain_info', 'aleatoire', 'sans_experience', 'parametres')
K_CLASSES = 4


def sync_bits(model, s5, image):
    p, routes, idx, record, bits = s5
    occ = model.occupants(p, routes, idx)
    for g, group in enumerate(model.groups):
        if group['kind'] != 'toggle':
            continue
        for dp in group['doors']:
            if dp in occ:
                continue
            closed = sum(image[dp[1] + v, dp[0] + u] == group['color'] for u, v in model.shape) >= len(model.shape) * .5
            bits = bits & ~(1 << g) if closed else bits | (1 << g)
    return p, routes, idx, record, bits


class Agent:
    def __init__(self, game, level, jeux, output, mode='complet', budget=150, seconds=900, biblio=None,
                 graine=0, lab=None, max_noeuds=150000, memoire=None, sans_superviseur=False):
        assert mode in MODES
        self.out = Path(output); self.out.mkdir(parents=True, exist_ok=True)
        self.game, self.level, self.mode, self.budget, self.seconds = game, level, mode, budget, seconds
        self.graine = graine; self.max_noeuds = max_noeuds
        self.lab = lab or Laboratoire(game, level, jeux, self.out / 'partie')
        self.biblio = Bibliotheque(biblio) if biblio else None
        self.j = Journal(self.out, 'journal', dict(game=game, level=level, mode=mode, budget=budget, graine=graine,
                                                    injecte=self.lab.injected, biblio=str(biblio)))
        self.hyps = {}; self.version = Counter(); self.inventions = []; self.interventions = []
        self.refutes = {}; self.plans = {}; self.engagement = []; self.engagement_but = None
        self.visites = Counter(); self.n_generees = 0; self.evenements = []
        self.t_premier_modele_correct = None; self.mecanismes_biblio = []
        self.memoire = Memoire(memoire or (self.out / 'memoire_hypotheses.json'))
        self.sans_superviseur = sans_superviseur; self.stagnation = Counter(); self.retrogradees = set()
        self.rapports_superviseur = []; self.sans_loi = 0
        self.certificat_actif = False   # les réparations de certificat ne sont proposées que si aucun modèle n'a de plan

    # ------------------------------------------------------------------ perception / suivi
    def identifier(self):
        for a in range(1, 5):
            if len(self.lab.rows) >= self.budget or self.lab.finished:
                break
            b = self.lab.image.copy(); im, _ = self.lab.play(a, 'identifier_translation')
            try:
                m = FantomeGeneral(b, im, a)
                return m
            except (ValueError, IndexError, AssertionError) as e:
                self.j.ecrire('identification', step=len(self.lab.rows), message=str(e))
        return None

    def init_suivi(self):
        m = self.model; ims = self.lab.images
        self.objs = O.objets_initiaux(m, ims[0])
        self.poses = [m.start]; self.pistes = {o['id']: [o['pos0']] for o in self.objs}
        self.fant = [set()]; self.lignes = []
        self.s5 = (m.start, (), 0, (), 0)
        self.s5 = sync_bits(m, self.s5, ims[0])
        for t in range(1, len(ims)):
            self.avancer_suivi(t)

    def avancer_suivi(self, t):
        m = self.model; im = self.lab.images[t]; a = self.lab.rows[t - 1]['action']
        p_prev = self.poses[-1]
        if a == 5:
            pres = m.start                      # ACTION5 renvoie au départ : ne pas confondre avec un fantôme
        elif a in (1, 2, 3, 4):
            pres = (p_prev[0] + m.dirs[a - 1][0], p_prev[1] + m.dirs[a - 1][1])
        else:
            pres = p_prev
        p = m.observe_player(im, pres) or p_prev
        pos, routes, idx, record, bits = self.s5
        if a == 5:
            routes = ajouter_memoire(routes, (m.start,) + record, m.capacity, m.overflow) if record else routes
            pos, idx, record = p, 0, ()
            bits = 0 if m.reset_bits else bits
        elif a in (1, 2, 3, 4) and p != p_prev:
            idx = min(idx + 1, max(map(len, routes)) - 1) if routes else 0
            record = record + (p,); pos = p
        else:
            pos = p
        self.s5 = sync_bits(m, (pos, routes, idx, record, bits), im)
        self.poses.append(p)
        fant = {r[min(idx, len(r) - 1)] for r in routes}
        self.fant.append(fant)
        objets = {}
        for o in self.objs:
            prev = next((q for q in reversed(self.pistes[o['id']]) if q is not None), o['pos0'])
            q = O.localiser(o, im, prev, fant)
            objets[o['id']] = (self.pistes[o['id']][-1], q); self.pistes[o['id']].append(q)
        self.lignes.append(dict(t=t, action=a, joueur_avant=p_prev, joueur_apres=p,
                                effectif=(a in (1, 2, 3, 4) and p != p_prev),
                                portes_fermees=sorted(O.portes_fermees(m, im)), objets=objets))
        self.visites[('pose', p)] += 1

    # ------------------------------------------------------------------ invention / filtrage
    def hyps_biblio(self, o):
        out = []
        if not self.biblio:
            return out
        for mec in self.biblio.mecanismes('valide'):
            prog = dict(mec['programme']); prog['portee_dalles'] = None
            if prog['effet'] == 'route_latente':
                continue
            h = Hypothese(id=f"{o['id']}-{mec['id']}", version=0, objet=o['id'], programme=programme(**{
                k: prog[k] for k in ('declencheur', 'effet', 'reinit', 'delai', 'transfo', 'destruction', 'fin_route', 'fin_couloir')
                if k in prog}),
                mutations=[f"bibliotheque:{mec['id']}"])
            h.__dict__['biblio'] = mec['id']; h.__dict__['t_inv'] = len(self.lignes)
            out.append(h)
        return out

    def inventer(self, o, cons):
        self.version[o['id']] += 1
        ctx = contexte_causal(o, cons, self.lignes)
        contexte = f"{self.game}_N{self.level}_{o['id']}"
        pi = O.portes_fermees(self.model, self.lab.images[0])
        if self.mode == 'parametres':
            hyps = generer_parametres_seuls(o, ctx, self.lignes)
            evaluer(hyps, o, self.lignes, self.model, len(self.lignes), portes_initiales=pi)
            rap = dict(familles=[dict(famille='parametres_seuls')])
        else:
            hb = self.hyps_biblio(o)
            evaluer(hb, o, self.lignes, self.model, len(self.lignes), portes_initiales=pi)
            hs, rap = superviser(o, ctx, self.lignes, self.model, len(self.lignes), self.memoire, contexte,
                                 self.version[o['id']], pi, self.j, tuple(self.retrogradees),
                                 sans_superviseur=self.sans_superviseur)
            hyps = hb + hs
        for h in hyps:
            h.version = self.version[o['id']]; h.__dict__.setdefault('t_inv', len(self.lignes))
            h.__dict__.setdefault('famille', h.parent.split('/')[-1])
        rap.update(objet=o['id'], version=self.version[o['id']], step=len(self.lab.rows))
        self.rapports_superviseur.append(rap)
        self.j.ecrire('superviseur_rapport', **rap)
        self.n_generees += len(hyps)
        surv = [h for h in hyps if h.statut == 'survivante']
        self.inventions.append(dict(step=len(self.lab.rows), objet=o['id'], version=self.version[o['id']],
                                    contexte=ctx, generees=len(hyps), survivantes=len(surv)))
        self.j.ecrire('invention', step=len(self.lab.rows), objet=o['id'], version=self.version[o['id']], contexte=ctx,
                      generees=len(hyps), survivantes=len(surv),
                      classes=[dict(n=len(c['membres']), score=round(c['score'], 2), rep=c['representant'].id,
                                    programme=c['representant'].programme, mutations=c['representant'].mutations)
                               for c in classes_equivalence(hyps)[:6]],
                      exemples_rejets=[dict(id=h.id, mutations=h.mutations, preuve=h.preuve_rejet)
                                       for h in hyps if h.statut == 'rejetee'][:8])
        self.hyps[o['id']] = hyps

    def mettre_a_jour_hypotheses(self):
        cons = O.contradictions_v4(self.objs, self.lignes)
        change = False
        for o in self.objs:
            co = [c for c in cons if c['objet'] == o['id']]
            H = self.hyps.get(o['id'])
            if H is None:
                if co:
                    self.inventer(o, cons); change = True
                continue
            avant = {h.id for h in H if h.statut == 'survivante'}
            evaluer([h for h in H if h.statut == 'survivante'], o, self.lignes, self.model, 10 ** 9,
                    portes_initiales=O.portes_fermees(self.model, self.lab.images[0]))
            apres = {h.id for h in H if h.statut == 'survivante'}
            fam_perdues = Counter(); fam_gardees = Counter()
            for h in H:
                if h.id in apres:
                    fam_gardees[h.__dict__.get('famille')] += 1
                if h.id in avant - apres:
                    fam_perdues[h.__dict__.get('famille')] += 1
                    self.memoire.enregistrer(f"{self.game}_N{self.level}_{o['id']}", h, h.version, h.__dict__.get('famille'))
                    self.j.ecrire('rejet_prospectif', step=len(self.lab.rows), id=h.id, mutations=h.mutations,
                                  preuve=h.preuve_rejet, t_inv=h.__dict__.get('t_inv'))
            for f in fam_perdues:
                if not fam_gardees[f]:
                    self.stagnation[f] += 1
                    if self.stagnation[f] >= 2 and f not in self.retrogradees:
                        self.retrogradees.add(f)
                        self.j.ecrire('superviseur', objet=o['id'], famille=f, decision='retrogradee_stagnation',
                                      versions_refutees=self.stagnation[f])
            self.memoire.sauver()
            if avant != apres:
                change = True
            if not apres and co:
                self.inventer(o, cons); change = True
        return change

    # ------------------------------------------------------------------ modèles du monde
    def modeles(self):
        """Dict nom -> (ModeleEtendu, poids, meta). Varie l'objet principal (le plus contredit), portée sur dalles."""
        tracked = [o for o in self.objs if self.hyps.get(o['id'])]
        base_autos = []; varies = None
        for o in tracked:
            cl = self.representants(self.hyps[o['id']])
            if not cl:
                continue
            if varies is None:
                varies = (o, cl[:K_CLASSES])
            else:
                base_autos.append((o, dict(cl[0]['representant'].programme, portee_dalles=True)))
        out = {}
        if varies is None:
            out['v4'] = (ModeleEtendu(self.model, base_autos), 1.0, dict(desc='v4 (objets non revendiqués = décor)'))
            if 'franchissable' not in self.refutes and self.certificat_actif:
                out['franchissable'] = (ModeleEtendu(self.model, base_autos, portes={'franchissable': True}),
                                        math.exp(-0.3), dict(desc='réparation certificat : porte dessinée fermée franchissable'))
            return out
        o, cl = varies; best = cl[0]['score']
        for c in cl:
            rep = c['representant']
            for portee in (True, False):
                prog = dict(rep.programme, portee_dalles=portee)
                nom = f"{rep.id}|dalles={portee}"
                w = math.exp(-(c['score'] - best)) * 0.5
                out[nom] = (ModeleEtendu(self.model, [(o, prog)] + base_autos), w,
                            dict(desc=str({k: v for k, v in prog.items() if v not in (None, 0, 'id')}), hyp=rep.id,
                                 objet=o['id'], portee=portee))
        if 'franchissable' not in self.refutes and self.certificat_actif:
            rep = cl[0]['representant']
            out['franchissable'] = (ModeleEtendu(self.model, [(o, dict(rep.programme, portee_dalles=False))] + base_autos,
                                                 portes={'franchissable': True}), 0.5 * math.exp(-0.3),
                                    dict(desc='réparation certificat : porte dessinée fermée franchissable', hyp=rep.id))
        return out

    def representants(self, H):
        """Classes observationnelles scindées par comportement contrefactuel pertinent pour le plan
        (réinitialisation, destruction, fin de couloir, effet) : deux hypothèses indiscernables sur les données
        mais qui prescrivent des plans différents restent deux modèles."""
        out = []
        for c in classes_equivalence(H):
            groupes = {}
            for m in c['membres']:
                p = m.programme
                k = (p['reinit'], p['destruction'], p.get('fin_couloir'), p['effet'] if p['effet'] != 'route_latente' else 'couloir')
                if k not in groupes:
                    groupes[k] = m
            for m in groupes.values():
                out.append(dict(representant=m, membres=c['membres'], score=m.score))
        out.sort(key=lambda c: c['score'])
        return out

    def etats(self, mods):
        out = {}
        for nom, (M, w, meta) in mods.items():
            autos = []
            for o, prog in M.autos:
                autos.append(etat_final(prog, o, self.lignes, self.model,
                                        O.portes_fermees(self.model, self.lab.images[0])))
            out[nom] = M.initial_depuis(self.s5, autos)
        return out

    # ------------------------------------------------------------------ certificats
    def certificat(self):
        """Accessibilité relâchée (toutes portes ouvertes) depuis la pose du joueur : dalles hors d'atteinte."""
        m = self.model; seen = {self.s5[0]}; todo = [self.s5[0]]
        while todo:
            p = todo.pop()
            for dx, dy in m.dirs:
                q = (p[0] + dx, p[1] + dy)
                if q in m.node_set and q not in seen:
                    seen.add(q); todo.append(q)
        hors = sorted(t for t in m.triggers if t not in seen)
        but = sorted(g for g in m.goals if g not in seen)
        T = len(self.lignes)
        portes_jamais_ouvertes = sorted(d for g in m.groups if g['kind'] == 'toggle' for d in g['doors']
                                        if all(tuple(d) in map(tuple, L['portes_fermees']) for L in self.lignes))
        reparations = [
            dict(id='declencheur_distant', mecanisme='un occupant non joueur (objet autonome) atteint la dalle',
                 lien='hypothèses objet avec dalles=True', statut='a_tester' if self.hyps else 'sans_candidat_objet'),
            dict(id='declencheur_temporel', mecanisme='la porte s\'ouvre seule après k coups',
                 statut=f'réfutée pour k <= {T} (portes {portes_jamais_ouvertes} jamais ouvertes)' if portes_jamais_ouvertes
                 else 'non réfutée', valeur_plan='nulle si k > budget restant'),
            dict(id='etat_persistant', mecanisme='un événement antérieur a basculé un état caché',
                 statut='non testable sans prédiction précise ; conservée, priorité basse'),
            dict(id='condition_cachee', mecanisme='dalle/condition invisible ailleurs',
                 statut='non testable sans prédiction précise ; conservée, priorité basse'),
            dict(id='franchissable', mecanisme='rendu ≠ état : porte dessinée fermée mais franchissable',
                 statut='réfutée' if 'franchissable' in self.refutes else 'a_tester'),
        ]
        return dict(step=len(self.lab.rows), dalles_hors_atteinte_joueur=hors, but_hors_atteinte=but,
                    noeuds_atteignables=len(seen), reparations=reparations)

    def verifier_franchissable(self, L, image_avant):
        """Réfute 'franchissable' si le joueur a tenté d'entrer dans une porte de bascule dessinée fermée et est resté."""
        if L['action'] not in (1, 2, 3, 4) or L['effectif']:
            return
        dx, dy = self.model.dirs[L['action'] - 1]; q = (L['joueur_avant'][0] + dx, L['joueur_avant'][1] + dy)
        g = self.model.doors.get(q)
        if g is not None and self.model.groups[g]['kind'] == 'toggle' and q in O.portes_fermees(self.model, image_avant):
            if 'franchissable' not in self.refutes:
                self.refutes['franchissable'] = dict(step=L['t'], porte=q, action=L['action'],
                                                     observe='joueur immobile devant la porte dessinée fermée')
                self.j.ecrire('rejet_intervention', step=L['t'], hypothese='franchissable', preuve=self.refutes['franchissable'])

    # ------------------------------------------------------------------ décision
    def exploration(self, M, s):
        best = None
        for target in sorted(self.model.nodes):
            r = M.nav(s, target, maxsteps=40)
            if r and r[1] and self.lab.economy.admissible(r[1][:1]):
                sc = (self.visites[('pose', target)], 0 if target in self.model.triggers else 1, len(r[1]), target)
                if best is None or sc < best[0]:
                    best = (sc, r[1])
        return best[1] if best else None

    def decider(self, mods, etats):
        poids = {n: w for n, (M, w, meta) in mods.items()}
        mm = {n: M for n, (M, w, meta) in mods.items()}
        t0 = time.monotonic()
        for n in mm:
            if n not in self.plans:
                r = mm[n].solve(etats[n], max_vies=5, max_noeuds=self.max_noeuds)
                self.plans[n] = r.get('actions')
                self.j.ecrire('plan', step=len(self.lab.rows), modele=n, status=r['status'],
                              longueur=len(r['actions']) if r.get('actions') else None, noeuds=r.get('nodes'))
        faisables = {n: p for n, p in self.plans.items() if p and n in mm}
        if not faisables and not self.certificat_actif:
            self.certificat_actif = True
            self.j.ecrire('certificat_inaccessibilite', **self.certificat())
            return None, 'recalcul', None
        ordre = sorted(faisables, key=lambda n: -poids[n])
        ref = faisables[ordre[0]] if ordre else None
        premier = {p[0] for p in faisables.values()}
        if self.mode in ('sans_experience',) or (self.mode in ('complet', 'parametres') and faisables and len(premier) == 1):
            if ref:
                return [ref[0]], 'plan:' + ordre[0], None
        if self.mode in ('complet', 'parametres', 'gain_info', 'aleatoire') and len(mm) > 1:
            top = max(mm, key=lambda n: poids[n])
            navs = []
            for c in sorted(set(self.model.triggers) | set(self.model.goals)):
                r = mm[top].nav(etats[top], c, maxsteps=40)
                if r and r[1]:
                    navs.append((c, r[1]))
            mode = {'complet': 'risque_plan', 'parametres': 'risque_plan'}.get(self.mode, self.mode)
            choix, evals = choisir(mode, mm, etats, poids, faisables, navs, self.lab.economy, plan_ref=ref,
                                   graine=self.graine + len(self.lab.rows))
            if choix:
                self.j.ecrire('experience', step=len(self.lab.rows), mode=mode, choix=choix, n_candidats=len(evals),
                              secondes=round(time.monotonic() - t0, 2))
                return list(choix['seq']), 'experience:' + choix['nom'], choix
        if ref:
            return [ref[0]], 'plan:' + ordre[0], None
        top = max(mm, key=lambda n: poids[n])
        ex = self.exploration(mm[top], etats[top])
        if ex:
            return ex[:1], 'exploration', None
        return None, 'aucune_action', None

    # ------------------------------------------------------------------ délégation à la v4
    def deleguer_v4(self):
        """La v4 joue tant que sa théorie n'est contredite par aucun objet non revendiqué (non-régression :
        sur les familles connues, l'inventeur n'intervient pas). Au premier écart, la main passe à l'inventeur."""
        from boucle_v4.agent_fantome import run as v4run
        lab = self.lab; jeu = self; orig = lab.play

        class Releve(Exception):
            pass

        def play(a, purpose='experience'):
            r = orig(a, 'v4:' + purpose)
            if lab.finished:
                return r
            try:
                from .analyse_trace import modele_depuis_trace
                acts = [row['action'] for row in lab.rows]
                m, _ = modele_depuis_trace(lab.images, acts)
            except Exception:
                return r
            if not m.goals:
                jeu.non_reconnu = True
                raise Releve('structure non reconnue par la v4 g50t (pas de but ponctuel)')
            objs = O.objets_initiaux(m, lab.images[0])
            for o in objs:
                q = O.localiser(o, lab.image, o['pos0'])
                if q != o['pos0']:
                    jeu.releve = dict(step=len(lab.rows), objet=o['id'], pos0=o['pos0'], observe=q)
                    raise Releve('écart objet non revendiqué')
            return r
        lab.play = play
        try:
            r = v4run(self.level, None, self.out / 'v4', self.budget, 10 ** 9, lab=lab)   # bornes v4 en nœuds (bornes.py)
        finally:
            lab.play = orig
        self.j.ecrire('delegation_v4', resultat={k: r.get(k) for k in ('victory', 'actions', 'reason')},
                      releve=getattr(self, 'releve', None))
        return r

    # ------------------------------------------------------------------ boucle
    def run(self, delegation=True):
        t0 = time.monotonic(); raison = 'budget'; plan_final = []
        try:
            if delegation:
                self.releve = None; self.non_reconnu = False
                self.deleguer_v4()
                if self.non_reconnu:
                    raison = 'non_reconnu'; raise StopIteration
                if self.lab.won or self.lab.finished or self.releve is None:
                    raison = 'v4_seule'; raise StopIteration
            if self.lab.rows:
                from .analyse_trace import modele_depuis_trace
                self.model, _ = modele_depuis_trace(self.lab.images, [row['action'] for row in self.lab.rows])
            else:
                self.model = self.identifier()
            if self.model is None:
                raison = 'perception_non_identifiee'; raise StopIteration
            self.j.ecrire('geometrie', description=self.model.describe())
            self.init_suivi()
            if self.biblio:
                for o in self.objs:
                    hb = self.hyps_biblio(o)
                    if hb:
                        evaluer(hb, o, self.lignes, self.model, len(self.lignes),
                                portes_initiales=O.portes_fermees(self.model, self.lab.images[0]))
                        self.hyps[o['id']] = hb; self.n_generees += len(hb)
                        self.mecanismes_biblio += [h.__dict__['biblio'] for h in hb]
                self.j.ecrire('bibliotheque_chargee', mecanismes=[m['id'] for m in self.biblio.mecanismes('valide')],
                              objets=[o['id'] for o in self.objs])
            self.mettre_a_jour_hypotheses()
            cert_ecrit = False; derniere_pred = {}
            while len(self.lab.rows) < self.budget and not self.lab.finished:
                if time.monotonic() - t0 > self.seconds:
                    raison = 'temps'; break
                mods = self.modeles(); ets = self.etats(mods)
                if not self.engagement:
                    seq, but, choix = self.decider(mods, ets)
                    if but == 'recalcul':
                        continue
                    if not seq:
                        raison = 'aucune_action'; break
                    self.engagement = list(seq); self.engagement_but = but
                a = self.engagement.pop(0)
                if not self.lab.economy.admissible([a]):
                    raison = 'jauge_insuffisante'; break
                preds = {n: mods[n][0].observation(mods[n][0].step_state(ets[n], a)) for n in mods}
                image_avant = self.lab.image.copy()
                self.lab.play(a, self.engagement_but)
                plan_final.append(a)
                if self.lab.won:
                    # image terminale = niveau suivant : exclue de l'induction (comme la v4)
                    self.j.ecrire('victoire', step=len(self.lab.rows), action=a); break
                self.avancer_suivi(len(self.lab.rows))
                L = self.lignes[-1]
                self.verifier_franchissable(L, image_avant)
                # exception observée (comme les contre-exemples de pose v4) : si AUCUN modèle n'a prédit la pose,
                # la transition observée est mémorisée et prime ensuite sur la loi (évite les boucles)
                if all(preds[n] == ('mort',) or preds[n][0] != self.poses[-1] for n in preds) and a in (1, 2, 3, 4):
                    M0 = next(iter(mods.values()))[0]; s0 = next(iter(ets.values()))
                    occ = M0.occupants(s0[0], s0[1], s0[2], s0[5])
                    k = (L['joueur_avant'], a, s0[4], frozenset(t for t in self.model.triggers if t in occ))
                    self.model.memo_transitions = getattr(self.model, 'memo_transitions', {})
                    self.model.memo_transitions[k] = self.poses[-1]
                    self.j.ecrire('exception_observee', step=L['t'], cle=k, observe=self.poses[-1],
                                  predit={n: preds[n][0] if preds[n] != ('mort',) else 'mort' for n in list(preds)[:4]})
                    self.plans = {}
                obs = (self.poses[-1], tuple(L['objets'][o['id']][1] for o, prog in next(iter(mods.values()))[0].autos),
                       tuple(sorted(map(tuple, L['portes_fermees']))))
                ok = {n: self._accord(mods[n][0], preds[n], obs) for n in mods}
                confirmes = sorted(n for n in ok if ok[n]); refutes = sorted(n for n in ok if not ok[n])
                if not confirmes and self.hyps:
                    self.sans_loi += 1
                if confirmes and refutes:
                    self.interventions.append(dict(step=len(self.lab.rows), action=a, but=self.engagement_but,
                                                   confirmes=confirmes, refutes=refutes))
                    # une réfutation de modèle vaut pour sa version : elle est journalisée (interventions),
                    # la mise à jour des hypothèses fait le reste ; pas de bannissement par nom (les noms sont réutilisés)
                self.j.ecrire('transition', step=len(self.lab.rows), action=a, but=self.engagement_but,
                              observe=obs, predictions={n: preds[n] for n in list(preds)[:6]},
                              accord=ok, jauge=self.lab.economy.last,
                              cout_borne=self.lab.economy.cost_upper([a]) if self.lab.economy.valid else None)
                for n in refutes:
                    self.plans.pop(n, None)
                for n in confirmes:
                    if self.plans.get(n) and self.plans[n][:1] == [a]:
                        self.plans[n] = self.plans[n][1:]
                    else:
                        self.plans.pop(n, None)
                if refutes:
                    self.engagement = []
                if self.mettre_a_jour_hypotheses():
                    self.plans = {}; self.engagement = []
                self.plans = {n: p for n, p in self.plans.items() if n not in self.refutes}
                if self.t_premier_modele_correct is None and confirmes and not refutes and self.hyps:
                    pass
                derniere_pred = ok
        except StopIteration:
            pass
        except BudgetInconnu as e:
            raison = 'abstention_economie'; self.j.ecrire('economie_stop', message=str(e))
        except Exception as e:
            raison = 'exception_contenue'
            self.j.ecrire('exception', nom=type(e).__name__, message=str(e), tb=traceback.format_exc())
        return self.bilan(raison, time.monotonic() - t0, plan_final)

    def _accord(self, M, pred, obs):
        if pred == ('mort',):
            return False
        p, vis, fer = pred
        return p == obs[0] and tuple(vis) == tuple(obs[1][:len(vis)]) and tuple(fer) == tuple(obs[2])

    # ------------------------------------------------------------------ bilan / bibliothèque
    def bilan(self, raison, secondes, plan_final):
        lab = self.lab
        val = []
        for oid, H in self.hyps.items():
            surv = [h for h in H if h.statut == 'survivante']
            if not surv:
                continue
            cl = classes_equivalence(H); h = cl[0]['representant']
            t_inv = h.__dict__.get('t_inv', 0)
            n_pros = sum(1 for t in h.explique if t > t_inv)
            # portée validée par intervention : un modèle « dalles=True » confirmé quand « dalles=False » est réfuté
            iv = [i for i in self.interventions if any(c.startswith(h.id + '|') for c in i['confirmes'])
                  and any(r.startswith(h.id + '|') or r == 'franchissable' or not r.startswith(h.id) for r in i['refutes'])]
            portee = None
            if any(f"{h.id}|dalles=True" in i['confirmes'] and f"{h.id}|dalles=False" in i['refutes'] for i in self.interventions):
                portee = True
            elif any(f"{h.id}|dalles=False" in i['confirmes'] and f"{h.id}|dalles=True" in i['refutes'] for i in self.interventions):
                portee = False
            prog = dict(h.programme, portee_dalles=portee)
            preuves = dict(nouveaute=nouveaute(prog), n_pred_prospectives=n_pros,
                           interventions=[dict(step=i['step'], action=i['action'], refutes=i['refutes'][:4]) for i in iv][:6],
                           mutations=h.mutations, classe_taille=len(cl[0]['membres']), n_classes=len(cl))
            entree = dict(objet=oid, hypothese=h.id, programme=prog, preuves=preuves,
                          statut='survivante (non prouvée)')
            if self.biblio and lab.won and self.mode in ('complet', 'gain_info', 'aleatoire', 'sans_experience'):
                mid = h.__dict__.get('biblio')
                if mid:   # mécanisme réutilisé : on note le transfert, on ne crée pas de nouveau gabarit
                    self.biblio.marquer_transfert(mid, f'{self.game}_N{self.level}', True,
                                                  dict(actions=len(lab.rows), generees=self.n_generees,
                                                       n_pred_prospectives=n_pros))
                    m = next(x for x in self.biblio.d['mecanismes'] if x['id'] == mid)
                    entree['bibliotheque'] = dict(id=mid, statut=m['statut'], reutilise=True)
                else:
                    m = self.biblio.proposer(prog, preuves, f'{self.game}_N{self.level}_{self.mode}')
                    entree['bibliotheque'] = dict(id=m['id'], statut=m['statut'], reutilise=False)
            val.append(entree)
        r = dict(game=self.game, level=self.level, mode=self.mode, victoire=lab.won, actions=len(lab.rows),
                 secondes=round(secondes, 2), raison='victoire_reelle' if lab.won else ('defaite_reelle' if lab.finished else raison),
                 injecte=lab.injected, hypotheses_generees=self.n_generees,
                 hypotheses_refutees=sum(1 for H in self.hyps.values() for h in H if h.statut == 'rejetee'),
                 refutations_par_intervention=len(self.interventions), inventions=self.inventions,
                 interventions=self.interventions[:30], refutes_monde=self.refutes, mecanismes=val,
                 mecanismes_biblio_utilises=sorted(set(self.mecanismes_biblio)),
                 economie=dict(capacite=lab.economy.report().get('capacity_interval'),
                               jauge_finale=getattr(lab.economy, "last", None)),  # C (CW-447) : EconomieP1 n'a pas `last`
                 actions_liste=[row['action'] for row in lab.rows], buts=[row['purpose'] for row in lab.rows],
                 code_sha256=sha_code(), superviseur=self.rapports_superviseur[-6:],
                 familles_retrogradees=sorted(self.retrogradees),
                 defauts_ARC=dict(
                     effet_local_sans_regle_globale=dict(pas_sans_aucun_modele_correct=self.sans_loi,
                                                         note='pose resynchronisée sans loi qui la prédise'),
                     mauvais_niveau_abstraction=dict(
                         hyp_bibliotheque_plaquees_refutees=sum(1 for H in self.hyps.values() for h in H
                                                                if h.__dict__.get('biblio') and h.statut == 'rejetee'),
                         famille_parametre_refutee_en_prospectif=sum(1 for H in self.hyps.values() for h in H
                                                                     if h.__dict__.get('famille') == 'parametre_miroir'
                                                                     and h.statut == 'rejetee' and (h.preuve_rejet or {}).get('t', 0) > h.__dict__.get('t_inv', 0))),
                     victoire_sans_regle_reutilisable=bool(lab.won and not any(
                         (v.get('bibliotheque') or {}).get('statut') in ('valide', 'transfere')
                         or (v.get('bibliotheque') or {}).get('reutilise') for v in val))))
        self.j.ecrire('bilan', **{k: v for k, v in r.items() if k not in ('actions_liste',)})
        p = self.out / 'bilan.json'
        if p.exists():
            p = self.out / f'bilan_{time.strftime("%H%M%S")}.json'
        p.write_text(json.dumps(r, indent=1, default=str, ensure_ascii=False))
        return r


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default='g50t'); ap.add_argument('--level', type=int, required=True)
    ap.add_argument('--jeux', default='jeux'); ap.add_argument('--output', required=True)
    ap.add_argument('--mode', default='complet', choices=MODES); ap.add_argument('--budget', type=int, default=150)
    ap.add_argument('--seconds', type=float, default=900); ap.add_argument('--biblio'); ap.add_argument('--graine', type=int, default=0)
    a = ap.parse_args()
    r = Agent(a.game, a.level, a.jeux, a.output, a.mode, a.budget, a.seconds, a.biblio, a.graine).run()
    print(json.dumps({k: r[k] for k in ('game', 'level', 'mode', 'victoire', 'actions', 'secondes', 'raison',
                                         'hypotheses_generees', 'hypotheses_refutees', 'refutations_par_intervention')}))


if __name__ == '__main__':
    main()
