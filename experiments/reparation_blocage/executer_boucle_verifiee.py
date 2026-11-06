"""Entrée explicite du pilote expérimental ; moteur empaqueté vérifié avant usage.

--verifier n'ouvre aucun jeu. --tests exécute les tests fournis sans SDK implicite.
--pilote transmet les arguments au pilote existant, sans changer ses options.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import runpy
import sys

ICI = Path(__file__).resolve().parent
PAQUET = ICI / 'paquet'


def configurer():
    # Ne pas retirer/recharger des modules : un processus déjà mélangé est refusé.
    for nom, module in list(sys.modules.items()):
        if nom == 'chrysalide' or nom.startswith('chrysalide.'):
            origine = getattr(module, '__file__', None)
            if origine is None or not Path(origine).resolve().is_relative_to(PAQUET):
                raise RuntimeError(f'Moteur déjà chargé hors paquet : {nom} ({origine})')
    chemins = [str(PAQUET), str(PAQUET / 'livraison_p1/code'), str(ICI)]
    sys.path[:] = chemins + [p for p in sys.path if p not in chemins]
    preuves = {}
    for nom in ('chrysalide.arc3.logique.theorie',
                'chrysalide.arc3.logique.export_langage',
                'chrysalide.arc3.moteur'):
        module = importlib.import_module(nom)
        chemin = Path(module.__file__).resolve()
        if not chemin.is_relative_to(PAQUET):
            raise RuntimeError(f'Import incohérent : {nom} ({chemin})')
        preuves[nom] = {'fichier': str(chemin),
                        'sha256': hashlib.sha256(chemin.read_bytes()).hexdigest()}
    theorie = sys.modules['chrysalide.arc3.logique.theorie']
    if not callable(getattr(theorie, 'roles_motif', None)):
        raise RuntimeError('Paquet sans contrat roles_motif')
    if not hasattr(theorie.Theorie(), 'masque_projection'):
        raise RuntimeError('Paquet sans contrat masque_projection')
    return preuves


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--verifier', action='store_true')
    mode.add_argument('--tests', action='store_true')
    mode.add_argument('--pilote', action='store_true')
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    args = p.parse_args()
    arguments = args.arguments
    if arguments[:1] == ['--']:
        arguments = arguments[1:]
    preuves = configurer()
    # stderr : ne pas polluer le protocole JSON du pilote persistant.
    print(json.dumps({'moteur_verifie': preuves}), file=sys.stderr)
    if args.verifier:
        return 0
    if args.tests:
        if not arguments:
            p.error('--tests exige une sélection explicite de tests')
        import pytest
        return pytest.main(['-o', 'pythonpath=', '--import-mode=importlib',
                            '-p', 'no:cacheprovider', *arguments])
    sys.argv = [str(ICI / 'session_chaine_generique.py'), *arguments]
    runpy.run_path(sys.argv[0], run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
