"""Contrôle positif « une famille retirée » (demande du coordinateur) — hors ligne, sur traces de développement g50t.

On retire une famille dont la vérité est connue, on regarde si l'inventeur la retrouve seul par modifications
structurelles des familles restantes, sur les observations enregistrées (0 coup réel).
Familles retirées : A « porte maintenue par occupation » (held), B « bascule à l'entrée » (toggle),
C « fantôme qui rejoue le trajet de la vie précédente » (mémoire).
La vérité (groupes v4) ne sert QU'À noter le résultat (rang, fausses découvertes), jamais à générer ou filtrer.

DSL porte (A, B) : type ∈ {occupation, inverse, entree_bascule, verrou, minuterie(k)} ; lieu ∈ tous les nœuds
(relation locale → distante, M4) ; occupants ∈ {joueur, joueur+fantomes} (portée, M7) ; délai ∈ {0,1} (M6).
Point de départ = la famille porte restante (A : bascule ; B : maintenue) ; mutations M3 (type de déclencheur),
M2 (négation = précondition), M5 (verrou = état persistant), M4 (lieu), M6, M7.
DSL fantôme (C) : objet apparu après ACTION5 ; source de route ∈ {route propre induite (M5), trajet d'un autre
objet pendant la vie précédente (M4+M5), miroir du joueur (M1), couloir (M8), poursuite (M4)} ;
horloge ∈ {coup effectif, tout coup} (M3) ; accumulation ∈ {remplace, capacité c ∈ 1..3 clear/fifo} (M5/M7).
"""
import json, math, sys
from pathlib import Path
from itertools import product
import numpy as np

from .analyse_trace import modele_depuis_trace, poses_joueur, charger
from . import objets as O

DEV = Path(__file__).resolve().parents[3] / 'references/astra4/livraison_astra4/developpement/reset_g50t'
LAM = 0.1


def fantomes_observes(model, image, pj):
    """Poses (sur nœuds) des composantes de la forme du joueur, autres que le joueur, d'une couleur ≠ joueur."""
    out = set()
    for p in model.nodes:
        if p == pj:
            continue
        cols = [int(image[p[1] + v, p[0] + u]) for u, v in model.shape]
        c = max(set(cols), key=cols.count)
        if c not in (model.color, model.floor, 0) and cols.count(c) == len(model.shape):
            # même empreinte creuse que le joueur : le trou central n'a pas la couleur c
            out.add((p, c))
    return out


def donnees(trace):
    images, actions = charger(trace)
    model, _ = modele_depuis_trace(images, actions)
    poses = poses_joueur(model, images, 0)
    if json.load(open(Path(trace) / 'partie.json')).get('victory'):
        images, actions, poses = images[:-1], actions[:-1], poses[:-1]   # image terminale = niveau suivant
    for t in range(len(poses)):
        if poses[t] is None:
            poses[t] = poses[t - 1] if t else model.start
    return model, images, actions, poses


# ----------------------------------------------------------------------------------------- portes (A, B)
def etat_porte_observe(model, image, d, couleur):
    n = sum(image[d[1] + v, d[0] + u] == couleur for u, v in model.shape)
    return n >= len(model.shape) * .5  # fermée


