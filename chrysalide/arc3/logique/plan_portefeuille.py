# ruff: noqa
# Code du défi 6 (ChatGPT, CW-278/279), intégré tel quel par A le 20/10 après vérification indépendante des plans ; style hors charte.
"""Portefeuille de huit recherches génériques : ordres, poids et traits différents."""
import os,time,multiprocessing as mp
import queue as queue_module
from chrysalide.arc3.logique import plan_generique as pg


def traits_canevas(sc,etat):
    out=pg.caracteristiques_initiales(sc,etat)
    # Objets virtuels portés par l'état du programme, pas forcément par Scene.sprites.
    for name,value in (etat or {}).items():
        objects=[value] if isinstance(value,dict) else value if isinstance(value,list) else []
        for i,obj in enumerate(objects):
            if isinstance(obj,dict) and 'x' in obj and 'y' in obj:
                attrs=tuple(sorted((k,v) for k,v in obj.items() if isinstance(v,(str,int,float,bool,type(None)))))
                out.add(('virtuel',name,i,attrs))
    return out


def _worker(queue,compteurs,index,texte,scene,coups,kwargs,memoire_mio):
    try:
        # Borne de protection du hôte à 8 Go; l'épuisement est rapporté, jamais assimilé à une impasse.
        import resource
        if memoire_mio:resource.setrlimit(resource.RLIMIT_AS,(memoire_mio*1024**2,memoire_mio*1024**2))
        if index>=4:
            pg.caracteristiques_initiales=pg.caracteristiques
            pg.caracteristiques=traits_canevas
        report=lambda n:setattr(compteurs[index],'value',n)
        if index<2:
            from chrysalide.arc3.logique.plan_langage import planifier_langage
            plan,stats=planifier_langage(texte,scene,coups,recherche='but' if index==0 else 'paliers',
                                        compiler=False,progression=report,**kwargs)
        else:
            plan,stats=pg.planifier(texte,scene,coups,seed=0 if index==2 else index,
                                   progression=report,**kwargs)
        queue.put((index,plan,stats))
    except MemoryError:queue.put((index,None,{'raison':'limite_memoire'}))
    except Exception as exc:queue.put((index,None,{'raison':'erreur','erreur':repr(exc)}))


def portefeuille(texte,scene,coups,noeuds=200000,secondes=300,processus=8,memoire_mio=1024,**kwargs):
    os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
    ctx=mp.get_context('spawn');q=ctx.Queue();counts=[ctx.Value('q',0,lock=False) for _ in range(processus)]
    start=time.monotonic();jobs=[];finished=[];plan=None;winner=None
    for i in range(processus):
        p=ctx.Process(target=_worker,args=(q,counts,i,texte,scene,coups,dict(noeuds=noeuds,secondes=secondes,**kwargs),memoire_mio))
        p.start();jobs.append(p)
    while len(finished)<processus and time.monotonic()-start<secondes+10:
        try:i,result,stats=q.get(timeout=.2)
        except queue_module.Empty:
            if not any(p.is_alive() for p in jobs):break
            continue
        finished.append({'worker':i,**stats})
        if result:plan=result;winner=i;break
    for p in jobs:
        if p.is_alive():p.terminate()
    for p in jobs:p.join()
    return plan,{'raison':'but_simule' if plan else 'budget_portefeuille','secondes':time.monotonic()-start,
                 'processus':processus,'gagnant':winner,'noeuds':sum(c.value for c in counts),
                 'noeuds_par_processus':[c.value for c in counts],'termines':finished,
                 'memoire_par_processus_Mio':memoire_mio,'traits_virtuels_workers':[4,5,6,7],'reference_workers':{'0':'but','1':'paliers'},'nouveau_worker_principal':2}
