"""Nouveau contrôleur depuis observations ; aucun SDK, aucun accès au jeu."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from session_chaine_generique import nouvel_agent
from avancer_agent_relais import sauver_agent,aligner
from session_sdk_observee import empreinte_image
from issues_observees import issue_sdk


def preparer(source,sortie):
    source=Path(source);sortie=Path(sortie)
    etat=json.loads((source/'etat.json').read_text())
    niveau=etat['niveau'];tentative=etat.get('tentative',1)
    if niveau!=1 or tentative!=1 or etat.get('resets_retry',0):
        raise ValueError('Sans snapshot, reconstruction limitée au premier épisode N1 sans RESET')
    trace=source/'N1/partie'
    chemins=[source/'etat.json',source/'journal.json',trace.with_suffix('.json'),trace.with_suffix('.npz')]
    empreintes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in chemins}
    rows=json.loads(trace.with_suffix('.json').read_text())['rows']
    if any(r['action']==0 for r in rows):raise ValueError('RESET présent : épisodes à séparer')
    if len(rows)!=etat['coups_reels']:raise ValueError('Compteur archive désaligné')
    with np.load(trace.with_suffix('.npz')) as z:
        images=z['images'].copy()
        films=[z[f'film_{i+1}'].copy() for i in range(len(rows))]
    if len(images)!=len(rows)+1:raise ValueError('Images/actions désalignées')
    issues=[issue_sdk(r['state'],r['levels_completed'],niveau-1) for r in rows]
    if any(i!='continue' for i in issues):raise ValueError('Épisode terminal : migration active refusée')
    a=nouvel_agent(images,[r['action'] for r in rows],films,issues,
        graine_exploration=etat.get('graine_exploration',0))
    a.commandes_connues.update(r['action'] for r in rows if isinstance(r['action'],int))
    a.journal=json.loads((source/'journal.json').read_text())
    # Les événements servent de preuves, pas de restauration implicite d'objets Python.
    for event in a.journal:
        if event.get('type')=='configuration_graine' and event.get('graine_exploration')!=a.graine_exploration:
            raise ValueError('Graine journal/état contradictoire')
    pertes=['hypotheses et caches internes non serialises, a revalider',
            'questions de revision deja resolues non restaurees comme autorite',
            'plans en attente non adoptes sans snapshot verifie']
    rapport={'statut':'nouveau_controleur_sur_prefixe','meme_instance':False,
        'source':str(source),'jeu':etat['jeu'],'niveau':niveau,'actions_observees':len(rows),
        'actions_reelles_nouvelles':0,'reacces_effectue':0,'initialisations_sdk':0,
        'sdk_rattache':False,'etat_sdk_original':etat,'empreintes_sources':empreintes,
        'pertes_ou_revalidation':pertes,'modeles_survivants_source':etat.get('modeles_survivants',[]),
        'observations_films_et_journal_conserves':True,
        'limite':'aucun transfert du SDK actif ; rattachement exige un relais deja proprietaire de ce meme etat'}
    a.journal.append({'type':'reconstruction_controleur_archive',**{k:v for k,v in rapport.items() if k!='etat_sdk_original'}})
    etat_archive={**etat,'trace':str(trace.resolve()),'image_sha256':empreinte_image(images[-1])}
    aligner(a,etat_archive)
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=empreintes[str(p)] for p in chemins):
        raise ValueError('Archive modifiée pendant préparation')
    sortie.mkdir(parents=True,exist_ok=False)
    sauver_agent(a,sortie/'agent.pkl')
    (sortie/'rapport.json').write_text(json.dumps(rapport,indent=2))
    return rapport


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--sortie',type=Path,required=True);args=p.parse_args()
    print(json.dumps(preparer(args.source,args.sortie),indent=2))