def simuler_porte(prog, occs, ferme0):
    """occs[t] = ensemble des nœuds occupés après le pas t (t=0 : initial). Rend la liste fermée/ouverte prédite."""
    typ, lieu, delai, k = prog['type'], prog['lieu'], prog['delai'], prog.get('k')
    ferme = ferme0; out = [ferme0]; verrou = False
    for t in range(1, len(occs)):
        o_now = lieu in occs[t - delai] if t - delai >= 0 else False
        o_prev = lieu in occs[t - 1 - delai] if t - 1 - delai >= 0 else False
        if typ == 'occupation':
            ferme = not o_now
        elif typ == 'inverse':
            ferme = o_now
        elif typ == 'entree_bascule':
            if o_now and not o_prev:
                ferme = not ferme
        elif typ == 'verrou':
            verrou = verrou or o_now; ferme = not verrou
        elif typ == 'minuterie':
            ferme = ferme0 if (t // k) % 2 == 0 else not ferme0
        out.append(ferme)
    return out


COUT_TYPE = {'occupation': 2, 'inverse': 3, 'entree_bascule': 2, 'verrou': 3, 'minuterie': 3}


def candidats_porte(model, famille_restante):
    nl = math.log2(max(2, len(model.nodes)))
    out = []
    for typ, lieu, occ, delai in product(COUT_TYPE, model.nodes, ('joueur', 'joueur+fantomes'), (0, 1)):
        ks = range(1, 11) if typ == 'minuterie' else [None]
        for k in ks:
            if typ == 'minuterie' and (lieu != model.nodes[0] or occ != 'joueur'):
                continue  # la minuterie ne dépend ni du lieu ni des occupants : une seule instance par k
            muts = []
            if typ != famille_restante:
                muts.append({'occupation': 'M3:declencheur(entree->occupation)', 'inverse': 'M2:precondition(negation)',
                             'entree_bascule': 'M3:declencheur(occupation->entree)', 'verrou': 'M5:etat_persistant(verrou)',
                             'minuterie': 'M3:declencheur_temporel(k)'}[typ])
            if typ != 'minuterie':
                muts.append('M4:lieu_distant')
            if occ == 'joueur+fantomes':
                muts.append('M7:portee(occupants+fantomes)')
            if delai:
                muts.append('M6:delai(1)')
            cout = COUT_TYPE[typ] + (0 if typ == famille_restante else 1) + (nl if typ != 'minuterie' else 0) + \
                (1 if occ == 'joueur+fantomes' else 0) + 2 * delai + (math.log2(10) if k else 0)
            out.append(dict(type=typ, lieu=lieu, occupants=occ, delai=delai, k=k, mutations=muts, cout=cout))
    return out


def controle_porte(kind, famille_restante, traces):
    """Pour chaque groupe de type `kind` présent dans les traces : invention sur observations, rang de la vérité."""
    res = []
    for tr in traces:
        model, images, actions, poses = donnees(tr)
        groupes = [g for g in model.groups if g['kind'] == kind]
        if not groupes:
            continue
        fant = [fantomes_observes(model, im, poses[t]) for t, im in enumerate(images)]
        occ_j = [{poses[t]} for t in range(len(images))]
        occ_jf = [{poses[t]} | {p for p, c in fant[t]} for t in range(len(images))]
        cands = candidats_porte(model, famille_restante)
        for g in groupes:
            for d in g['doors']:
                obs = [etat_porte_observe(model, im, d, g['color']) for im in images]
                # contradiction de la base « porte = décor fermé immobile »
                contra = [t for t in range(1, len(obs)) if obs[t] != obs[0]]
                evals = []
                for c in cands:
                    occs = occ_jf if c['occupants'] == 'joueur+fantomes' else occ_j
                    pr = simuler_porte(c, occs, obs[0])
                    # pas jugés : ceux où aucun occupant ne cache la porte (occupant dans la porte => rendu ouvert)
                    err = [t for t in range(1, len(obs)) if pr[t] != obs[t] and d not in occ_jf[t]]
                    evals.append(dict(c, erreurs=len(err), premier_contre=err[0] if err else None,
                                      score=len(err) + LAM * c['cout']))
                surv = sorted([e for e in evals if e['erreurs'] == 0], key=lambda e: e['score'])
                vrai_type = {'held': 'occupation', 'toggle': 'entree_bascule'}[kind]
                vraies = set(map(tuple, g['triggers']))

                def est_vrai(e):
                    return e['type'] == vrai_type and tuple(e['lieu']) in vraies
                rang = next((i + 1 for i, e in enumerate(surv) if est_vrai(e)), None)
                # équivalence : mêmes prédictions sur toutes les données
                tete = surv[0] if surv else None
                fausses = [e for e in surv if not est_vrai(e) and e['score'] <= (surv[rang - 1]['score'] if rang else 1e9)]
                res.append(dict(trace=Path(tr).name, groupe=dict(couleur=g['color'], porte=d, dalles=g['triggers']),
                                contradictions_base=len(contra), generes=len(cands), survivants=len(surv),
                                retrouvee=bool(rang), rang_verite=rang, tete=_court(tete), vrai_en_tete=bool(tete and est_vrai(tete)),
                                fausses_decouvertes_classees_avant_ou_egales=len(fausses),
                                exemples_fausses=[_court(e) for e in fausses[:3]],
                                mutations_verite=next((e['mutations'] for e in surv if est_vrai(e)), None)))
    return res


def _court(e):
    if not e:
        return None
    return {k: e[k] for k in ('type', 'lieu', 'occupants', 'delai', 'k', 'erreurs', 'score') if k in e}


# ----------------------------------------------------------------------------------------- fantôme (C)
def controle_fantome(traces):
    res = []
    for tr in traces:
        model, images, actions, poses = donnees(tr)
        if 5 not in actions:
            continue
        fant = [fantomes_observes(model, im, poses[t]) for t, im in enumerate(images)]
        obs = [frozenset(p for p, c in f) for f in fant]
        if not any(obs):
            continue
        # vies (trajets du joueur entre ACTION5)
        cands = []
        for src, hor, acc in product(('trajet_vie_precedente', 'route_propre', 'miroir_joueur', 'couloir', 'immobile_au_depart'),
                                     ('effectif', 'tout'), ('remplace', 'cap1_clear', 'cap2_clear', 'cap3_clear', 'cap2_fifo', 'cap3_fifo')):
            muts = {'trajet_vie_precedente': ['M5:etat_persistant(route)', 'M4:relation(trajet_autre_objet)'],
                    'route_propre': ['M5:etat_persistant(route_induite)'], 'miroir_joueur': ['M1:relation_miroir'],
                    'couloir': ['M8:composition(autonome+rail)'], 'immobile_au_depart': ['M7:portee(apparition_au_depart)']}[src]
            muts = muts + (['M3:declencheur_temporel'] if hor == 'tout' else ['M2:precondition(deplacement_effectif)'])
            if acc != 'remplace':
                muts.append(f'M5/M7:accumulation({acc})')
            cout = {'trajet_vie_precedente': 5, 'route_propre': 6, 'miroir_joueur': 4, 'couloir': 4, 'immobile_au_depart': 2}[src] + \
                (1 if hor == 'tout' else 2) + (0 if acc == 'remplace' else 3)
            cands.append(dict(source=src, horloge=hor, accumulation=acc, mutations=muts, cout=cout))
        evals = []
        for c in cands:
            pr = simuler_fantomes(c, model, actions, poses, obs)
            err = [t for t in range(1, len(obs)) if pr[t] is not None and pr[t] != obs[t]]
            nonp = sum(1 for t in range(1, len(obs)) if pr[t] is None)
            evals.append(dict(c, erreurs=len(err), non_predits=nonp, premier_contre=err[0] if err else None,
                              score=len(err) + LAM * c['cout'] + nonp / 10))
        surv = sorted([e for e in evals if e['erreurs'] == 0], key=lambda e: e['score'])

        def est_vrai(e):
            return e['source'] == 'trajet_vie_precedente' and e['horloge'] == 'effectif' and \
                e['accumulation'] in (f"cap{model.capacity}_clear", 'remplace' if model.capacity == 1 else 'x')
        rang = next((i + 1 for i, e in enumerate(surv) if est_vrai(e)), None)
        fausses = [e for e in surv if not est_vrai(e) and e['score'] <= (surv[rang - 1]['score'] if rang else 1e9)]
        res.append(dict(trace=Path(tr).name, n_action5=actions.count(5), capacite_hud=model.capacity,
                        generes=len(cands), survivants=len(surv), retrouvee=bool(rang), rang_verite=rang,
                        tete={k: surv[0][k] for k in ('source', 'horloge', 'accumulation', 'score')} if surv else None,
                        fausses_decouvertes_classees_avant_ou_egales=len(fausses),
                        exemples_fausses=[{k: e[k] for k in ('source', 'horloge', 'accumulation', 'score')} for e in fausses[:3]],
                        survivants_detail=[{k: e[k] for k in ('source', 'horloge', 'accumulation', 'score', 'non_predits')} for e in surv[:5]]))
    return res


def simuler_fantomes(c, model, actions, poses, obs):
    """Ensemble prédit des poses de fantômes après chaque pas ; None = pas de prédiction (route propre inconnue)."""
    src, hor, acc = c['source'], c['horloge'], c['accumulation']
    cap = 1 if acc == 'remplace' else int(acc[3]); pol = 'clear' if acc == 'remplace' or acc.endswith('clear') else 'fifo'
    if acc == 'remplace':
        pol = 'fifo'
    routes = []; record = [model.start]; idx = 0; out = [frozenset()]
    vu = {}  # route propre : poses observées par rang depuis la dernière ACTION5
    for t in range(1, len(poses)):
        a = actions[t - 1]; eff = a in (1, 2, 3, 4) and poses[t] != poses[t - 1]
        if a == 5:
            if src in ('trajet_vie_precedente', 'route_propre', 'couloir', 'miroir_joueur', 'immobile_au_depart'):
                nouvelle = tuple(record)
                if len(record) <= 1:
                    pass                 # vie sans déplacement : rien à mémoriser
                elif len(routes) >= cap and pol == 'clear':
                    routes = []          # vidage : la nouvelle trace n'est pas gardée
                elif len(routes) >= cap:
                    routes = routes[1:] + [nouvelle]
                else:
                    routes.append(nouvelle)
            record = [model.start]; idx = 0; vu = {}
        else:
            if eff:
                record.append(poses[t])
            if eff or (hor == 'tout' and a in (1, 2, 3, 4)):
                idx += 1
        if src == 'trajet_vie_precedente':
            pr = frozenset(r[min(idx, len(r) - 1)] for r in routes)
        elif src == 'immobile_au_depart':
            pr = frozenset(model.start for r in routes) if routes else frozenset()
        elif src == 'route_propre':
            # la route n'est connue que par ce qui a déjà été vu au même rang : pas de prédiction sinon
            pr = None if routes and idx > 0 else frozenset(model.start for r in routes)
        elif src == 'miroir_joueur':
            pr = frozenset((2 * model.start[0] - poses[t][0], poses[t][1]) for r in routes) if routes else frozenset()
        else:  # couloir : indéterminé au premier embranchement, on ne prédit que le départ
            pr = None if routes and idx > 0 else frozenset(model.start for r in routes)
        pr = frozenset(p for p in pr if p != poses[t]) if pr is not None else None
        out.append(pr)
    return out


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    traces = [str(DEV / f'N{n}') for n in range(1, 6)]
    A = controle_porte('held', 'entree_bascule', traces)
    B = controle_porte('toggle', 'occupation', traces)
    C = controle_fantome(traces)
    r = dict(A_porte_maintenue_retiree=A, B_bascule_retiree=B, C_fantome_retire=C, coups_reels=0,
             note='hors ligne, traces developpement/reset_g50t N1..N5 ; vérité v4 utilisée seulement pour noter')
    (out / 'controle_positif.json').write_text(json.dumps(r, indent=1, default=str, ensure_ascii=False))
    for nom, R in (('A', A), ('B', B), ('C', C)):
        for x in R:
            print(nom, x['trace'], x.get('groupe', {}).get('porte'), 'générés', x['generes'], 'survivants', x['survivants'],
                  'retrouvée', x['retrouvee'], 'rang', x['rang_verite'], 'fausses<=', x['fausses_decouvertes_classees_avant_ou_egales'],
                  'tête', x['tete'])


if __name__ == '__main__':
    main()


# ----------------------------------------------------------------------------------------- expériences réelles
def _entropie(groupes):
    tot = sum(groupes.values())
    return -sum(v / tot * math.log2(v / tot) for v in groupes.values() if v)


def experiences_porte(level, kind, famille_restante, porte, sortie, max_exp=3):
    """Départage les survivants d'une porte par au plus `max_exp` expériences réelles (niveau injecté)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'references/astra4/livraison_astra4/ajouts'))
    from boucle_v4.laboratoire import Laboratoire
    from boucle_v4.fantome_general import FantomeGeneral
    tr = str(DEV / f'N{level}')
    model, images, actions, poses = donnees(tr)
    g = next(g for g in model.groups if tuple(porte) in map(tuple, g['doors']))
    fant = [fantomes_observes(model, im, poses[t]) for t, im in enumerate(images)]
    occ_j = [{poses[t]} for t in range(len(images))]; occ_jf = [{poses[t]} | {p for p, c in fant[t]} for t in range(len(images))]
    obs = [etat_porte_observe(model, im, tuple(porte), g['color']) for im in images]
    surv = []
    for c in candidats_porte(model, famille_restante):
        occs = occ_jf if c['occupants'] == 'joueur+fantomes' else occ_j
        pr = simuler_porte(c, occs, obs[0])
        if not [t for t in range(1, len(obs)) if pr[t] != obs[t] and tuple(porte) not in occ_jf[t]]:
            surv.append(c)
    lab = Laboratoire('g50t', level, 'jeux', Path(sortie) / 'partie')
    # identification du joueur (famille déplacement conservée)
    m = None
    for a in range(1, 5):
        b = lab.image.copy(); im, _ = lab.play(a, 'identifier'); 
        try:
            m = FantomeGeneral(b, im, a); break
        except Exception:
            continue
    journal = [dict(etape='depart', survivants=len(surv))]
    pose = m.observe_player(lab.image, m.start) or m.start
    hist_occ = [{pose}]; hist_ferme = [etat_porte_observe(m, lab.image, tuple(porte), g['color'])]
    def nav(src, dst):
        from collections import deque
        todo = deque([(src, [])]); seen = {src}
        while todo:
            p, path = todo.popleft()
            if p == dst:
                return path
            for a, (dx, dy) in enumerate(m.dirs, start=1):
                q = (p[0] + dx, p[1] + dy)
                if q in m.node_set and q not in seen and (q not in m.doors or q == dst and False):
                    seen.add(q); todo.append((q, path + [a]))
        return None
    for k in range(max_exp):
        if len(surv) <= 1 or len({(c['type'], c['lieu']) for c in surv}) <= 1:
            break
        best = None
        for lieu in sorted({tuple(c['lieu']) for c in surv}):
            path = nav(pose, lieu)
            if path is None:
                continue
            seq = path + ([{1: 2, 2: 1, 3: 4, 4: 3}[path[-1]]] if path else [])  # monter puis quitter la dalle
            # poses prédites (famille déplacement connue) le long de seq
            ps = []; p = pose
            for a in seq:
                dx, dy = m.dirs[a - 1]; q = (p[0] + dx, p[1] + dy)
                p = q if q in m.node_set and q not in m.doors else p; ps.append(p)
            groupes = {}
            for c in surv:
                pr = simuler_porte(c, hist_occ + [{q} for q in ps], hist_ferme[0])
                groupes.setdefault(tuple(pr[len(hist_occ):]), 0); groupes[tuple(pr[len(hist_occ):])] += 1
            H = _entropie(groupes) if len(groupes) > 1 else 0
            if H and (best is None or H / len(seq) > best[0]):
                best = (H / len(seq), seq, lieu)
        if not best:
            break
        for a in best[1]:
            lab.play(a, f'experience_controle_{k}')
            pose = m.observe_player(lab.image, pose) or pose
            hist_occ.append({pose}); hist_ferme.append(etat_porte_observe(m, lab.image, tuple(porte), g['color']))
        avant = len(surv)
        surv = [c for c in surv if all(a == b for a, b, o in zip(simuler_porte(c, hist_occ, hist_ferme[0]), hist_ferme, hist_occ)
                                        if tuple(porte) not in o)]
        journal.append(dict(etape=f'experience_{k}', vers=best[2], sequence=best[1], survivants_avant=avant, apres=len(surv)))
    vraies = set(map(tuple, g['triggers'])); vt = {'held': 'occupation', 'toggle': 'entree_bascule'}[kind]
    surv.sort(key=lambda c: c['cout'])
    rang = next((i + 1 for i, c in enumerate(surv) if c['type'] == vt and tuple(c['lieu']) in vraies), None)
    return dict(niveau=level, porte=porte, coups_reels=len(lab.rows), journal=journal, survivants=len(surv),
                rang_verite=rang, tete=_court(surv[0]) if surv else None,
                lieux_survivants=sorted({tuple(c['lieu']) for c in surv})[:6], types=sorted({c['type'] for c in surv}))


def experiences_fantome(level, sortie, max_exp=3, prof=4):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'references/astra4/livraison_astra4/ajouts'))
    from boucle_v4.laboratoire import Laboratoire
    from boucle_v4.fantome_general import FantomeGeneral
    off = [r for r in controle_fantome([str(DEV / f'N{level}')])][0]
    model, images, actions, poses = donnees(str(DEV / f'N{level}'))
    obs = [frozenset(p for p, c in fantomes_observes(model, im, poses[t])) for t, im in enumerate(images)]
    cands = []
    for src, hor, acc in product(('trajet_vie_precedente', 'route_propre', 'miroir_joueur', 'couloir', 'immobile_au_depart'),
                                 ('effectif', 'tout'), ('remplace', 'cap1_clear', 'cap2_clear', 'cap3_clear', 'cap2_fifo', 'cap3_fifo')):
        c = dict(source=src, horloge=hor, accumulation=acc)
        pr = simuler_fantomes(c, model, actions, poses, obs)
        if not [t for t in range(1, len(obs)) if pr[t] is not None and pr[t] != obs[t]]:
            cands.append(c)
    lab = Laboratoire('g50t', level, 'jeux', Path(sortie) / 'partie')
    m = None
    for a in range(1, 5):
        b = lab.image.copy(); im, _ = lab.play(a, 'identifier')
        try:
            m = FantomeGeneral(b, im, a); break
        except Exception:
            continue
    acts = [r['action'] for r in lab.rows]; ps = [m.start]
    for im in lab.images[1:]:
        ps.append(m.observe_player(im, ps[-1]) or ps[-1])
    obsr = [frozenset(p for p, c in fantomes_observes(m, im, ps[t])) for t, im in enumerate(lab.images)]
    journal = [dict(etape='depart', survivants=len(cands))]
    def pas(p, a):
        if a == 5:
            return m.start
        dx, dy = m.dirs[a - 1]; q = (p[0] + dx, p[1] + dy)
        return q if q in m.node_set and q not in m.doors else p
    for k in range(max_exp):
        if len(cands) <= 1:
            break
        best = None
        for seq in product(range(1, 6), repeat=prof):
            pp = list(ps); 
            for a in seq:
                pp.append(pas(pp[-1], a))
            groupes = {}
            for c in cands:
                pr = simuler_fantomes(c, m, acts + list(seq), pp, None)
                key = tuple(pr[len(ps):]); groupes[key] = groupes.get(key, 0) + 1
            if len(groupes) > 1:
                H = _entropie(groupes) / len(seq)
                if best is None or H > best[0]:
                    best = (H, list(seq))
        if not best:
            break
        for a in best[1]:
            lab.play(a, f'experience_controle_{k}')
        acts = [r['action'] for r in lab.rows]; ps = [m.start]
        for im in lab.images[1:]:
            ps.append(m.observe_player(im, ps[-1]) or ps[-1])
        obsr = [frozenset(p for p, c in fantomes_observes(m, im, ps[t])) for t, im in enumerate(lab.images)]
        avant = len(cands)
        cands = [c for c in cands if all(x is None or x == o for x, o in zip(simuler_fantomes(c, m, acts, ps, obsr), obsr))]
        journal.append(dict(etape=f'experience_{k}', sequence=best[1], survivants_avant=avant, apres=len(cands)))
    vrai = [c for c in cands if c['source'] == 'trajet_vie_precedente' and c['horloge'] == 'effectif']
    return dict(niveau=level, coups_reels=len(lab.rows), journal=journal, survivants=len(cands),
                survivants_detail=cands[:8], verite_parmi_survivants=bool(vrai), hors_ligne=dict(rang=off['rang_verite'], survivants=off['survivants']))
