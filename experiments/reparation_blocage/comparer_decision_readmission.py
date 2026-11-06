"""Ablation sur le même RESET archivé ; aucune commande SDK."""
import argparse,copy,json,time,hashlib,resource
from pathlib import Path
from avancer_agent_relais import charger_agent
from session_chaine_generique import nouvel_agent,configurer_composition,configurer_recherche
from readmission_episode import installer


def main(sortie=None):
    r=Path(__file__).parent/'runs'; source=r/'audit_readmission_episode100_1/agent.pkl'
    ancien_p=r/'ka59_n1_budget_long_meme_sha_1/session/N1/agent_avant_retry_1.pkl'
    blobs={str(p):p.read_bytes()for p in (source,ancien_p)}
    mem=charger_agent(source);ancien=charger_agent(ancien_p)
    offre=list(ancien.offre_avant_action)
    base=nouvel_agent(mem.images,[],[],[],graine_exploration=getattr(ancien,'graine_exploration',0))
    configurer_composition(base,ancien=ancien);configurer_recherche(base,activation=False,workers=1)
    for k in ('memoire_episodes','observations_episodes','modeles_episode_precedent'):
        setattr(base,k,copy.deepcopy(getattr(mem,k)))
    base.commandes_connues=set(ancien.commandes_connues)|{x for x in ancien.actions if isinstance(x,int)}
    base.precedents=copy.deepcopy(ancien.precedents)
    result=[]
    for actif in (False,True):
        a=copy.deepcopy(base)
        if actif:installer(a,offre)
        debut_j=len(a.journal);t=time.process_time();w=time.monotonic();ru=resource.getrusage(resource.RUSAGE_CHILDREN)
        d=a.decider(offre,secondes=5)
        rr=resource.getrusage(resource.RUSAGE_CHILDREN)
        result.append({'readmission':actif,'decision':{k:d.get(k)for k in ('statut','actions','origine','modele_plan')},
            'cpu_parent_s':time.process_time()-t,'mur_s':time.monotonic()-w,
            'cpu_enfants_recoltes_s':rr.ru_utime+rr.ru_stime-ru.ru_utime-ru.ru_stime,
            'modeles':list(a.chaines),'evenements':[e['type']for e in a.journal[debut_j:]],
            'issue_terminale_atteinte_par_plan':{n:c.verifier_plan(c.plan['actions'])[0]for n,c in a.chaines.items()if c.plan}})
    for p,blob in blobs.items():assert Path(p).read_bytes()==blob
    out=sortie or r/'audit_decision_readmission_reset100_1';out.mkdir(exist_ok=False)
    report={'sdk':0,'sources_sha256':{p:hashlib.sha256(b).hexdigest()for p,b in blobs.items()},
            'offre':offre,'budget_identique_s':5,'configuration':'nouvel_agent commun + options source ; recherche prolongée off,1worker',
            'bras':result,'action_modifiee':result[0]['decision']['actions']!=result[1]['decision']['actions'],
            'sources_inchangees':True,'limite':'Un état RESET et deux décisions simulées ; aucun progrès SDK ni sûreté future démontrés'}
    (out/'rapport.json').write_text(json.dumps(report,indent=2,default=str));print(json.dumps(report,default=str))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sortie',type=Path);main(p.parse_args().sortie)
