"""Reconstitue la mémoire puis compare les perceptions sans cible fournie."""
import argparse,json
from pathlib import Path
from reprise_niveaux_observes import preparer
from perception_clics_couples import proposer
from chaine_agent_integree import lots
from avancer_agent_relais import sauver_agent

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--agent',type=Path,required=True);a=p.parse_args()
    agent,_,meta=preparer(a.source,exiger_plan=False)
    for i,c in enumerate(proposer(agent.images,lots(agent.actions),agent.films)):
        agent._admettre(f'perception_clics/{i}',c)
    agent.reconstruction=False;agent.releves_p1.add(len(agent.actions)//8)
    agent.utilite_sondes=True
    sauver_agent(agent,a.agent)
    print(json.dumps({'niveau':meta['niveau'],'hypotheses':list(agent.chaines),'historique':len(agent.actions)}))
