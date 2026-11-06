"""Recherche unique sur transfert initial ; aucune action SDK."""
import cloudpickle,json,time,hashlib
from pathlib import Path
from transfert_roles import reaffecter
from plan_selection_dynamique import chercher
from chaine_agent_integree import canon

p=Path('runs/ka59_controleur_corrige72_1/agent.pkl')
raw=p.read_bytes();a=cloudpickle.loads(raw)
c,transfert=reaffecter(a.modele_gagnant,a.images[-1],[('UP',),('DOWN',),('LEFT',),('RIGHT',)])
t=time.process_time()
plan,infos=chercher(c,c.perception,secondes=30,max_noeuds=100000)
validation=c.verifier_plan(plan) if plan else None
out={'source':str(p),'source_sha256':hashlib.sha256(raw).hexdigest(),'sdk':False,
     'etat':'entree_N2','budget_secondes':30,'budget_noeuds':100000,'cpu':time.process_time()-t,
     'plan':plan,'infos':infos,'validation':validation,'transfert':transfert,
     'sources_sha256':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in
                       ('transfert_roles.py','plan_selection_dynamique.py','audit_plan_transfert_roles_n2.py')}}
Path('AUDIT_PLAN_TRANSFERT_ROLES_N2.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ('cpu','plan','infos','validation')},ensure_ascii=False))
