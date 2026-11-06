"""Lecture des preuves locales archivées, aucune action SDK, aucune loi ajoutée."""
from pathlib import Path
import hashlib,json,cloudpickle,numpy as np
from diagnostic_contexte_transfert import marqueurs
from objets_variables import ObjetsVariables
from roles_observes import PerceptionRoles
from selection_observee import SelectionObservee
from chaine_coherente import Chaine
from chaine_agent_integree import lots,canon

R=Path(__file__).parent
source=R/'runs/transfert_modele_commun_ar25_1/N2/partie'
snapshot=R/'runs/ar25_contexte37_restaure1/agent.pkl'
z=np.load(source.with_suffix('.npz'));rows=json.loads(source.with_suffix('.json').read_text())['rows']
a=cloudpickle.loads(snapshot.read_bytes());m=a.memoire_jeu
context=lambda im:{str(c):sorted(marqueurs(im).get(c,{})) for c in m.contexte_selection}
r={'SDK':False,'source_sha256':{str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source.with_suffix('.npz'),source.with_suffix('.json'),snapshot]},
   'snapshot_coup':len(a.actions),'recherche49':{'refus':'espace épuisé','noeuds':3136,'cpu_mesure':0.072155},
   'invariant_modele':{'somme_x_mobiles':60,'but_x':3,'x_autre_requis':57,'largeur_autre':15,'largeur_image':64,'portee':'programme_actuel_seulement'},
   'observations':[], 'essais':[], 'limite':'preuves locales anciennes, pas prédictions vérifiées à état49; but non réfuté'}
for k,row in enumerate(rows):
 ctx=context(z['images'][k])
 if ctx==context(a.images[0]):
  before,after=z['images'][k:k+2];ys,xs=np.where(before[:63,:63]!=after[:63,:63])
  r['observations'].append({'coup':k+1,'action':row['action'],'contexte':ctx,'pixels_modifies_hors_bord':len(xs),
   'boite_ecart':None if not len(xs) else [int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]})
for fin in [21,22]:
 images=z['images'][17:fin+1];actions=[row['action'] for row in rows[17:fin]]
 for nom,constructeur in [('objets',lambda:ObjetsVariables(images,actions)),('objets_contact',lambda:ObjetsVariables(images,actions,contact=True)),('objets_masque_court',lambda:ObjetsVariables(images,actions,contact=True,masque_court=True)),('roles',lambda:PerceptionRoles(images,actions)),('selection_sans_clic',lambda:SelectionObservee(images,actions,sans_clic=True))]:
  rec={'famille':nom,'apprentissage_coups':[18,fin],'suffixe_tenu_a_part':[fin+1,24]}
  try:
   v=constructeur();p=v.programme();c=Chaine(v,p,[g.tolist() for g in images],lots(actions),[])
   ck,state=c.rejouer();rec.update(controle=ck,mouvements=getattr(v,'mouvements',None))
   if state:
    pc,sc=state;rec['predictions_suffixe']=[]
    for k in range(fin,24):
     pc.step(sc,canon(rows[k]['action']));rec['predictions_suffixe'].append({'coup':k+1,'exact':bool(np.array_equal(v.rendu(sc),v.vue(z['images'][k+1])))})
  except (ValueError,TypeError,AttributeError,KeyError) as e:rec['refus']=repr(e)
  r['essais'].append(rec)
(R/'AUDIT_CONTEXTE_ALTERNATIF_ARCHIVE.json').write_text(json.dumps(r,indent=2,ensure_ascii=False,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
print(json.dumps(r['essais'],ensure_ascii=False,default=str))
