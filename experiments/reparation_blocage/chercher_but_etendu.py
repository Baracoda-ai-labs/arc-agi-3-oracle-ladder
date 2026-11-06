"""Réutilise le planificateur de théorie, puis vérifie le plan dans le programme exporté."""
import json,time,argparse
from pathlib import Path
from avancer_agent_relais import charger_agent
from buts_modele_conserve import candidats,actions_modele
from chrysalide.arc3.logique.plan import planifier
from chrysalide.arc3.moteur import _lot_c
from chaine_coherente import Chaine

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--agent',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);a=p.parse_args()
    agent=charger_agent(a.agent);source=next(iter(agent.chaines.values()));prior=agent.theorie_precedente.but
    c=next(c for b,c in candidats(source,actions_modele(source,[6])) if b[:3]==prior and len(b)>3)
    tr=c.perception.tr;th=c.perception.th_releve
    actions=[tr.action_cases(('clic',x[2],x[1])) for x in c.actions]
    t=time.monotonic();cpu=time.process_time()
    seq,n=planifier(th,tr.etat(agent.images[-1]),tr.taille,actions,limite=200000,deadline=cpu+30,guide=True)
    plan=[Chaine.action_tuple(_lot_c(x,tr)) for x in seq] if seq else None
    ok,preuve=c.verifier_plan(plan) if plan else (False,None)
    r={'but_herite':th.but,'observations':len(agent.actions),'sdk_actions':0,'diagnostic':c.diagnostic_extension_but,
       'resultats':[{'methode':'theorie_heritee','valide':ok,'plan':plan,'preuve':preuve,'noeuds':n,'mur_s':time.monotonic()-t,'cpu_s':time.process_time()-cpu}]}
    a.sortie.write_text(json.dumps(r,indent=2,default=int));print(json.dumps(r,default=int))
