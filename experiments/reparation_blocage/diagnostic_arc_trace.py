"""Rejoue la réparation sur observations archivées, sans charger de jeu."""
import copy
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / 'paquet'), str(ICI / 'paquet/livraison_p1/code')]
BASE = ICI / 'runs/arc_blocage_terminale_g1/m0r0'
meta = json.loads((BASE / 'journal_jeu.jsonl').read_text().splitlines()[0])
os.environ.update(meta['env'])

from agent_p1.reparation_locale import tenter

from chrysalide.arc3 import moteur
from chrysalide.arc3.logique import plan


def main():
    rows = json.loads((BASE / 'N2/partie.json').read_text())['rows']
    images = np.load(BASE / 'N2/partie.npz')['images']
    journal, mesures, capture = [], [], {}

    class Lab:
        level = 2
        won = False
        finished = False

        def __init__(self):
            self.rows = copy.deepcopy(rows[:120])
            self.images = [im.copy() for im in images[:121]]
            self.image = self.images[-1]

        def play(self, action, origine):
            k = len(self.rows)
            assert k < 125, 'Action nouvelle interdite en diagnostic sur trace'
            assert action == rows[k]['action'], 'Reconstruction différente de la trace'
            self.rows.append(copy.deepcopy(rows[k]))
            self.image = images[k + 1].copy()
            self.images.append(self.image)

    def noter(genre, **kw):
        journal.append({'type': genre, **kw})

    original = moteur.porte_but

    def porte_detaillee(m, programme, grilles, lots, suite):
        t = time.process_time()
        n, issue = original(m, programme, grilles, lots, suite)
        mesures.append({'phase': 'porte_but', 'longueur': len(suite), 'n': n,
                        'issue': issue, 'cpu': time.process_time() - t,
                        'exemple_action': suite[:1]})
        if capture and suite:
            th, monde, taille = capture['args'][:3]
            a = capture['resultat'][0][0]
            suivant, _ = th.pas(monde, a, taille)
            p = moteur.porte(m, programme, grilles, lots)
            if p:
                prog, sc = p
                prog.step(sc, moteur.nom_action(suite[0]))
                rt = th.rendu(suivant, taille, m.tr.fond)
                rt = m._masquer(np.where(rt >= 16, rt % 16, rt))
                mesures.append({'phase': 'comparaison_suite', 'theorie_atteint': th.atteint(suivant),
                                'issue_export': sc.issue, 'pixels_theorie_export': int((rt != m.rendu(sc)).sum()),
                                'but': repr(th.but), 'action': a,
                                'etat_export': repr(prog.etat)})
        return n, issue

    original_plan = plan.planifier

    def plan_detaille(*args, **kwargs):
        resultat = original_plan(*args, **kwargs)
        capture.update(args=args, resultat=resultat)
        mesures.append({'phase': 'planifier', 'longueur': len(resultat[0] or []),
                        'cpu_restant': kwargs.get('deadline', time.process_time()) - time.process_time()})
        return resultat

    moteur.porte_but = porte_detaillee
    plan.planifier = plan_detaille
    lab = Lab()
    t = time.process_time()
    resultat = tenter(SimpleNamespace(lab=lab, j=SimpleNamespace(ecrire=noter)), 'joue')
    sortie = {'mode': 'trace uniquement, aucun appel SDK', 'cpu': time.process_time() - t,
              'resultat': resultat, 'observations_rejouees': len(lab.rows) - 120,
              'journal': journal, 'mesures': mesures}
    Path(sys.argv[1]).write_text(json.dumps(sortie, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in sortie.items() if k != 'journal'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
