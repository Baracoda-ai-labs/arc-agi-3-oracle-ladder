"""Relais dans le même processus : budget explicite, environnement SDK conservé."""
import os,json,time,threading,sys,hashlib,subprocess,resource,traceback
from pathlib import Path
import numpy as np
import retour_perception,importlib
importlib.reload(retour_perception)
from retour_perception import reviser,charger
from direction_contenu import DirectionContenu
from direction_contenu_variable import DirectionContenuVariable
from loi_orientation import Orientation
from orientation_dirigee import Direction
from revision_orientation import Revision

class Relais:
 def __init__(self,ctx,root):
  self.lab=ctx['lab'];self.pool=ctx['pool'];self.pistes=ctx['pistes'];self.anciens=ctx['anciens'];self.l=ctx['l'];self.o=ctx['o'];self.state=ctx['state'];self.description=ctx['description']
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False);self.code=Path(__file__).resolve().parent
  self.budget=128;self.initial=len(self.lab.rows);self.attempts=self.initial;self.stop=False;self.journal=[];self.reparations=0;self.confirmations=0;self.actif=0.;self.commandes=0;self.status='en_attente';self.cout0=resource.getrusage(resource.RUSAGE_SELF);self.kids0=resource.getrusage(resource.RUSAGE_CHILDREN)
  self.dump()
 def coups_totaux(self):
  return getattr(self,"coups_precedents",0)+len(self.lab.rows)
 def niveau_suivant(self):
  if not self.lab.won or self.lab.partie_gagnee:raise ValueError("Transition non disponible")
  precedent=self.lab;total=self.coups_totaux()
  output=precedent.output.parent.parent/f"N{precedent.level+1}"/"partie"
  if output.parent.exists():raise ValueError("Sortie existante, conservation prioritaire")
  suivant=precedent.next_level(output)
  assert suivant.env is precedent.env
  self.precedents=getattr(self,"precedents",[])+[precedent]
  self.coups_precedents=total;self.lab=suivant;self.reaffectation_requise=True
  self.journal.append({"type":"transition_niveau","niveau":suivant.level,"coups_cumules":total,"actions_transition":0,"source_modele":str(precedent.output),"hypotheses_provisoires":True})
  self.status="instance_a_reaffecter"
 def dump(self):
  cpu=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
  d={'pid':os.getpid(),'session_ouverte':not self.stop,'statut':self.status,'coups_reels':self.coups_totaux(),'coups_niveau':len(self.lab.rows),'niveau':getattr(self.lab,'level',1),'coups_au_raccord':self.initial,'appels_tentes':self.attempts,'initialisations_sdk_supplementaires':0,'budget_coups':self.budget,'image_sha256':hashlib.sha256(self.lab.image.tobytes()).hexdigest(),'representation':self.description,'reparations':self.reparations,'confirmations_uniques_inedites':self.confirmations,'niveaux_gagnes':getattr(self.lab,'completed_baseline',0)+int(self.lab.won),'jeu_gagne':self.lab.partie_gagnee,'secondes_actives':self.actif,'cpu_parent':cpu.ru_utime+cpu.ru_stime-self.cout0.ru_utime-self.cout0.ru_stime,'cpu_enfants':kids.ru_utime+kids.ru_stime-self.kids0.ru_utime-self.kids0.ru_stime,'promotion_durable':False,'commandes':self.commandes}
  (self.root/'etat.json').write_text(json.dumps(d,indent=2)+'\n');(self.root/'journal.json').write_text(json.dumps(self.journal,indent=2)+'\n');m=self.l.memoire();m['portee']=self.description;(self.root/'memoire_provisoire.json').write_text(json.dumps(m,indent=2)+'\n');return d
 def reconstruire(self):
  current=charger(self.lab.output,len(self.lab.rows));r=reviser([self.anciens,current],self.pistes)
  if r['statut']!='description_compatible':self.journal.append({'type':'perception_non_resolue',**r});return False
  if r['representation']!=self.description:self.journal.append({'type':'retour_perception','avant':self.description,'apres':r['representation'],'preuves':r['journal']})
  self.description=r['representation'];self.l=Revision([self.pool]);self.l.exemples=r['exemples'];self.o=DirectionContenuVariable(self.pistes) if self.description=='contenu_variable' else DirectionContenu(self.pistes) if self.description=='contenu_dans_contour' else Direction(self.pistes) if self.description=='relation_dirigee' else Orientation();self.state=self.o.voir(current[0][0])
  for film in current[2]:
   for frame in film:self.state=self.o.voir(frame)
  return True
 def ajuster(self,a):
  if self.l.ajuster(a):return True
  if self.l.revisions and self.l.revisions[-1]['statut']=='representation_insuffisante':return self.reconstruire() and bool(self.l.candidats(a))
  src=self.root/f'reparation_{self.reparations}_entree.json';dst=self.root/f'reparation_{self.reparations}_sortie.json';self.reparations+=1
  src.write_text(json.dumps({'exemples':self.l.exemples[str(a)],'fonctions':self.pool}));env={**os.environ,'DREAMCODER_CORE_ONLY':'1','PYTHONPATH':str(self.code/'vendor/dreamcoder')}
  subprocess.run([str(self.code/'vendor/dreamcoder/.venv/bin/python'),str(self.code/'reparer_direction_dc.py'),str(src),str(dst)],env=env,timeout=22,check=True)
  result=json.loads(dst.read_text());self.pool+=result['fonctions'];self.l.etages=[self.pool];self.journal.append({'type':'reparation','action':a,'hypotheses':len(result['fonctions'])});return bool(self.l.candidats(a))
 def advance(self,n):
  if not isinstance(n,int) or not 1<=n<=32:raise ValueError('Lot doit contenir1à32coups')
  t=time.monotonic()
  try:
   for _ in range(n):
    if self.coups_totaux()>=self.budget:self.status='budget_atteint';break
    if self.lab.finished:self.status='victoire' if self.lab.won else 'defaite';break
    if time.monotonic()-t>120:self.status='pause_calcul';break
    if not all(self.ajuster(a) for a in (1,2,3,4)):self.status='revision_requise';break
    ids=sorted(self.pistes) if self.description=='axe_mod_pi' else [0]
    if any(k not in self.state for k in ids):self.status='perception_incomplete';break
    choix=self.l.choix([self.state[k] for k in ids],self.lab.actions_disponibles)
    if choix is None:self.status='orientation_couverte_but_non_modele';break
    a=choix['action'];before=self.state.copy();pred={k:self.l.predire(a,before[k]) for k in ids};novel={k:self.l.nouveau(a,[before[k]]) for k in ids}
    row={'type':'experience','coup':self.coups_totaux()+1,'choix':choix,'avant':before,'predictions':pred,'nouveau':novel};self.journal.append(row);self.attempts+=1;self.dump()
    im,film=self.lab.play(a,purpose='navigation_experience' if choix['acces'] else 'experience_prospective')
    for frame in film:self.state=self.o.voir(frame)
    row['apres']=self.state.copy();row['refute']=any(k not in self.state or self.state[k] not in pred[k] for k in ids)
    self.confirmations+=sum(novel[k] and len(pred[k])==1 and self.state.get(k)==pred[k][0] for k in ids)
    if not self.reconstruire():self.status='perception_non_resolue';break
    if not self.ajuster(a):self.status='revision_requise';break
    self.status='en_attente';self.dump()
  finally:self.actif+=time.monotonic()-t
 def explorer(self,n,archives,mode="sonde"):
  from experience_sans_but import proposer
  if not isinstance(n,int) or not 1<=n<=16:raise ValueError('Lot exploration invalide')
  passes=[]
  for path in archives:
   base=Path(path);z=np.load(str(base)+'.npz');rows=json.loads(Path(str(base)+'.json').read_text())['rows']
   passes.extend((z['images'][i],row['action']) for i,row in enumerate(rows))
  t=time.monotonic()
  try:
   for _ in range(n):
    if self.lab.finished or self.coups_totaux()>=self.budget:break
    offre=list(self.lab.actions_disponibles);exp=None
    while offre:
     actions=[row['action'] for row in self.lab.rows];films=[self.lab.films['film_'+str(i+1)] for i in range(len(actions))]
     exp,diag=proposer(self.lab.images,actions,films,offre)
     if mode=='p1':
      from exploration_p1_prefixe import proposer as graphe
      previous=exp
      from chrysalide.arc3.masque import Masque
      masque=Masque()
      for avant,apres in zip(self.lab.images,self.lab.images[1:]):masque.observer(avant.tolist(),apres.tolist())
      hud=list(masque.cellules());propres=[]
      for image in self.lab.images:
       clean=image.copy()
       for y,x in hud:clean[y,x]=0
       propres.append(clean)
      exp=graphe(propres,actions,['continue']*len(actions),offre)
      if exp is not None:exp['hud']=hud
     if exp is None:break
     a=exp['actions'][0];hud=exp.get('hud',[]);now=self.lab.image.copy()
     for y,x in hud:now[y,x]=0
     deja=False
     for image,action in passes+list(zip(self.lab.images,actions)):
      if action!=a:continue
      old=image.copy()
      for y,x in hud:old[y,x]=0
      if np.array_equal(old,now):deja=True;break
     if not deja:break
     code=6 if isinstance(a,list) else a;offre=[x for x in offre if x!=code];exp=None
    if exp is None:self.status='experiences_nouvelles_epuisees';break
    row={'type':'experience_sans_but_existante','coup':self.coups_totaux()+1,'proposition':exp};self.journal.append(row);self.attempts+=1;self.dump()
    before=self.lab.image.copy();im,film=self.lab.play(exp['actions'][0],purpose='experience_nouvelle_autre_mecanisme')
    row.update(pixels_changes=int(np.count_nonzero(before!=im)),frames=len(film),niveau_gagne=bool(self.lab.won))
    # Une nouvelle mécanique peut invalider la description : conserver le film et signaler.
    if not self.reconstruire():self.status='perception_non_resolue';break
    self.status='victoire' if self.lab.won else 'en_attente'
    self.dump()
  finally:self.actif+=time.monotonic()-t
 def sonder_controle(self,n,archives):
  from collections import deque
  # Commandes hors déplacement ayant déjà produit une animation observée.
  controls=sorted({row['action'] for i,row in enumerate(self.lab.rows) if isinstance(row['action'],int) and row['action'] not in (0,1,2,3,4,6) and len(self.lab.films['film_'+str(i+1)])>1} & set(self.lab.actions_disponibles))
  vus=set()
  episodes=[charger(Path(x),len(json.loads(Path(str(x)+'.json').read_text())['rows'])) for x in archives]
  episodes.append(charger(self.lab.output,len(self.lab.rows)))
  for images,actions,films in episodes:
   obs=DirectionContenu(self.pistes);before=obs.voir(images[0])
   for a,film in zip(actions,films):
    if a in controls and 0 in before:vus.add((a,before[0]))
    for frame in film:before=obs.voir(frame)
  t=time.monotonic()
  try:
   for _ in range(min(n,32)):
    if self.lab.finished or self.coups_totaux()>=self.budget:break
    if self.description!='contenu_dans_contour' or 0 not in self.state:self.status='perception_requise';break
    for a in (1,2,3,4):
     if not self.ajuster(a):self.status='regle_navigation_inconnue';return
    q=deque([(self.state[0],[])]);seen={self.state[0]};route=None
    while q:
     phase,steps=q.popleft()
     targets=[a for a in controls if (a,phase) not in vus]
     if targets:route=steps+[targets[0]];break
     for a in (1,2,3,4):
      pred=self.l.predire(a,phase)
      if len(pred)==1 and pred[0] not in seen:seen.add(pred[0]);q.append((pred[0],steps+[a]))
    if route is None:self.status='controles_orientations_explores';break
    a=route[0];row={'type':'experience_controle_orientation','coup':self.coups_totaux()+1,'route':route,'action':a,'avant':self.state.copy(),'navigation':len(route)>1,'hypothese':'effet du controle depend de la configuration observee, but encore inconnu'};self.journal.append(row);self.attempts+=1;self.dump()
    phase=self.state[0];im,film=self.lab.play(a,purpose='navigation_controle' if len(route)>1 else 'controle_orientation_inedite')
    if a in controls:vus.add((a,phase))
    if not self.reconstruire():self.status='perception_non_resolue';break
    row['apres']=self.state.copy();self.status='victoire' if self.lab.won else 'en_attente';self.dump()
  finally:self.actif+=time.monotonic()-t
 def resoudre_empreintes(self,n,archives):
  from apprendre_empreintes import apprendre
  t=time.monotonic()
  try:
   for _ in range(min(n,32)):
    if self.lab.finished or self.coups_totaux()>=self.budget:break
    bases=[Path(x) for x in archives]+[self.lab.output];rapport,plan=apprendre(bases,self.pistes)
    if not plan:self.status='pas_plan_empreinte';self.journal.append({'type':'recherche_empreinte','rapport':rapport});break
    row={'type':'plan_empreinte_appris','coup':self.coups_totaux()+1,'rapport':rapport,'action':plan[0]};self.journal.append(row);self.attempts+=1;self.dump()
    self.lab.play(plan[0],purpose='plan_empreinte_appris_replanifie')
    apres,_=apprendre(bases,self.pistes);row['observation']=apres.get('etat_observe');row['prediction_fidele']=row['observation']==rapport['prediction_prochain_coup']
    self.reconstruire()
    if self.lab.won:self.status='victoire';self.dump();break
    if not row['prediction_fidele']:self.status='divergence_empreinte';self.dump();break
    self.status='en_attente';self.dump()
  finally:self.actif+=time.monotonic()-t
 def transferer(self,n,archives):
  import apprendre_empreintes
  importlib.reload(apprendre_empreintes)
  from apprendre_empreintes import apprendre
  from transfert_empreintes import lier,planifier,observer
  if not 1<=n<=32:raise ValueError('Lot invalide')
  if not hasattr(self,'modele_transfert'):
   if not getattr(self,'precedents',[]):raise ValueError('Niveau acquis absent')
   self.modele_transfert=apprendre([Path(x) for x in archives]+[self.precedents[-1].output],self.pistes,exporter=True)
   if self.modele_transfert['errors']:raise ValueError('Modèle source contradictoire')
   self.instance_transfert=lier(self.modele_transfert,self.lab.images[0])
  t=time.monotonic()
  try:
   for _ in range(n):
    if self.lab.finished or self.coups_totaux()>=self.budget:break
    films=[self.lab.films['film_'+str(i+1)] for i in range(len(self.lab.rows))]
    report,plan=planifier(self.modele_transfert,self.instance_transfert,self.lab.images,films)
    if not plan:self.status='transfert_sans_plan';self.journal.append({'type':'recherche_transfert','rapport':report});break
    row={'type':'transfert_modele_niveau','coup':self.coups_totaux()+1,'action':plan[0],'rapport':report};self.journal.append(row);self.attempts+=1;self.dump()
    self.lab.play(plan[0],purpose='transfert_modele_niveau_sans_reapprentissage')
    if self.lab.finished:
     row['niveau_gagne']=bool(self.lab.won);row['comparaison']='transition_terminale';self.status='victoire' if self.lab.won else 'defaite';self.dump();break
    films.append(self.lab.films['film_'+str(len(self.lab.rows))])
    _,seen=observer(self.instance_transfert,self.lab.images,films);row['observation']=seen;row['prediction_fidele']=seen==report['prediction_prochain_coup']
    if not row['prediction_fidele']:self.status='divergence_transfert';self.dump();break
    self.status='transfert_en_cours';self.dump()
  finally:self.actif+=time.monotonic()-t
 def traiter(self,cmd):
  self.commandes+=1
  if getattr(self,'reaffectation_requise',False) and cmd['op'] in ('advance','solve_stamp','probe_control','explore','reobserve'):raise ValueError('Réaffecter les rôles du nouveau niveau avant les anciennes routines')
  if cmd['op']=='advance':self.advance(cmd.get('coups',1))
  elif cmd['op']=='solve_stamp':self.resoudre_empreintes(cmd.get('coups',16),cmd.get('archives',[]))
  elif cmd['op']=='probe_control':self.sonder_controle(cmd.get('coups',16),cmd.get('archives',[]))
  elif cmd['op']=='explore':self.explorer(cmd.get('coups',1),cmd.get('archives',[]),cmd.get('mode','sonde'))
  elif cmd['op']=='budget':
   b=cmd['coups_total']
   if not isinstance(b,int) or b<self.coups_totaux() or b>10000:raise ValueError('Budget invalide')
   self.journal.append({'type':'budget','ancien':self.budget,'nouveau':b});self.budget=b
  elif cmd['op']=='reobserve':
   self.status='en_attente' if self.reconstruire() else 'perception_non_resolue'
  elif cmd['op']=='reload':
   import runpy
   path=Path(__file__)
   if hashlib.sha256(path.read_bytes()).hexdigest()!=cmd['sha256']:raise ValueError('Empreinte code différente')
   self.__class__=runpy.run_path(str(path))['Relais']
  elif cmd['op']=='transfer':self.transferer(cmd.get('coups',1),cmd.get('archives',[]))
  elif cmd['op']=='next_level':self.niveau_suivant()
  elif cmd['op']=='status':pass
  elif cmd['op']=='close':self.stop=True;self.status='fermee'
  else:raise ValueError('Commande inconnue')
  return self.dump()
 def boucle(self):
  while not self.stop:
   for path in sorted(self.root.glob('commande_*.json')):
    result=path.with_suffix('.resultat.json')
    if path.name.endswith('.resultat.json') or result.exists():continue
    try:r=self.traiter(json.loads(path.read_text()))
    except Exception as e:self.status='erreur';self.journal.append({'type':'erreur','message':repr(e)});r=self.dump()
    result.write_text(json.dumps(r,indent=2)+'\n')
   time.sleep(.2)

def installer(root):
 if hasattr(sys,'_chrysalide_relais'):raise RuntimeError('Relais déjà installé')
 ctx=None
 for f in sys._current_frames().values():
  while f:
   if f.f_code.co_name=='main' and f.f_globals.get('__file__','').endswith('session_perception_arc.py') and 'lab' in f.f_locals:ctx=f.f_locals.copy();break
   f=f.f_back
  if ctx:break
 if ctx is None:raise RuntimeError('Session propriétaire introuvable')
 if len(ctx['lab'].rows)!=32:raise RuntimeError('État attendu32coups absent')
 s=Relais(ctx,root);sys._chrysalide_relais=s
 threading.Thread(target=s.boucle,name='chrysalide-relais',daemon=True).start()
