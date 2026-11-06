"""Diagnostic reproductible sur les six cas de développement déjà autorisés."""
import argparse
import json
from pathlib import Path

from banc_chaine import CAS, un_cas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sortie', type=Path, required=True)
    sortie = parser.parse_args().sortie
    if sortie.exists():
        raise FileExistsError(sortie)
    cas = []
    for entree in CAS:
        r = un_cas(*entree)
        cas.append({k: r[k] for k in ('jeu', 'niveau', 'coup', 'statut',
                    'classification_prefixe', 'classification_finale') if k in r})
        print(json.dumps({'jeu': r['jeu'], 'familles': [c['famille'] for c in
            r.get('classification_prefixe', {}).get('candidats', [])],
            'final': r.get('classification_finale', {}).get('statut')}, ensure_ascii=False), flush=True)
    bilan = {'nouveaux_appels_sdk': 0, 'appels_ia': 0,
             'preuve': 'Traces de developpement seulement ; aucune mesure de precision des familles', 'cas': cas}
    with sortie.open('x') as f:
        json.dump(bilan, f, ensure_ascii=False, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
