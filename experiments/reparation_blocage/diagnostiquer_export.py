"""Diagnostic sur enregistrements seulement ; aucun environnement de jeu chargé."""
import copy
import json
import os
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
PAQUET = Path(os.environ.get('CHRYS_PAQUET_DIAGNOSTIC', ICI / 'paquet'))
sys.path[:0] = [str(PAQUET), str(PAQUET / 'livraison_p1/code')]
os.environ['CHRYS_REPARATION_BLOCAGE'] = '2'
os.environ['CHRYS_BUT_SUPPOSE'] = '1'

from agent_p1.releve_moteur import _lot

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.theorie import monde_final
from chrysalide.arc3.moteur import MoteurC, _exporter, nom_action, porte


def diagnostic():
    base = ICI / 'runs/dev_locale_g0/y071/N2'
    rows = json.loads((base / 'partie.json').read_text())['rows']
    images = np.load(base / 'partie.npz')['images']
    k = 40
    debut = max(t + 1 for t in range(k) if rows[t]['action'] == 0)
    actes = [r['action'] for r in rows[debut:k]]
    grilles = [g.tolist() for g in images[debut:k + 1]]
    lots = [_lot(a) for a in actes]
    m = MoteurC(budget=30)
    r = m.proposer({'grilles': grilles, 'lots': lots, 'precedents': []})
    th = copy.deepcopy(m.th_plan)
    cle = th.cle_sans_effet(monde_final(th, m.tr), rows[k]['action'], m.tr.taille)
    th.sans_effet = th.sans_effet | {cle}
    programme, non = _exporter(th, m.tr.taille)
    initiale = porte(m, r[1], grilles, lots) is not None
    grilles.append(images[k + 1].tolist())
    lots.append(_lot(rows[k]['action']))
    p, sc = Programme(programme), m.scene(grilles[0])
    monde = m.tr.etats[0]
    etapes = []
    for i, (lot, g) in enumerate(zip(lots, grilles[1:])):
        if i == len(lots) - 1:
            avant = {'theorie': repr(monde), 'sprites': [{'x': s['x'], 'y': s['y'], 'pixels': np.asarray(s['pixels']).tolist()}
                                                      for s in sc.sprites], 'etat': repr(p.etat)}
        p.step(sc, nom_action(lot['actions'][0]))
        monde, _ = th.pas(monde, rows[debut + i]['action'], m.tr.taille)
        rt = th.rendu(monde, m.tr.taille, m.tr.fond)
        rt = m._masquer(np.where(rt >= 16, rt % 16, rt))
        etapes.append({'coup': debut + i + 1, 'ecart_theorie': int((rt != m.vue(g)).sum()),
                           'ecart_export': int((m.rendu(sc) != m.vue(g)).sum()), 'sans_effet': p.etat.get('_sans_effet')})
    return {'cpu_proposition': m.infos.get('cpu_s'), 'but': m.infos.get('but_suppose'), 'plan': r[0],
                'theorie': repr(th), 'programme': programme, 'porte_initiale': initiale, 'porte_corrigee': porte(m, programme, grilles, lots) is not None,
                'cle': repr(cle), 'non_exporte': non, 'etapes': etapes, 'avant_blocage': avant,
                'regles': [x for x in programme['regles'] if x.get('nom') == 'coups sans effet']}


if __name__ == '__main__':
    d = diagnostic()
    sortie = Path(sys.argv[1])
    sortie.write_text(json.dumps(d, ensure_ascii=False, default=repr, indent=2) + '\n')
    print(json.dumps({k: d[k] for k in ('porte_initiale', 'porte_corrigee', 'cle', 'etapes')}, ensure_ascii=False))
