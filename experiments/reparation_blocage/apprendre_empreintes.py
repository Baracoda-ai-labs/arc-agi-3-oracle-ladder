"""Films → attribut couleur, empreintes conditionnelles, modèle visible candidat.
Aucun identifiant de jeu, palette, région ou formule cible dans l'induction.
"""
import json,time
from pathlib import Path
from collections import deque,defaultdict
import numpy as np
from scipy.ndimage import label
from direction_contenu_variable import DirectionContenuVariable
from loi_orientation import prefixe
from agent_p1.progres import Progres

def apprendre(bases,pistes,exporter=False):
 transitions=[];initial=None;current=None
 for base in bases:
  z=np.load(str(base)+'.npz');rows=json.loads(Path(str(base)+'.json').read_text())['rows'];o=DirectionContenuVariable(pistes);s=o.voir(z['images'][0]);col=getattr(o,'couleur',None)
  if initial is None:initial=z['images'][0]
  for i,row in enumerate(rows):
   if row.get("levels_completed",0)> (rows[0].get("levels_completed",0) if rows else 0):break # transition de niveau hors domaine appris N1
   for frame in z[f'film_{i+1}']:after=o.voir(frame)
   c2=getattr(o,'couleur',None)
   if 0 in s and 0 in after:
    transitions.append({'a':row['action'],'b':z['images'][i],'c':z['images'][i+1],'phase':s[0],'phase2':after[0],'color':col,'color2':c2,'frames':len(z[f'film_{i+1}'])})
   s=after;col=c2
  current=(z['images'][-1],s.get(0),col)
 controls=sorted({t['a'] for t in transitions if isinstance(t['a'],int) and t['a'] not in (0,1,2,3,4,6) and t['frames']>1})
 assert controls,'Aucun contrôle animé observé'
 mask=np.zeros(initial.shape,bool)
 for t in transitions:
  if t['a'] in controls:mask|=t['b']!=t['c']
 cc,n=label(mask);parts=[]
 for k in range(1,n+1):
  ys,xs=np.where(cc==k)
  if len(xs)>=9 and min(xs)>0 and min(ys)>0 and max(xs)<63 and max(ys)<63:parts.append((len(xs),(int(min(xs)),int(min(ys)),int(max(xs))+1,int(max(ys))+1)))
 assert parts,'Zone causale non identifiée';_,box=max(parts);x0,y0,x1,y1=box
 crop=lambda im:im[y0:y1,x0:x1]
 rules={};selectors={};nav=defaultdict(set);errors=[]
 for t in transitions:
  if isinstance(t['a'],int) and t['a'] in (1,2,3,4):nav[(t['phase'],t['a'])].add(t['phase2'])
  if isinstance(t['a'],list) and t['color']!=t['color2'] and t['phase']==t['phase2']:selectors.setdefault(t['color2'],t['a'])
  if t['a'] not in controls:continue
  key=(t['a'],t['phase']);b,c=crop(t['b']),crop(t['c']);color=t['color'];change=b!=c
  if np.any(c[change]!=color):errors.append({'type':'effet_non_uniforme','phase':t['phase']});continue
  yes,no=rules.setdefault(key,(np.zeros(b.shape,bool),np.zeros(b.shape,bool)))
  yes|=change;no|=(b!=color)&(c!=color)
  if np.any(yes&no):errors.append({'type':'empreinte_contextuelle','phase':t['phase']})
 if exporter:return dict(initial=initial,box=box,rules=rules,selectors=selectors,nav=dict(nav),errors=errors,pistes=pistes,observations=len(transitions))
 palette={t['color'] for t in transitions};goals=[]
 prog=Progres(initial)
 for (x,y,w,h),(xx,yy),score in prog._paires_modele():
  if (x,y,w,h)!=(x0,y0,x1-x0,y1-y0):continue
  g=initial[yy:yy+h,xx:xx+w]
  if not set(np.unique(g))<=palette:continue
  if not all(np.array_equal(t['c'][yy:yy+h,xx:xx+w],g) for t in transitions):continue
  if not any(np.array_equal(g,a) for a in goals):goals.append(g.copy())
 # Same existing visual-model family, exhaustive candidates when top8 truncated the true tile.
 if not goals:
  h,w=crop(initial).shape
  for yy in range(64-h+1):
   for xx in range(64-w+1):
    if not (xx+w<=x0 or xx>=x1 or yy+h<=y0 or yy>=y1):continue
    g=initial[yy:yy+h,xx:xx+w]
    if len(np.unique(g))<2 or not set(np.unique(g))<=palette:continue
    if not all(np.array_equal(t['c'][yy:yy+h,xx:xx+w],g) for t in transitions):continue
    if not any(np.array_equal(g,a) for a in goals):goals.append(g.copy())
 report={'region':box,'palette':sorted(palette),'selecteurs':selectors,'controle':controls,'erreurs':errors,'modeles_visuels_candidats':len(goals),'observations':len(transitions),'empreintes':{str(k):{'positifs':int(y.sum()),'negatifs':int(n.sum()),'inconnus':int((~(y|n)).sum())} for k,(y,n) in rules.items()}}
 report['etat_observe']={'phase':current[1],'color':current[2],'canvas':crop(current[0]).tolist()}
 if errors or not goals:return report,None
 return chercher(current,box,rules,selectors,nav,goals,report)

def chercher(current,box,rules,selectors,nav,goals,report):
 x0,y0,x1,y1=box
 crop=lambda im:im[y0:y1,x0:x1]
 start=(crop(current[0]).tobytes(),current[1],current[2]);q=deque([(start,[])]);seen={start};t0=time.monotonic();shape=crop(current[0]).shape;dtype=current[0].dtype
 while q and len(seen)<100000 and time.monotonic()-t0<10:
  (raw,p,c),path=q.popleft();im=np.frombuffer(raw,dtype=dtype).reshape(shape)
  if any(np.array_equal(im,g) for g in goals):
   report.update(etats=len(seen),plan=path,secondes_recherche=time.monotonic()-t0)
   if path:
    raw0,p0,c0=start;canvas=np.frombuffer(raw0,dtype=dtype).reshape(shape).copy();a=path[0]
    if isinstance(a,list):c0=next(col for col,action in selectors.items() if action==a)
    elif a in (1,2,3,4):p0=next(iter(nav[(p0,a)]))
    else:canvas[rules[(a,p0)][0]]=c0
    report['prediction_prochain_coup']={'phase':p0,'color':c0,'canvas':canvas.tolist()}
   return report,path
  successors=[]
  for a in (1,2,3,4):
   ds=nav.get((p,a),set())
   if len(ds)==1:successors.append(((raw,next(iter(ds)),c),a))
  for col,a in selectors.items():successors.append(((raw,p,col),a))
  for (a,phase),(yes,no) in rules.items():
   if phase!=p or np.any((~(yes|no))&(im!=c)):continue
   after=im.copy();after[yes]=c;successors.append(((after.tobytes(),p,c),a))
  for nxt,a in successors:
   if nxt not in seen:seen.add(nxt);q.append((nxt,path+[a]))
 report.update(etats=len(seen),plan=None,secondes_recherche=time.monotonic()-t0);return report,None

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--session',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);args=p.parse_args();r=Path(__file__).parent
 fs=json.loads((r/'orientations_dc.json').read_text())['fonctions'];_,_,pistes,_,_,_=prefixe(args.source,fs)
 report,plan=apprendre([args.source,args.session],pistes);args.sortie.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
