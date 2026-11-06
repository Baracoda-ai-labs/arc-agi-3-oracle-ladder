"""Reconstruction d'un AST déjà journalisé, coup terminal et RESET observés ; zéro SDK."""
import argparse,copy,hashlib,json,time
from pathlib import Path
import numpy as np
from avancer_agent_relais import charger_agent,sauver_agent
from chaine_agent_integree import AgentIntegre,lots,canon
from chaine_coherente import Chaine,empreinte
from readmission_episode import installer


def main(source,reset,sortie):
    cpu=time.process_time();blob=source.read_bytes();a=charger_agent(source)
    rows=[e for e in a.journal if e.get('type')=='observation' and e.get('coup')==len(a.actions)]
    final=rows[-1]; candidates={r['nom'] for r in final['resultats'] if r.get('image_exacte') and r['statut']=='fin_sans_victoire'}
    from roles_observes import PerceptionRoles
    admissions=[e for e in a.journal if e.get('type')=='admission' and e.get('nom')=='roles_1']
    prefixe=admissions[-1]['controle']['transitions']
    vue=PerceptionRoles(a.images[:prefixe+1],a.actions[:prefixe],films=a.films[:prefixe],
                        clics_negatifs=a.decouverte_courte)
    # Les indices viennent des modèles déjà journalisés, jamais d'une nouvelle induction.
    journal_precedent=[e for e in a.journal if e.get('type')=='observation' and e.get('coup')==len(a.actions)-1][-1]
    sigs={r['nom']:r.get('atms',{}).get('labels',{}) for r in journal_precedent['resultats']}
    local=AgentIntegre(a.images[:-1],a.actions[:-1],a.films[:-1],a.issues[:-1],reparation=False)
    preuves=[]
    for nom in sorted(candidates):
        if not nom.startswith('roles_'):continue
        p=vue.programme(vue.buts[int(nom.split('_')[-1])]);sha=empreinte(p)
        if 'modele:'+sha not in sigs.get(nom,{}):raise ValueError('AST non identique au modèle journalisé : '+nom)
        c=Chaine(vue,p,[g.tolist() for g in local.images],lots(local.actions),[],films=local.films)
        check,state=c.rejouer()
        if state is None:raise ValueError('Préfixe causal refusé')
        c.activer_atms();c.plan={'actions':[list(canon(a.actions[-1]))],**c.signature(),'origine':'rejeu_decision_reelle_archivee'}
        local.chaines[nom]=c;preuves.append({'nom':nom,'ast_sha':sha,'controle99':check})
    if not local.chaines:raise ValueError('Aucun AST historique reconstruit')
    local.attente={'statut':'experience_archivee','actions':[a.actions[-1]],'modeles':list(local.chaines)}
    obs=local.observer(a.actions[-1],a.images[-1],a.films[-1],'defaite',source='trace')
    with np.load(reset,allow_pickle=False) as z:image=z['images'][0]
    nouveau=AgentIntegre([image],[],[],[])
    nouveau.modeles_episode_precedent=copy.deepcopy(local.modeles_physiques_fin_episode)
    nouveau.journal=copy.deepcopy(local.journal)
    from memoire_episodes import retenir_defaite
    nouveau.memoire_episodes=retenir_defaite(local,[1,2,3,4],1)
    from session_chaine_generique import observations_tentatives
    nouveau.observations_episodes=observations_tentatives(local)
    essais=installer(nouveau,[1,2,3,4])
    assert nouveau.chaines and nouveau.memoire_episodes and not nouveau.actions
    assert source.read_bytes()==blob
    sortie.mkdir(parents=True,exist_ok=False);sauver_agent(nouveau,sortie/'agent.pkl')
    rapport={'sdk':0,'source':str(source),'source_sha256':hashlib.sha256(blob).hexdigest(),
        'reset_observe':str(reset),'reset_sha256':hashlib.sha256(reset.read_bytes()).hexdigest(),
        'source_inchangee':True,'perception_reconstruite_prefixe_historique':prefixe,'essai_preliminaire_refuse':'perception roles_0 du11 ne correspond pas aux AST99 ; aucun rejeu ni admission sur cet essai','preuves_ast':preuves,'terminal':[{k:r.get(k)for k in ('nom','statut','image_exacte')}for r in obs['resultats']],
        'readmission':essais,'cpu_parent':time.process_time()-cpu,'limite':'Seuls AST historiques roles reconstruits ; aucun choix futur ni sûreté prouvés'}
    (sortie/'rapport.json').write_text(json.dumps(rapport,indent=2,default=str));print(json.dumps({'admis':list(nouveau.chaines),'cpu':rapport['cpu_parent']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--reset',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);x=p.parse_args();main(x.source,x.reset,x.sortie)
