"""Différentiel de séquences : même théorie, deux chemins de calcul, aucune source de jeu."""
import copy
import os
import random
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI / 'paquet_prefiltre'))

from chrysalide.arc3.logique.theorie import Theorie


def verifier():
    rng = random.Random(2410)
    un = frozenset({(0, 0)})
    comparees = 0
    for cas in range(300):
        positions = rng.sample([(x, y) for y in range(6) for x in range(8)], 6)
        monde = tuple((c, un, *xy) for c, xy in zip([3, 5, 8, 8, 8, 8], positions))
        th = Theorie(moves={(3, 1): (0, -1), (3, 2): (0, 1), (3, 3): (-1, 0), (3, 4): (1, 0)},
                     solides=frozenset({8}), retour=((3, 2, *positions[0]),) if cas % 2 else ())
        th.sans_effet = frozenset(th.cle_sans_effet(monde, a, (8, 6)) for a in rng.sample([1, 2, 3, 4], 2))
        actions = [rng.randrange(1, 5) for _ in range(30)]
        sorties, theories = [], []
        for drapeau in ['0', '1']:
            os.environ['CHRYS_SANS_EFFET_PREFILTRE'] = drapeau
            copie, etat = copy.deepcopy(th), monde
            suite = []
            for a in actions:
                etat, effet = copie.pas(etat, a, (8, 6))
                suite.append((etat, effet))
            sorties.append(suite)
            theories.append(copie.__dict__)
        assert sorties[0] == sorties[1], cas
        assert theories[0] == theories[1], cas
        comparees += len(actions)
    return comparees


if __name__ == '__main__':
    print(f'{verifier()} transitions identiques ; états et paramètres de théorie identiques')
