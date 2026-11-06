"""Point d'entrée de l'assemblage : vérification hors ligne, aucune partie lancée."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
R = ICI.parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verifier', action='store_true', help='préparer, tester, raccorder les traces')
    a = ap.parse_args()
    if not a.verifier:
        ap.print_help()
        return
    env = {**os.environ, 'PYTHONHASHSEED': '0'}
    for script in ['preparer.py', 'verifier_assemblage.py', 'banc_chaine.py']:
        subprocess.run([sys.executable, str(ICI / script)], cwd=R, env=env, check=True)
    print('Assemblage vérifié ; aucun nouveau coup SDK et aucun appel IA.')


if __name__ == '__main__':
    main()
