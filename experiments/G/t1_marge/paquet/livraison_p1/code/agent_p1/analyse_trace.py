"""Test B hors ligne : rejouer une trace enregistrée où la théorie courante prédit mal, inventer, filtrer, journaliser.

Usage : python -m mechanism_inventor.analyse_trace <dossier_trace> <sortie> [--t_invention N] [--parametres_seuls]
La trace est un dossier `partie.json` + `partie.npz` (format Laboratoire v4). Aucune action réelle n'est jouée.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'references/astra4/livraison_astra4/ajouts'))
from boucle_v4.fantome_general import FantomeGeneral  # noqa: E402

from . import objets as O  # noqa: E402
from .mutations import contexte_causal, generer, generer_parametres_seuls  # noqa: E402
from .classement import evaluer, classes_equivalence, sensibilite  # noqa: E402
from .journal import Journal  # noqa: E402
from .superviseur import superviser, Memoire  # noqa: E402


def modele_depuis_trace(images, actions):
    for t, a in enumerate(actions[:6], start=1):
        if a in (1, 2, 3, 4):
            try:
                return FantomeGeneral(images[t - 1], images[t], a), t
            except (ValueError, IndexError, AssertionError):
                continue
    raise ValueError('joueur non identifié')


def poses_joueur(model, images, t_id):
    poses = [None] * len(images)
    pres = model.start
    for t in range(len(images)):
        p = model.observe_player(images[t], pres)
        poses[t] = p
        if p is not None:
            pres = p
    return poses


def charger(dossier):
    d = Path(dossier)
    z = np.load(d / 'partie.npz'); images = z['images']
    actions = json.load(open(d / 'partie.json'))['actions']
    return images, actions


def analyser(images, actions, t_invention=None, parametres_seuls=False, journal=None, sans_superviseur=False):
    model, t_id = modele_depuis_trace(images, actions)
    poses = poses_joueur(model, images, t_id)
    objs, lignes = O.transitions(model, images, actions, poses)
    cons = O.contradictions_v4(objs, lignes)
    res = dict(objets=[{k: v for k, v in o.items() if k != 'forme'} for o in objs], n_contradictions=len(cons),
               contradictions=cons[:20], par_objet={})
    if journal:
        journal.ecrire('perception', objets=res['objets'], groupes=model.groups, pas=model.step)
        journal.ecrire('contradictions_v4', n=len(cons), detail=cons[:30])
    for o in objs:
        co = [c for c in cons if c['objet'] == o['id']]
        if not co:
            continue
        ti = t_invention or co[max(0, len(co) // 2 - 1)]['t']
        inv = [L for L in lignes if L['t'] <= ti]
        ctx = contexte_causal(o, cons, lignes)
        pi = O.portes_fermees(model, images[0])
        if parametres_seuls:
            hyps = generer_parametres_seuls(o, ctx, inv); evaluer(hyps, o, lignes, model, ti, portes_initiales=pi); rap = {}
        else:
            hyps, rap = superviser(o, ctx, lignes, model, ti, Memoire(), f"trace_{o['id']}", 1, pi, journal,
                                   sans_superviseur=sans_superviseur)
        cl = classes_equivalence(hyps)
        surv_inv = [h for h in hyps if not h.__dict__['err_invention']]
        r = dict(superviseur=rap, contexte=ctx, t_invention=ti, n_generees=len(hyps), n_compatibles_invention=len(surv_inv),
                 n_survivantes=sum(h.statut == 'survivante' for h in hyps),
                 n_rejetees_validation=sum(1 for h in surv_inv if h.statut == 'rejetee'),
                 classes=[dict(score=round(c['score'], 2), n=len(c['membres']), representant=c['representant'].resume(),
                               membres=[m.id for m in c['membres']]) for c in cl[:8]],
                 rejets_exemples=[dict(id=h.id, mutations=h.mutations, preuve=h.preuve_rejet)
                                  for h in hyps if h.statut == 'rejetee'][:12])
        if not parametres_seuls:
            r['sensibilite'] = sensibilite(hyps, o, lignes, model, ti)
        res['par_objet'][o['id']] = r
        res.setdefault('_hyps', {})[o['id']] = hyps
        if journal:
            journal.ecrire('invention', objet=o['id'], contexte=ctx, t_invention=ti, n_generees=len(hyps))
            for h in hyps:
                journal.ecrire('hypothese', id=h.id, version=h.version, statut=h.statut, score=h.score, cout=h.cout,
                               mutations=h.mutations, programme=h.programme, preuve_rejet=h.preuve_rejet,
                               n_explique=len(h.explique), n_non_predit=len(h.non_predit))
    res['_model'] = model; res['_lignes'] = lignes; res['_objs'] = objs; res['_poses'] = poses
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('trace'); ap.add_argument('sortie')
    ap.add_argument('--t_invention', type=int); ap.add_argument('--parametres_seuls', action='store_true'); ap.add_argument('--sans_superviseur', action='store_true')
    a = ap.parse_args()
    images, actions = charger(a.trace)
    j = Journal(a.sortie, 'testB_' + ('param' if a.parametres_seuls else 'struct') + ('_sanssup' if a.sans_superviseur else ''), dict(trace=a.trace, t_invention=a.t_invention))
    res = analyser(images, actions, a.t_invention, a.parametres_seuls, j, a.sans_superviseur)
    out = {k: v for k, v in res.items() if not k.startswith('_')}
    p = Path(a.sortie) / ('resume_testB_' + ('param' if a.parametres_seuls else 'struct') + ('_sanssup' if a.sans_superviseur else '') + '.json')
    if p.exists():
        import time
        p = p.with_name(p.stem + time.strftime('_%H%M%S') + '.json')
    p.write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    for oid, r in out['par_objet'].items():
        print(oid, 'générées', r['n_generees'], 'compatibles invention', r['n_compatibles_invention'],
              'survivantes', r['n_survivantes'], 'rejetées en validation', r['n_rejetees_validation'])
        for c in r['classes'][:5]:
            rp = c['representant']
            print('  classe', c['n'], 'score', c['score'], rp['programme'], rp['nouveaute'])
    print('journal', j.path)


if __name__ == '__main__':
    main()
