"""Deux décisions nouvelles (froid/chaud) sur copies identiques, sans SDK."""
import cProfile,hashlib,json,pstats,time
from pathlib import Path
from avancer_agent_relais import charger_agent
from boucle_agent_integree import empreintes
from cache_fidelite_traduction import vider,statistiques

def main():
    source=Path('../runs/stream_multijeux_26_10/lf52_n2_support46/agent.pkl')
    sortie=Path('../runs/mesure_cache_fidelite_lf52_46_1');sortie.mkdir(exist_ok=False)
    blob=source.read_bytes();versions=empreintes();vider();mesures=[]
    for condition in ('froid','chaud'):
        a=charger_agent(source);assert not a.attente
        a.recherche_prolongee=False;a.recherche_prolongee_workers=1
        avant=statistiques();p=cProfile.Profile();cpu=time.process_time();mur=time.monotonic()
        p.enable();d=a.decider([1,2,3,4,6,7],secondes=5);p.disable()
        mesure={'condition':condition,'cpu_s':time.process_time()-cpu,'mur_s':time.monotonic()-mur,
            'cache_avant':avant,'cache_apres':statistiques(),'decision':{k:d.get(k) for k in ('statut','actions','origine')},'fonctions':[]}
        for k,v in pstats.Stats(p).stats.items():
            if k[2] in ('fidele','depuis_python','rejouer','reconstruire','proposer_navigation'):
                mesure['fonctions'].append({'fichier':k[0],'fonction':k[2],'appels':v[1],'cumule_s':v[3]})
        p.dump_stats(str(sortie/(condition+'.prof')));mesures.append(mesure)
        print(json.dumps(mesure),flush=True)
    assert mesures[0]['decision']==mesures[1]['decision']
    assert source.read_bytes()==blob and versions==empreintes(versions)
    r={'source':str(source),'sha256':hashlib.sha256(blob).hexdigest(),'sdk_actions':0,'source_inchangee':True,
       'mesures':mesures,'sources':versions,'limite':'cProfile actif ; autres caches/imports chauffent aussi, ne pas attribuer tout ecart au cache fidelite.'}
    (sortie/'rapport.json').write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
