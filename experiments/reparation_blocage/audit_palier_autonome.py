"""Validation hors SDK de la décision commune, depuis une copie empreintée."""
import argparse, hashlib, json, time, resource
from pathlib import Path
from avancer_agent_relais import charger_agent, sauver_agent, decision_suivante
from session_chaine_generique import configurer_recherche
from chaine_agent_integree import canon
from boucle_agent_integree import empreintes


def main(args):
    args.sortie.mkdir(parents=True,exist_ok=False)
    original=args.source.read_bytes();sha=hashlib.sha256(original).hexdigest()
    a=charger_agent(args.source)
    assert not a.attente, 'Une décision est déjà en attente : audit non causal'
    assert not any(c.plan and not c.refute for c in a.chaines.values()), 'Plan déjà présent'
    configurer_recherche(a,activation=True,workers=args.workers)
    sources=empreintes();j=len(a.journal)
    debut=time.process_time();mur=time.monotonic()
    d=decision_suivante(a,args.offre)
    cpu=time.process_time()-debut
    owner=d.get('modele_plan');plan=None;preuve=None
    if owner:
        plan=[canon(d['actions'][0]),*d.get('suite_plan',[])]
        preuve=a.chaines[owner].verifier_plan(plan)
    nouveaux=a.journal[j:]
    paliers=[r for r in nouveaux if r.get('type')=='recherche_selection_prolongee']
    assert original==args.source.read_bytes(), 'Source modifiée'
    assert sources==empreintes(sources), 'Runtime modifié'
    rapport={'source':str(args.source),'source_sha256':sha,'actions_observees':len(a.actions),
        'sdk_actions':0,'workers':args.workers,'rss_parent_pic':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'rss_unite':'octets sur macOS, kilo-octets sur Linux','cpu_parent_s':cpu,'cpu_enfants_s':sum(r.get('cpu_enfants_s',0) for r in paliers),
        'mur_s':time.monotonic()-mur,'decision':d,'plan':plan,'verification':preuve,
        'paliers':paliers,'journal_nouveau':nouveaux,'sources':sources,
        'source_inchangee':True,'intervention':'activation option commune, aucun choix de modèle/plan/archives interne'}
    rapport['cpu_total_s']=cpu+rapport['cpu_enfants_s']
    (args.sortie/'rapport.json').write_text(json.dumps(rapport,indent=2,default=str))
    sauver_agent(a,args.sortie/'agent.pkl')
    print(json.dumps({'decision':d.get('statut'),'owner':owner,'plan_longueur':len(plan) if plan else None,
        'plan_valide':bool(preuve and preuve[0]),'paliers':len(paliers),'cpu_total_s':rapport['cpu_total_s'],'sdk_actions':0}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True)
    p.add_argument('--offre',type=int,nargs='+',required=True);p.add_argument('--workers',type=int,choices=(1,2),default=1);main(p.parse_args())
