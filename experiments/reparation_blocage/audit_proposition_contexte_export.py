"""Aucun runtime modifié : recherche de buts via proposition chargée en mémoire."""
from pathlib import Path
import json
import cloudpickle
from test_revision_forme_occultee import cas
from transfert_modele_c import reaffecter
from chaine_agent_integree import canon,lots
from revision_perception_selection import porteur_boite
from revision_forme_occultee import reviser
from proposition_contexte_export import charger_proposition
R=Path(__file__).parent
_,z,rows=cas.__wrapped__()
s=cloudpickle.loads((R/'runs/session_re86_buts_conserves1/modele_gagnant_local.pkl').read_bytes())
s,_=reaffecter(s,z['images'][0],[canon(i) for i in (1,2,3,4,5)])
s,_=charger_proposition('revision_perception_selection.py').reviser(s,z['images'][0],z['images'][1],canon(5),z['film_1'])
with porteur_boite():
 c,d=reviser(s,z['images'][:12].tolist(),lots([r['action'] for r in rows[:11]]),[z[f'film_{i}'] for i in range(1,12)])
b=charger_proposition('buts_modele_conserve.py')
trouve,essais=b.chercher({'source_reparee11':c},c.actions,secondes=10)
resultat={'sdk':0,'runtime_modifie':False,'prefixe':11,'essais':essais,
          'plan_trouve':trouve is not None,'plan':trouve.plan if trouve else None}
(R/'AUDIT_PROPOSITION_CONTEXTE_EXPORT.json').write_text(json.dumps(resultat,default=str,indent=2)+'\n')
print(json.dumps({'essais':len(essais),'statuts':[x['statut'] for x in essais],
                  'plan_trouve':trouve is not None,'actions':trouve.plan['actions'] if trouve else None}))
