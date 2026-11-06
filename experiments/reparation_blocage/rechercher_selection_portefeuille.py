"""Deux priorités de recherche, même modèle courant, aucun appel SDK."""
import argparse, json, time
from pathlib import Path
import multiprocessing
import resource
from multiprocessing.connection import wait
from avancer_agent_relais import charger_agent, sauver_agent
from plan_selection_dynamique import chercher
from boucle_agent_integree import empreintes


def rechercher(tache, arreter=None):
    path,nom,poids,secondes=tache
    a=charger_agent(Path(path));c=a.chaines[nom];debut=time.process_time()
    plan,preuve=chercher(c,c.perception,secondes=secondes,max_noeuds=150000,poids_heuristique=poids,arreter=arreter)
    return {'poids':poids,'plan':plan,'preuve':preuve,'cpu_s':time.process_time()-debut}



def _worker(tache, stop, canal):
    try:
        r=rechercher(tache,arreter=stop.is_set)
    except BaseException as exc:
        r={'poids':tache[2],'plan':None,'preuve':{'erreur':repr(exc)}}
    usage=resource.getrusage(resource.RUSAGE_SELF)
    r.update(cpu_s=usage.ru_utime+usage.ru_stime,rss_pic=usage.ru_maxrss)
    canal.send(r);canal.close()


def portefeuille(taches, valider, worker=None):
    """Premier plan validé ; annulation coopérative et récolte avant retour."""
    ctx=multiprocessing.get_context('spawn');stop=ctx.Event()
    processus=[];canaux={};resultats=[];annulation=None
    usage_avant=resource.getrusage(resource.RUSAGE_CHILDREN)
    deadline=time.monotonic()+max(t[3] for t in taches)+30
    try:
        for tache in taches:
            rec,emet=ctx.Pipe(duplex=False)
            p=ctx.Process(target=worker or _worker,args=(tache,stop,emet))
            p.start();emet.close();processus.append(p);canaux[rec]=tache
        while canaux:
            if time.monotonic()>deadline:
                resultats.append({'poids':None,'plan':None,'preuve':{'erreur':'delai_recolte'},'cpu_s':0,'cpu_incomplet':True})
                break
            for canal in wait(list(canaux),timeout=.2):
                tache=canaux.pop(canal)
                try:r=canal.recv()
                except EOFError:r={'poids':tache[2],'plan':None,'preuve':{'erreur':'worker_sans_resultat'},'cpu_s':0,'cpu_incomplet':True}
                canal.close();resultats.append(r)
                if annulation is None and r.get('plan') and valider(r['plan']):
                    r['premier_plan_valide']=True
                    annulation=time.monotonic();stop.set()
                    deadline=min(deadline,annulation+5)
    finally:
        stop.set()
        for p in processus:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate();p.join()
                resultats.append({'poids':None,'plan':None,'preuve':{'erreur':'arret_force'},'cpu_s':0,'cpu_incomplet':True})
        for canal in canaux:canal.close()
    for r in resultats:
        r['enfants_termines']=all(not p.is_alive() for p in processus)
    if resultats:
        usage_apres=resource.getrusage(resource.RUSAGE_CHILDREN)
        resultats[-1]['cpu_enfants_recoltes_s']=(usage_apres.ru_utime+usage_apres.ru_stime)-(usage_avant.ru_utime+usage_avant.ru_stime)
        resultats[-1]['annulation_join_s']=time.monotonic()-annulation if annulation is not None else 0
    return resultats

def main(args):
    args.sortie.mkdir(parents=True,exist_ok=False)
    hashes=empreintes();(args.sortie/'sources.json').write_text(json.dumps(hashes,indent=2))
    a=charger_agent(args.agent);c=a.chaines[args.modele]
    resultats=portefeuille([(str(args.agent),args.modele,w,args.secondes) for w in (3,10)],
        lambda plan: hashes==empreintes(hashes) and c.verifier_plan(plan)[0])
    assert hashes==empreintes(hashes),'Code modifié pendant recherche'
    (args.sortie/'recherches.json').write_text(json.dumps(resultats,indent=2))
    valides=[r for r in resultats if r.get('premier_plan_valide')]
    if valides:
        meilleur=valides[0];a=charger_agent(args.agent);c=a.chaines[args.modele]
        assert c.verifier_plan(meilleur['plan'])[0]
        c.adopter_plan(meilleur['plan'],origine='portefeuille_selection_cpu')
        a.attente=None
        sauver_agent(a,args.sortie/'agent.pkl')
    print(json.dumps({'recherches':[{'poids':r['poids'],'longueur':len(r['plan']) if r['plan'] else None,
        'cpu_s':r['cpu_s'],'noeuds':r['preuve'].get('noeuds')} for r in resultats],
        'agent_prepare':bool(valides),'sdk_actions':0}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--agent',type=Path,required=True)
    p.add_argument('--modele',required=True);p.add_argument('--sortie',type=Path,required=True)
    p.add_argument('--secondes',type=float,default=45);main(p.parse_args())
