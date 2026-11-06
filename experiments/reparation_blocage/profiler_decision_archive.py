"""Une décision instrumentée sur copie d'archive, aucun SDK."""
import argparse,cProfile,hashlib,json,pstats,time
from pathlib import Path

def bilan_cache(avant, apres):
    """Mesurer sans vider le cache ni attribuer un gain de temps aux hits."""
    delta = {k: apres[k] - avant[k] for k in ('hits', 'misses')}
    return {'avant': avant, 'apres': apres, 'delta': delta,
            'etat_initial': 'vide' if avant['entrees'] == 0 else 'deja_peuple',
            'appels_mesures': sum(delta.values()),
            'portee': 'fidelite de traduction uniquement, pas reconstruction complete',
            'gain_temps': 'non_mesure'}

def main(args):
    from avancer_agent_relais import charger_agent
    from boucle_agent_integree import empreintes
    from cache_fidelite_traduction import statistiques
    args.sortie.mkdir(parents=True,exist_ok=False)
    blob=args.source.read_bytes();a=charger_agent(args.source);assert not a.attente
    a.recherche_prolongee=False;a.recherche_prolongee_workers=1
    j=len(a.journal);sources=empreintes();prof=cProfile.Profile();cpu=time.process_time();mur=time.monotonic()
    cache_avant = statistiques()
    prof.enable()
    d=a.decider(args.offre,secondes=args.secondes)
    prof.disable();cpu=time.process_time()-cpu;mur=time.monotonic()-mur
    cache_apres = statistiques()
    prof.dump_stats(str(args.sortie/'decision.prof'))
    stats=pstats.Stats(prof)
    rows=[{'fichier':k[0],'ligne':k[1],'fonction':k[2],'appels_primitifs':v[0],'appels':v[1],
           'temps_propre_s':v[2],'temps_cumule_s':v[3]} for k,v in stats.stats.items()]
    rows.sort(key=lambda r:r['temps_cumule_s'],reverse=True)
    assert blob==args.source.read_bytes();assert sources==empreintes(sources)
    r={'source':str(args.source),'source_sha256':hashlib.sha256(blob).hexdigest(),'actions':len(a.actions),
       'offre':args.offre,'budget_decider_s':args.secondes,'recherche_prolongee':False,
       'cpu_s':cpu,'mur_s':mur,'sdk_actions':0,
       'cache_traduction':bilan_cache(cache_avant, cache_apres),
       'decision':{k:d.get(k) for k in ('statut','actions','origine','modele_plan')},
       'journal':[{k:x.get(k) for k in ('type','nom','statut','raison')} for x in a.journal[j:]],
       'profil':rows[:100],'profil_complet':'decision.prof','sources':sources,'source_inchangee':True,
       'limite':'Une mesure instrumentee ; overhead cProfile, pas comparaison temporelle causale au run non instrumente.'}
    (args.sortie/'rapport.json').write_text(json.dumps(r,indent=2,default=str))
    print(json.dumps({'cpu_s':cpu,'mur_s':mur,'statut':d.get('statut'),'actions':d.get('actions'),'top':rows[:12]}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True)
    p.add_argument('--offre',nargs='+',type=int,required=True);p.add_argument('--secondes',type=float,default=5);main(p.parse_args())
