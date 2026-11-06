"""Révérifie un plan calculé et l'adopte dans le contrôleur, sans action SDK."""
import argparse,json
from pathlib import Path
from avancer_agent_relais import charger_agent,sauver_agent
from buts_modele_conserve import candidats,actions_modele

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--agent',type=Path,required=True);p.add_argument('--bilan',type=Path,required=True);a=p.parse_args()
    agent=charger_agent(a.agent);b=json.loads(a.bilan.read_text())
    if b['observations']!=len(agent.actions):raise ValueError('Historique a changé')
    source=next(iter(agent.chaines.values()))
    c=next(c for but,c in candidats(source,actions_modele(source,[6])) if json.dumps(but)==json.dumps(b['but_herite']))
    r=next(r for r in b['resultats'] if r['valide'])
    adoption=c.adopter_plan(r['plan'],origine='portefeuille_cpu_herite')
    if adoption['statut']!='plan_simule_valide':raise ValueError(adoption)
    agent.chaines['p1_but_hypothese']=c;agent.reconstruction=False
    agent.releves_p1.add(len(agent.actions)//8)
    agent.journal.append({'type':'portefeuille_cpu_adopte','bilan':str(a.bilan.resolve()),'longueur':len(r['plan'])})
    sauver_agent(agent,a.agent);print({'plan_admis':len(r['plan'])})
