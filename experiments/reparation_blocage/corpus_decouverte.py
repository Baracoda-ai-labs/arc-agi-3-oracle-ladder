"""Exporte des décisions enregistrées ; aucun SDK, oracle ou entraînement."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from evidence_films import Films

def sauver(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))

def exemple(images, films, actions, coup, decision, observation):
    """Entrée disponible AVANT le coup ; résultat séparé, sans label de bonne action."""
    if not 1 <= coup <= len(actions):
        raise ValueError("Coup hors trace")
    preuve = Films()
    for i in range(coup):
        preuve.ajouter(images[i], films[i])
    # Films vérifie toutes les dimensions, vérifier aussi les observations finales.
    if any(not np.array_equal(films[i][-1], images[i+1]) for i in range(coup)):
        raise ValueError("Film non aligné")
    if decision['actions'][0] != actions[coup-1]:
        raise ValueError("Décision/action non alignées")
    entree = {
        'actions_passees': actions[:coup-1], 'action_proposee': actions[coup-1],
        'predictions': decision.get('predictions', []),
        'modeles': decision.get('modeles', []),
        'origine': decision.get('origine'),
        'coups_payes_avant': coup-1,
        'films_passes_sha256': preuve.signatures()[:-1],
    }
    payload = np.asarray(images[:coup], dtype=np.int16).tobytes()
    ident = hashlib.sha256(payload + json.dumps(entree, sort_keys=True).encode()).hexdigest()
    resultats = [{k:v for k,v in x.items() if k != 'atms'}
                 for x in observation.get('resultats', [])]
    cible = {
        'resultats': resultats, 'film_resultat_sha256': preuve.signatures()[-1],
        'action_optimale': None, 'regle_correcte': None,
        'preuve': 'observation_jeu_enregistree',
        'usage': 'diagnostic_prediction_uniquement',
        'imitation_action_autorisee': False,
    }
    return ident, entree, cible

def exporter(runs, sortie):
    sortie.mkdir(parents=True, exist_ok=False)
    lignes, vus, doublons = [], set(), 0
    for run in runs:
        b=json.loads((run/'bilan.json').read_text())
        rows=json.loads((run/'N1/partie.json').read_text())['rows']
        actions=[x['action'] for x in rows]
        with np.load(run/'N1/partie.npz') as z:
            images=z['images']
            films=[z[f'film_{i+1}'] for i in range(len(actions))]
            for folder in sorted(run.glob('decision_*')):
                obs=folder/'observation.json'
                if not obs.exists():continue
                observation=json.loads(obs.read_text())
                coup=observation['coup']
                decision=json.loads((folder/'decision.json').read_text())
                ident, entree, cible=exemple(images,films,actions,coup,decision,observation)
                if ident in vus:
                    doublons+=1;continue
                vus.add(ident)
                p=sortie/ident;p.mkdir()
                # Fichiers physiquement séparés : le chargeur élève ne reçoit pas le futur.
                np.savez_compressed(p/'entree.npz', images=images[:coup],
                    **{f'film_{i+1}':films[i] for i in range(coup-1)})
                np.savez_compressed(p/'resultat.npz', image=images[coup], film=films[coup-1])
                sauver(p/'entree.json',entree);sauver(p/'resultat.json',cible)
                lignes.append({'id':ident,'provenance':str(folder.resolve()),
                    'groupe_jeu':b['jeu'], 'partition':'developpement_deja_consulte',
                    'coups_payes_avant':coup-1, 'resultats':len(cible['resultats']),
                    'imitation_action_autorisee':False})
    sauver(sortie/'index.json',lignes)
    manifest={str(p.relative_to(sortie)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sortie.rglob('*') if p.is_file()}
    sauver(sortie/'manifest.json',manifest)
    bilan={'exemples':len(lignes),'doublons_ignores':doublons,
           'avec_confrontation':sum(x['resultats']>0 for x in lignes),
           'jeux':sorted({x['groupe_jeu'] for x in lignes}),
           'exemples_action_optimale':0,'entrainement_execute':False,
           'nouveaux_coups':0,'fichiers':len(manifest)}
    sauver(sortie/'bilan.json',bilan)
    return bilan

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--run',type=Path,action='append',required=True)
    p.add_argument('--sortie',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(exporter(a.run,a.sortie),ensure_ascii=False))
