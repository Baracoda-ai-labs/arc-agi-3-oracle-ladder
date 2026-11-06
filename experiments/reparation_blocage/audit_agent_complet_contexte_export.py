"""Agent SDK complet, mais observations strictement préfixées de l'archive.

Arrêt avant l'observation du premier coup différent ; aucun propriétaire SDK.
"""
import hashlib
import json
import time
from pathlib import Path
import cloudpickle
import numpy as np
from session_chaine_generique import reconstituer_gagnant, agent_transfere

R=Path(__file__).parent
archive=R/'runs/session_re86_forme_occultee1/N2/partie'
z=np.load(archive.with_suffix('.npz'))
rows=json.loads(archive.with_suffix('.json').read_text())['rows']
ancien,_,_,b=reconstituer_gagnant(R/'runs/session_re86_buts_conserves1')
offre=b['actions_disponibles']
a=agent_transfere(ancien,z['images'][0],offre)
rep=R/'runs/audit_agent_complet_contexte_export'
rep.mkdir(exist_ok=True)
fichiers=[R/n for n in ('chaine_agent_integree.py','buts_modele_conserve.py','transfert_modele_c.py',
                       'revision_perception_selection.py','revision_calques_hotes.py','revision_forme_occultee.py')]
fichiers.append(R/'paquet/chrysalide/arc3/moteur.py')
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in fichiers}
resultats=[]
for _ in range(20):
    assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in fichiers}, 'Runtime modifié pendant audit'
    i=len(a.actions)
    folder=rep/f'decision_{i+1:03}'
    folder.mkdir(exist_ok=True)
    source=folder/'prefixe'
    np.savez_compressed(source.with_suffix('.npz'),images=z['images'][:i+1],
                        **{f'film_{j}':z[f'film_{j}'] for j in range(1,i+1)})
    source.with_suffix('.json').write_text(json.dumps({'rows':rows[:i]})+'\n')
    avant=cloudpickle.dumps(a)
    t=time.monotonic()
    d=a.decider(offre,folder,source,secondes=10)
    item={'coup':i+1,'secondes':time.monotonic()-t,'actions':d.get('actions'),
          'origine':d.get('origine'),'statut':d.get('statut'),
          'action_archive':rows[i]['action'],'modeles':list(a.chaines),
          'modele_revision':d.get('modele_revision'),'modele_plan':d.get('modele_plan')}
    identique=bool(d.get('actions')) and d['actions'][0]==rows[i]['action']
    item['identique_archive']=identique
    resultats.append(item)
    (folder/'decision.json').write_text(json.dumps(d,default=str,indent=2)+'\n')
    print(json.dumps(item),flush=True)
    if not identique:
        (folder/'agent_avant_decision.pkl').write_bytes(avant)
        (folder/'agent_apres_decision.pkl').write_bytes(cloudpickle.dumps(a))
        break
    observation=a.observer(rows[i]['action'],z['images'][i+1],z[f'film_{i+1}'],'continue')
    (folder/'observation.json').write_text(json.dumps(observation,default=str,indent=2)+'\n')
rapport={'sdk':0,'source':'agent_transfere(reconstituer_gagnant(N1),imageN2,offre)',
         'observations_finales':len(a.actions),'decisions':resultats,
         'premiere_difference':next((r['coup'] for r in resultats if not r['identique_archive']),None),
         'runtime_sha256':hashes,'journal':a.journal}
(R/'AUDIT_AGENT_COMPLET_CONTEXTE_EXPORT.json').write_text(json.dumps(rapport,default=str,indent=2)+'\n')
