"""Tous pixels et images, contrôle d'un outil généré ; aucune règle ni jeu exécuté."""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI / 'paquet'))
from propositions_python import Proposition


def main():
    sortie = ICI / 'controle_outil_film_arc.json'
    if sortie.exists():
        raise FileExistsError(sortie)
    source = Path('/Users/ts/models/chrysalide3/experiments/films_p1/runs/v3_g3/sp80/N1/partie.npz')
    with np.load(source) as archive:
        frames = np.concatenate([archive['images'][1:2], archive['film_2']], axis=0)
    assert 1 < len(frames) <= 64
    films = frames.reshape(len(frames), -1).tolist()
    code = (ICI / 'essai_outil_27b/reponse_brute.txt').read_text()
    p = Proposition(code)
    reference = int(np.count_nonzero(frames[1:] != frames[:-1]))
    t = time.process_time()
    complet = p.tester_outil('compter_transitions', [((films,), reference)])
    cpu_complet = time.process_time() - t
    t = time.process_time()
    obtenu = sum(p.appeler('compter_transitions', films[i:i + 2]) for i in range(len(films) - 1))
    bilan = {'preuve': 'trace ARC uniquement', 'nouveaux_appels_sdk': 0, 'nouveaux_appels_ia': 0,
        'source': str(source), 'film': 'film_2', 'images_film': len(frames) - 1,
        'images_avec_avant': len(frames), 'dimensions': list(frames.shape[1:]),
        'donnees_sha256': hashlib.sha256(frames.tobytes()).hexdigest(),
        'appel_complet': complet, 'cpu_complet_s': cpu_complet,
        'par_paires': {'appels': len(frames) - 1, 'obtenu': obtenu, 'reference': reference,
                       'conforme': obtenu == reference, 'cpu_total_s': time.process_time() - t},
        'limite': 'compte des changements visuels ; aucune loi ou victoire inferree'}
    sortie.write_text(json.dumps(bilan, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(bilan, ensure_ascii=False))
    assert obtenu == reference


if __name__ == '__main__':
    main()
