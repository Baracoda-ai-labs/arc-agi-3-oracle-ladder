"""Raccordement des recherches aux modèles appris sur traces ARC, zéro SDK."""
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
from montecarlo import chercher

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / 'paquet'), str(ICI / 'paquet/livraison_p1/code')]

from agent_p1.releve_moteur import _lot

from chrysalide.arc3.logique.plan import distance_but, planifier
from chrysalide.arc3.logique.theorie import monde_final
from chrysalide.arc3.moteur import NOMS, MoteurC, _clics_offerts, _lot_c, porte, porte_but


def main():
    bilan = []
    for jeu, niveau, k in [('ft09', 1, 80), ('ka59', 6, 120)]:
        base = ICI / 'runs/publics_ref_g0' / jeu
        meta = json.loads((base / 'journal_jeu.jsonl').read_text().splitlines()[0])
        for cle in list(os.environ):
            if cle.startswith('CHRYS_'):
                del os.environ[cle]
        os.environ.update(meta['env'])
        os.environ.update(CHRYS_REPARATION_BLOCAGE='2', CHRYS_PLAN_CONTEXTE_COMPLET='1',
                          CHRYS_CENTRES_RAPIDES='1', CHRYS_EXPORT_SANS_EFFET='1')
        rows = json.loads((base / f'N{niveau}/partie.json').read_text())['rows']
        images = np.load(base / f'N{niveau}/partie.npz')['images']
        debut = max((i + 1 for i in range(k) if rows[i]['action'] == 0), default=0)
        debut = max(debut, k - 40)
        grilles = [g.tolist() for g in images[debut:k + 1]]
        lots = [_lot(r['action']) for r in rows[debut:k]]
        m = MoteurC(budget=2)
        r = m.proposer({'grilles': grilles, 'lots': lots, 'precedents': []})
        item = {'jeu': jeu, 'niveau': niveau, 'coup': k, 'mode': 'simulation sur trace',
                'source_moteur': sys.modules[planifier.__module__].__file__}
        th = getattr(m, 'th_plan', None)
        if r is None or th is None or porte(m, r[1], grilles, lots) is None:
            item.update(admissible=False, refus=m.infos.get('refus'))
            bilan.append(item)
            continue
        item.update(admissible=True, resultats=[])
        initial = monde_final(th, m.tr)
        actions = sorted(a for a in set(m.tr.actions) if a in NOMS and a != 7)
        actions += _clics_offerts(th, m.tr) if th.motif else []
        item['actions_offertes'] = len(actions)
        profondeur = 150 - k
        for methode in ['bfs', 'multigraines', 'aleatoire', 'nmcs']:
            t0 = time.process_time()
            if methode in ('bfs', 'multigraines'):
                suite, noeuds = None, 0
                n = 3 if methode == 'multigraines' else 1
                for graine in range(n):
                    ordre = list(actions)
                    if n > 1:
                        random.Random(graine).shuffle(ordre)
                    suite, visites = planifier(th, initial, m.tr.taille, ordre,
                        profondeur=profondeur, deadline=min(t0 + .5, time.process_time() + .5 / n))
                    noeuds += visites
                    if suite:
                        break
                infos = {'noeuds': noeuds}
            else:
                suite, infos = chercher(initial, actions, lambda s, a, th=th, taille=m.tr.taille: th.pas(s, a, taille)[0],
                    th.atteint, th.meurt, lambda s, th=th: -distance_but(th, s), profondeur, .5,
                    methode=methode, transitions_max=10000)
            cpu = time.process_time() - t0
            code = [_lot_c(a, m.tr) for a in suite] if suite else []
            n, issue = porte_but(m, r[1], grilles, lots, code) if code else (None, None)
            item['resultats'].append({'methode': methode, 'longueur': len(code), 'cpu_s': cpu,
                'porte_validee': bool(code) and n == len(code) and issue in ('niveau', 'victoire'),
                'issue': issue, **infos})
        bilan.append(item)
    (ICI / 'bilan_montecarlo_trace.json').write_text(json.dumps(bilan, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(bilan, ensure_ascii=False))


if __name__ == '__main__':
    main()
