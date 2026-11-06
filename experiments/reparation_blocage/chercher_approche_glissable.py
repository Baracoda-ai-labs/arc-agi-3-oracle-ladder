import cloudpickle,copy,json,time
from pathlib import Path
from revision_but_roles import couverture
from chrysalide.arc3.logique.plan_langage import planifier_langage,cle_complete,_GELES
from chrysalide.arc3.langage import Programme
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--agent',type=Path,required=True);ap.add_argument('--sortie',type=Path,required=True);args=ap.parse_args()
p=args.agent.parent;a=cloudpickle.load(open(args.agent,'rb'));c=next(iter(a.chaines.values()));_,(pc,sc)=c.rejouer();cl=c.preuve_classe_glissable['classe'];hs=couverture(c.perception)
targets=[(x,y,w,h) for hh in hs if hh['classe_cible_candidate']!=cl for x,y,w,h in hh['centres']]
targets=[t for t in targets if any((s['x'],s['y'])==t[:2] and s.get('couche',0)>=0 and set(s['pixels'].ravel())-{-1} != {cl} for s in c.perception.statiques)]
passifs=[o for o in sc.sprites if set(o['pixels'].ravel())-{-1}=={cl}];piece=next(o for o in sc.sprites if 'piece' in o.get('tags',[]));ph,pw=piece['pixels'].shape
restants=[o for o in passifs if not any((o['x'],o['y'],*o['pixels'].shape)==(x,y,h,w) for x,y,w,h in targets)];assert len(restants)==1
o=restants[0];oh,ow=o['pixels'].shape
libres=[t for t in targets if not any((q['x'],q['y'])==t[:2] for q in passifs)];assert len(libres)==1
tx,ty,tw,th=libres[0];goals=[]
if tx<o['x']:goals.append((o['x']+ow,o['y']+(oh-ph)//2,'LEFT'))
if tx>o['x']:goals.append((o['x']-pw,o['y']+(oh-ph)//2,'RIGHT'))
if ty<o['y']:goals.append((o['x']+(ow-pw)//2,o['y']+oh,'UP'))
if ty>o['y']:goals.append((o['x']+(ow-pw)//2,o['y']-ph,'DOWN'))
condition=['existe','$o',['objets',{'tag':'piece'}],['ou',*[['et',['=',['x','$o'],x],['=',['y','$o'],y]] for x,y,_ in goals]]]
prog=copy.deepcopy(c.programme);prog['regles'].append({'nom':'approche_experimentale','phase':99,'quand':condition,'alors':[['niveau_suivant']]})
t=time.process_time();plan,infos=planifier_langage(prog,copy.deepcopy(sc),[(x,) for x in ['RIGHT','UP','LEFT','DOWN']],noeuds=40000,secondes=10,compiler=False,etat=pc.etat)
etapes=[]
if plan:
 pi=Programme(c.programme);pi.etat=copy.deepcopy(pc.etat);si=copy.deepcopy(sc)
 for action in plan:
  pc.step(sc,action);pi.step(si,action);_GELES.clear();assert cle_complete(sc,pc.etat)==cle_complete(si,pi.etat)
  etapes.append({'action':action,'image':c.perception.rendu(sc).tolist(),'issue':sc.issue})
 pos=next((o['x'],o['y']) for o in sc.sprites if 'piece' in o.get('tags',[]));action=next((n,) for x,y,n in goals if (x,y)==pos)
 pc.step(sc,action);pi.step(si,action);_GELES.clear();assert cle_complete(sc,pc.etat)==cle_complete(si,pi.etat)
 etapes.append({'action':action,'image':c.perception.rendu(sc).tolist(),'issue':sc.issue,'sonde':True});plan=[*plan,action]
r={'plan_experience':plan,'etapes':etapes,'infos':infos,'cpu':time.process_time()-t,'but_jeu_inconnu':True,'objectifs':goals,'source':'agent.pkl','sdk':0,'limite':'Derniere sonde applique mecanisme a une autre instance ; sol sous celle-ci non etabli, arret divergence obligatoire.'};args.sortie.write_text(json.dumps(r,indent=2));print({k:v for k,v in r.items() if k!='etapes'})
