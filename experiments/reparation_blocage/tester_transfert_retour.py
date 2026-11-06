"""Porte de transfert figée sur population publique autorisée ; aucun SDK."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI/'paquet')]

from contact_observe import induire, rectangles

INTERDITS = {'vc33', 'tu93', 'wa30', 's5i5', 'cn04', 'm0r0'}


def main():
    sortie = ICI/'bilan_transfert_retour.json'
    if sortie.exists():
        raise FileExistsError(sortie)
    reference = json.loads((ICI/'bilan_publics_rapide.json').read_text())
    cas = []
    for fiche in sorted(reference['niveaux'], key=lambda f: (f['jeu'], f['niveau'])):
        jeu = fiche['jeu']
        if jeu in INTERDITS or fiche['niveau'] != 1:
            continue
        r = {'jeu': jeu, 'reference_n1_gagne': fiche['ref_victoire']}
        cas.append(r)
        if not fiche['ref_victoire']:
            r['statut'] = 'prerequis_n1_gagne_absent'
            continue
        base = ICI/'runs/publics_ref_g0'/jeu/'N1'
        rows = json.loads((base/'partie.json').read_text())['rows']
        with np.load(base/'partie.npz') as a:
            images = a['images'].copy()
        r['coups_archives'] = len(rows)
        r['sha_archive'] = hashlib.sha256((base/'partie.npz').read_bytes()).hexdigest()
        # Canonisation du code d'action SDK ; clics exclus par l'inducteur inchangé.
        actions = [row['action'][0] if isinstance(row['action'], list) else row['action'] for row in rows]
        r['actions_disponibles_dans_trace'] = sorted(set(actions), key=str)
        formes = []
        for couleur in sorted(set(images[0].ravel().tolist())):
            try:
                rectangles(images[0], couleur)
                formes.append(couleur)
            except ValueError:
                pass
        r['couleurs_avec_deux_rectangles_initiaux'] = formes
        try:
            h = induire(images, actions, True)
            r['statut'] = 'induction_acceptee_a_examiner'
            r['couleur_induite'] = h['couleur']
        except ValueError as e:
            r.update(statut='induction_refusee', raison=str(e))
        except Exception as e:  # noqa: BLE001 — erreur de banc consignée, jamais acceptée
            r.update(statut='erreur_induction', raison=repr(e))
        print(json.dumps(r, ensure_ascii=False), flush=True)
    bilan = {'nouveaux_appels_sdk': 0, 'nouveaux_appels_ia': 0,
             'code_sha': {n: hashlib.sha256((ICI/n).read_bytes()).hexdigest()
                          for n in ('contact_observe.py', 'apprendre_retour.py')},
             'preuve': 'Porte sur traces de développement, pas de victoire ou défaite SDK nouvelle', 'cas': cas}
    sortie.write_text(json.dumps(bilan, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'population': len(cas), 'acceptes': sum(r['statut']=='induction_acceptee_a_examiner' for r in cas),
                      'refus': sum(r['statut']=='induction_refusee' for r in cas),
                      'prerequis_absent': sum(r['statut']=='prerequis_n1_gagne_absent' for r in cas)}))


if __name__ == '__main__':
    main()
