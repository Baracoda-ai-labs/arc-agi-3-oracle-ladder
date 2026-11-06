"""Le lanceur doit refuser un ancien moteur, même déjà importé."""
import json
from pathlib import Path
import subprocess
import sys

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
LANCEUR = ICI / 'executer_boucle_verifiee.py'


def test_verification_depuis_racine_identifie_paquet():
    p = subprocess.run([sys.executable, '-B', str(LANCEUR), '--verifier'],
                       cwd=RACINE, capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    preuves = json.loads(p.stderr)['moteur_verifie']
    assert len(preuves) == 3
    assert all(Path(v['fichier']).is_relative_to(ICI / 'paquet')
               and len(v['sha256']) == 64 for v in preuves.values())


def test_moteur_deja_charge_refuse_sans_rechargement():
    code = '''import runpy, sys
import chrysalide.arc3.logique.theorie as theorie
avant = theorie
m = runpy.run_path(sys.argv[1])
try:
    m['configurer']()
except RuntimeError as erreur:
    assert 'hors paquet' in str(erreur)
else:
    raise AssertionError('Un moteur ancien doit être refusé')
assert sys.modules['chrysalide.arc3.logique.theorie'] is avant
'''
    p = subprocess.run([sys.executable, '-B', '-c', code, str(LANCEUR)],
                       cwd=RACINE, capture_output=True, text=True, timeout=30,
                       env={k:v for k,v in __import__('os').environ.items() if k != 'PYTHONPATH'})
    assert p.returncode == 0, p.stderr
