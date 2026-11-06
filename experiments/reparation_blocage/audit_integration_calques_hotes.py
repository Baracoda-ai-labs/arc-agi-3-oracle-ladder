"""Audit archive C2 : six observations seulement, décision suivante sans SDK."""
import json
import time
from pathlib import Path
import cloudpickle
import numpy as np
from chaine_agent_integree import AgentIntegre, canon
from transfert_modele_c import reaffecter
from revision_perception_selection import porteur_boite
from chrysalide.arc3.logique.export_langage import exporter

R = Path(__file__).parent
z = np.load(R/'runs/session_re86_transfert_c2/N2/partie.npz')
rows = json.loads((R/'runs/session_re86_transfert_c2/N2/partie.json').read_text())['rows']
s = cloudpickle.loads((R/'runs/session_re86_buts_conserves1/modele_gagnant_local.pkl').read_bytes())
c,_ = reaffecter(s,z['images'][0],[canon(k) for k in (1,2,3,4,5)])
a = AgentIntegre([z['images'][0]], [], [], [], revision_projection=True, exploration_p1=True,limite=200)
a.chaines={'transfert':c};a.reconstruction=False;a.releves_p1={0}
for i in range(6):
    action=rows[i]['action'];d={'actions':[action],'predictions':[[]]}
    a._suivre_experience(d);a.attente=d
    a.observer(action,z['images'][i+1],z[f'film_{i+1}'],'continue')
rap={'sdk':0,'observations':len(a.actions),'modeles':list(a.chaines)}
for name,c in a.chaines.items():
    if name.endswith('/calques_hotes'):
        with porteur_boite():
            p,non=exporter(c.perception.th_releve,c.perception.tr.taille)
        rap.update(revision=name,controle=c.rejouer()[0],theorie_programme_synchro=p==c.programme and not non,
                   but_conserve=c.perception.th_releve.but is not None,
                   historique_complet=len(c.lots)==6 and len(c.grilles)==7)
t=time.monotonic();d=a.decider([1,2,3,4,5],secondes=10)
rap.update(decision=d,secondes_decision=time.monotonic()-t,action7_archive=rows[6]['action'],
           action7_differente=bool(d.get('actions')) and d['actions'][0]!=rows[6]['action'])
(R/'AUDIT_INTEGRATION_CALQUES_HOTES.json').write_text(json.dumps(rap,indent=2,default=str)+'\n')
resume={k:v for k,v in rap.items() if k!='decision'}
resume['decision']={k:d.get(k) for k in ('statut','origine','actions','but','modele_revision')}
print(json.dumps(resume,default=str))
