"""Les contrôles de raccordement préinscrits, uniquement sur enregistrements."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / 'paquet'), str(ICI / 'paquet/livraison_p1/code')]

from agent_p1.releve_moteur import _lot
from chaine_coherente import Chaine

from chrysalide.arc3.moteur import NOMS, MoteurC, _clics_offerts, _lot_c, nom_action

CAS = [('audit', 'y056', 1, 80), ('audit', 'y071', 2, 40),
       ('audit', 'y084', 2, 80), ('publics_ref_g0', 'ft09', 1, 80),
       ('arc_blocage_terminale_g1', 'm0r0', 2, 120), ('publics_ref_g0', 'ka59', 6, 120)]


def un_cas(run, jeu, niveau, k):
    if run == 'audit':
        base = ICI.parents[2] / 'audit/chrysalide_audit_23-10/traces/enregistrements' / jeu
    else:
        base = ICI / 'runs' / run / jeu
    meta = json.loads((base / 'journal_jeu.jsonl').read_text().splitlines()[0])
    for cle in list(os.environ):
        if cle.startswith('CHRYS_'):
            del os.environ[cle]
    os.environ.update(meta['env'])
    os.environ.update(CHRYS_REPARATION_BLOCAGE='2', CHRYS_EXPORT_SANS_EFFET='1',
                      CHRYS_CENTRES_RAPIDES='1', CHRYS_PLAN_CONTEXTE_COMPLET='1')
    document = json.loads((base / f'N{niveau}/partie.json').read_text())
    rows = document['rows']
    archive = np.load(base / f'N{niveau}/partie.npz')
    images = archive['images']
    debut = max((i + 1 for i in range(k) if rows[i]['action'] == 0), default=0)
    debut = max(debut, k - 40)
    grilles = [g.tolist() for g in images[debut:k + 1]]
    lots = [_lot(r['action']) for r in rows[debut:k]]
    resultat = {'jeu': jeu, 'niveau': niveau, 'coup': k, 'trace': str(base / f'N{niveau}'),
                'preuve': 'trace uniquement', 'nouveaux_appels_sdk': 0}
    m = MoteurC(budget=2)
    t0 = time.process_time()
    r = m.proposer({'grilles': grilles, 'lots': lots, 'precedents': []})
    resultat.update(cpu_perception_induction=time.process_time() - t0, infos_induction=m.infos)
    th = getattr(m, 'th_plan', None)
    if r is None or r[1] is None or th is None:
        return {**resultat, 'statut': 'modele_non_reconstruit', 'refus': m.infos.get('refus')}
    offertes = sorted(a for a in set(m.tr.actions) if a in NOMS and a != 7)
    offertes += _clics_offerts(th, m.tr) if th.motif else []
    actions = [nom_action(_lot_c(a, m.tr)) for a in offertes]
    films = [archive.get('film_' + str(t + 1)) for t in range(debut, k)]
    c = Chaine(m, r[1], grilles, lots, actions, coups_deja_joues=k, films=films)
    resultat['classification_prefixe'] = c.classifier()
    resultat['perception'] = c.description_perception()
    resultat['controle'] = c.rejouer()[0]
    resultat['recherche_compilee'] = c.proposer(secondes=.25)
    plan = [nom_action(a if 'action' in a else a['actions'][0]) for a in r[0]]
    resultat['plan_moteur_existant'] = c.adopter_plan(plan)
    resultat['observations'] = []
    for i, action in enumerate(plan):
        t = k + i
        if t >= len(rows):
            resultat['observations'].append({'statut': 'trace_terminee'})
            break
        action_trace = nom_action(_lot(rows[t]['action'])['actions'][0])
        if c.action_tuple(action) != action_trace:
            resultat['observations'].append({'statut': 'plan_reconstruit_different_de_la_trace', 'pas': i + 1})
            break
        if c.plan is None:
            resultat['observations'].append({'statut': 'plan_non_admissible', 'pas': i + 1})
            break
        victoire = bool(document['victory']) and t + 1 == len(rows)
        termine = rows[t]['state'].split('.')[-1] != 'NOT_FINISHED'
        obs = c.observer(action, images[t + 1], victoire=victoire, termine=termine, source='trace',
                         film=archive.get('film_' + str(t + 1)))
        resultat['observations'].append({'pas': i + 1, **obs})
        if obs['statut'] != 'transition_confirmee':
            break
        if i + 1 < len(plan):
            c.adopter_plan(plan[i + 1:])
    dossier = c.dossier_ia()
    # Le dossier est prêt pour le client existant ; aucun LLM n'est appelé par ce banc.
    resultat['dossier_ia'] = {'contrats_exprimes': len((dossier['contrats_theorie_origine'] or {}).get('instances', [])),
        'champs_non_exprimes': (dossier['contrats_theorie_origine'] or {}).get('non_exprimes', []),
        'semantique_native_fournie': bool(dossier['semantique_native']), 'appel_ia': False}
    resultat['signature_finale'] = c.signature()
    resultat['classification_finale'] = c.classifier()
    resultat['statut'] = 'controle_raccordement_effectue'
    return resultat


def main():
    bilan = {'source_science_sha256': hashlib.sha256((ICI / 'science_source_24-10.md').read_bytes()).hexdigest(),
             'nouveaux_appels_sdk': 0, 'appels_ia': 0, 'cas': []}
    for cas in CAS:
        r = un_cas(*cas)
        bilan['cas'].append(r)
        print(json.dumps({'jeu': r['jeu'], 'niveau': r['niveau'], 'statut': r['statut'],
                          'controle': r.get('controle'), 'observations': r.get('observations')}, ensure_ascii=False))
    attendus = {'y056': (4, 'victoire_verifiee_sur_trace'), 'y071': (1, 'modele_refute'),
                'y084': (12, 'but_refute'), 'ft09': (3, 'victoire_verifiee_sur_trace'),
                'm0r0': (5, 'modele_refute')}
    for r in bilan['cas']:
        if r['jeu'] in attendus:
            n, statut = attendus[r['jeu']]
            assert len(r['observations']) == n and r['observations'][-1]['statut'] == statut, r['jeu']
            assert r['controle']['compilation_fidele'] and r['controle']['catalogue_shacl'], r['jeu']
        if r['jeu'] == 'y071':
            assert r['observations'][-1]['pixels_ecart'] == 4
        if r['jeu'] == 'y084':
            assert all(o['pixels_ecart'] == 0 for o in r['observations'])
    bilan['controles_attendus_passes'] = True
    (ICI / 'bilan_chaine.json').write_text(json.dumps(bilan, ensure_ascii=False, indent=2, default=repr) + '\n')


if __name__ == '__main__':
    main()
