"""Audit figé d'admission du diagnostic sur une trace publique, aucun SDK."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from chaine_agent_integree import AgentIntegre
from classification_prefixe import classifier
from diagnostic_contexte_transfert import contexte_source,marqueurs
from boucle_agent_integree import AUTORISES
from chrysalide.langue.ontologie_formelle import MECANISMES

def auditer(base,prefixe=8):
 base=Path(base);jp=base.with_suffix('.json');npz=base.with_suffix('.npz');j=json.loads(jp.read_text());game=j['game']
 if game.split('-')[0] not in AUTORISES:raise ValueError('Archive non autorisée')
 z=np.load(npz);rows=j['rows']
 if not 0<prefixe<len(rows):raise ValueError('Préfixe invalide')
 images=z['images'][:prefixe+1];actions=[r['action'] for r in rows[:prefixe]];films=[z[f'film_{i+1}'] for i in range(prefixe)]
 if any(r['levels_completed']!=rows[0]['levels_completed'] or 'GAME_OVER' in r['state'] for r in rows[:prefixe]):raise ValueError('Préfixe franchit une frontière de session')
 start=time.monotonic();a=AgentIntegre(images,actions,films,['continue']*prefixe,decouverte_courte=True,routage_classes=True);a.reconstruire()
 desc=classifier(images,actions,films);ctx=contexte_source(images)
 observed=[marqueurs(im) for im in images];colors=sorted(set().union(*(set(o) for o in observed)))
 candidates=[{'couleur':c,'images_presentes':sum(c in o for o in observed),'images_total':len(images),'hotes':sorted(set().union(*(set(o.get(c,{})) for o in observed))),'retenu_par_contexte_source':c in ctx,'selection_prouvee':False} for c in colors]
 contracts=[n for n,v in MECANISMES.items() if 'selection' in v.get('ecrit',[])]
 report={'jeu':game,'preuve':'traces_uniquement','prefixe':prefixe,'transitions_archive':len(rows),'modeles_admis':list(a.chaines),'classification':desc,'marqueurs_candidats':candidates,'dependance_selection':MECANISMES['deplacement']['lit'],'contrats_ecrivant_selection':contracts,'admissions_et_refus':a.journal,'secondes':time.monotonic()-start,'coups_sdk_nouveaux':0,'victoire_nouvelle':False,'transfert_diagnostic_demontre':False,'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (jp,npz)}}
 if not a.chaines:
  report.update(statut='precondition_perception_absente',etape_atteinte='classification_et_admission',diagnostics_selection_executables=0,transitions_suite_non_couvertes=len(rows)-prefixe,experience_validee=False,reprise_modele_validee=False)
 else:
  report.update(statut='admission_a_poursuivre',etape_atteinte='admission',transitions_suite_non_evaluees=len(rows)-prefixe)
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);args=p.parse_args();r=auditer(args.source);args.sortie.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=int)+'\n');print(json.dumps({k:r[k] for k in ['jeu','statut','modeles_admis','marqueurs_candidats','coups_sdk_nouveaux']}))
