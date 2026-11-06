"""Protocole fixe, traces seules ; aucun serveur IA ni SDK."""
import argparse
import json
from pathlib import Path

import banc_chaine
from ablation import diagnostiquer
from chaine_coherente import Chaine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sortie', type=Path, default=Path(__file__).with_name('bilan_ablation.json'))
    sortie = parser.parse_args().sortie
    if sortie.exists():
        raise FileExistsError(sortie)
    bilan = {'nouveaux_appels_sdk': 0, 'appels_ia': 0, 'cas': []}
    for cas in [*banc_chaine.CAS[:3], banc_chaine.CAS[4]]:
        captures = []
        class Capture(Chaine):
            def __init__(self, *args, _captures=captures, **kwargs):
                super().__init__(*args, **kwargs)
                _captures.append(self)
        original = banc_chaine.Chaine
        banc_chaine.Chaine = Capture
        try:
            reference = banc_chaine.un_cas(*cas)
        finally:
            banc_chaine.Chaine = original
        diagnostic, candidats = diagnostiquer(captures[-1])
        resultat = {'cas': cas, 'reference': reference, 'diagnostic': diagnostic}
        if len(candidats) == 1:
            resultat['replanification_simulee'] = candidats[0].proposer(secondes=1)
        bilan['cas'].append(resultat)
        print(json.dumps({'cas': cas, 'diagnostic': diagnostic['statut'],
                          'candidats': diagnostic['candidats'],
                          'replanification': resultat.get('replanification_simulee', {}).get('statut')}))
    sortie.write_text(json.dumps(bilan, ensure_ascii=False, indent=2, default=repr) + '\n')


if __name__ == '__main__':
    main()
