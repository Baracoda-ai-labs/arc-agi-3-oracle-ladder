"""Portefeuille historique sur modèle observé et but hérité, sans SDK."""
import argparse,json,time,resource
from pathlib import Path
from avancer_agent_relais import charger_agent
from buts_modele_conserve import candidats,actions_modele
from chrysalide.arc3.logique.plan_langage import planifier_langage
from chrysalide.arc3.logique.plan_portefeuille import portefeuille


def mesurer(source,sortie,secondes,processus=2,parallele_seul=False,extension=False):
    a=charger_agent(source);prior=a.theorie_precedente.but
    source_c=next(iter(a.chaines.values()))
    c=next(c for but,c in candidats(source_c,actions_modele(source_c,[6])) if (but[:3]==prior and len(but)>3) == extension and but[:3]==prior)
    prior=c.perception.th_releve.but
    sortie.mkdir(parents=True,exist_ok=False)
    results=[]
    for methode in ([f'parallele_{processus}'] if parallele_seul else ['sequentiel',f'parallele_{processus}']):
        _,(pc,sc)=c.rejouer();t=time.monotonic();cpu=time.process_time();r=resource.getrusage(resource.RUSAGE_CHILDREN)
        if methode=='sequentiel':
            plan,infos=planifier_langage(c.programme,sc,c.actions,recherche='but',secondes=secondes,noeuds=20000,compiler=False,etat=pc.etat)
        else:
            plan,infos=portefeuille(c.programme,sc,c.actions,secondes=secondes,noeuds=20000//processus,processus=processus,etat=pc.etat,memoire_mio=2048)
        rr=resource.getrusage(resource.RUSAGE_CHILDREN)
        wall=time.monotonic()-t;total=time.process_time()-cpu+rr.ru_utime+rr.ru_stime-r.ru_utime-r.ru_stime
        valide,preuve=c.verifier_plan(plan) if plan else (False,None)
        results.append(dict(methode=methode,mur_s=wall,cpu_total_s=total,plan=plan,valide=valide,preuve=preuve,infos=infos))
    report={'but_herite':prior,'observations':len(a.actions),'budget_mur_par_recherche':secondes,
        'noeuds_max_total':20000,'processus_paralleles':processus,'cpu_budgets_non_egaux':True,'sdk_actions':0,'resultats':results}
    (sortie/'bilan.json').write_text(json.dumps(report,default=int,indent=2));print(json.dumps(report,default=int))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--agent',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);p.add_argument('--secondes',type=float,default=10);p.add_argument('--processus',type=int,default=2);p.add_argument('--parallele-seul',action='store_true');p.add_argument('--extension',action='store_true');a=p.parse_args();mesurer(a.agent,a.sortie,a.secondes,a.processus,a.parallele_seul,a.extension)
