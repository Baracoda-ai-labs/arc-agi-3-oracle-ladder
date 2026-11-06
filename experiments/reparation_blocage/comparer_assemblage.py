"""Réutilise la comparaison existante en limitant explicitement la référence à y056."""
import json
import tempfile
from pathlib import Path

from comparer_passages import comparer

ICI = Path(__file__).resolve().parent


def main():
    reference = ICI / 'runs/dev_export_g0'
    candidat = ICI / 'runs/coherence_y056_g0'
    with tempfile.TemporaryDirectory(prefix='chrysalide-comparaison-') as nom:
        dossier = Path(nom)
        resume = json.loads((reference / 'resume.json').read_text())
        (dossier / 'resume.json').write_text(json.dumps({'y056': resume['y056']}))
        (dossier / 'y056').symlink_to((reference / 'y056').resolve(), target_is_directory=True)
        bilan = comparer(dossier, candidat)
    bilan['reference'] = str(reference / 'y056')
    bilan['portee'] = 'controle SDK synthetique de compatibilite, pas gain ARC'
    bilan['empreinte_paquet_teste_sdk'] = json.loads((candidat / 'commande.json').read_text())['sha_experimental']
    (ICI / 'bilan_assemblage_reel.json').write_text(json.dumps(bilan, ensure_ascii=False, indent=2) + '\n')
    assert not bilan['erreurs'] and bilan['toutes_actions_identiques']
    cout = {**bilan['total_bras'], 'initialisations_sdk': 1, 'actions_sdk_total_initialisations_incluses':
            bilan['total_bras']['coups'] + 1, 'resets_deja_inclus_dans_coups': True,
            'appels_ia_nouveaux': 0, 'traces_reutilisees_non_recomptees': True}
    (ICI / 'couts_assemblage.json').write_text(json.dumps(cout, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'resultat': bilan['total_bras'], 'actions_identiques': bilan['toutes_actions_identiques'],
                      'cout': cout}, ensure_ascii=False))


if __name__ == '__main__':
    main()
