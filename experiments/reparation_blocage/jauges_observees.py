"""Régions de jauge candidates : lecteur existant + validation dynamique causale.

Ce masque est conditionnel à la famille des barres de bord, pas une preuve que
ces pixels sont dépourvus d'effets. Les deux orientations réutilisent le même
lecteur ; elles ne constituent pas un transfert entre jeux.
"""
from functools import lru_cache
from pathlib import Path
import importlib.util
import numpy as np


@lru_cache(maxsize=1)
def lecteur():
    path = Path(__file__).parent/'paquet/references/astra4/livraison_astra4/ajouts/boucle_v4/economie.py'
    spec = importlib.util.spec_from_file_location('_economie_jauge_existante', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Economie


def jauges_validees(images, actions):
    if len(images) != len(actions)+1:
        raise ValueError('Historique jauge non aligné')
    cells, rapports = set(), []
    for renverse in (False, True):
        gs = [np.asarray(g)[::-1].copy() if renverse else np.asarray(g).copy() for g in images]
        economie = lecteur()(gs[0])
        if not economie.valid:
            continue
        row = len(gs[0])-1-economie.y if renverse else economie.y
        region = [(int(row),int(x)) for x in economie.columns]
        valeurs = [economie.read(g) for g in gs]
        # Le motif doit rester un segment contigu, rogné au bord, sans déplacement
        # de la région ni retour/recharge ambigu dans ce préfixe d'admission.
        segments = []
        for g in gs:
            positions = np.flatnonzero(g[economie.y,economie.columns]==economie.color)
            segments.append(bool(len(positions) and np.all(np.diff(positions)==1)
                                 and (positions[0]==0 or positions[-1]==len(economie.columns)-1)))
        for k,a in enumerate(actions):
            economie.update(a,gs[k],gs[k+1])
        deltas = np.diff(valeurs)
        accepte = bool(economie.valid and np.count_nonzero(deltas<0)>=3 and np.all(deltas<=0)
                       and all(segments) and all(r['prediction_contains_observation'] for r in economie.rows))
        rapport = {'region':region,'orientation_renversee':renverse,'valeurs':valeurs,
                   'admis':accepte,'statut':'hypothese_jauge_bornee','rapport_economie':economie.report()}
        rapports.append(rapport)
        if accepte:
            cells.update(region)
    return frozenset(cells), rapports
