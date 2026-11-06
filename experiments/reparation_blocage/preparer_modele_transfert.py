"""Reconstruire la mémoire du contrôleur sur une trace gagnante, sans SDK."""
from pathlib import Path
import json,hashlib
import numpy as np
from chaine_agent_integree import AgentIntegre

def depuis_trace(base,offre):
    base=Path(base);raw=base.with_suffix('.json');j=json.loads(raw.read_text());z=np.load(base.with_suffix('.npz'));rows=j['rows'];actions=[r['action'] for r in rows]
    if not rows or rows[-1]['levels_completed']<=rows[0]['levels_completed']:raise ValueError('Trace sans victoire de niveau')
    a=AgentIntegre([z['images'][0]],[],[],[],decouverte_courte=True,routage_classes=True)
    for i,action in enumerate(actions):
        d=a.decider(offre,secondes=4)
        if not d.get('actions') or d['actions'][0]!=action:raise ValueError(f'Décision de trace différente au coup{i+1}')
        if i==len(actions)-1:
            modele=a.consolider_modele_jeu(d['modele_plan'],{'trace':str(base),'sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'victoire_sdk_archivee':True,'actions_acquisition':len(actions)})
            return modele,actions,z['images'],a.journal
        a.observer(action,z['images'][i+1],z[f'film_{i+1}'],'continue')
