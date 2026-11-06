# ruff: noqa
# Code du défi 6 (ChatGPT, CW-278/279), intégré tel quel par A le 20/10 après vérification indépendante des plans ; style hors charte.
"""Recherche générique à programmes exacts. Aucun accès au moteur des jeux.
Les distances sont des guides non admissibles; seul ProgrammeCompile décide du but.
"""
import copy
import heapq
import math
import pickle
import zlib
import time
import numpy as np
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
from chrysalide.arc3.logique.plan_langage import regle_victoire, _gel, _gel_sprite, distance_but


def cle(scene, etat):
    # Ordre des sprites, début et données conservés; pas seulement le hash.
    value = (tuple(_gel_sprite(s) for s in scene.sprites), _gel(etat),
            _gel(scene.camera), _gel(scene.canevas), _gel(scene.donnees),
            scene.issue, scene.debut, scene.niveau)
    return zlib.compress(pickle.dumps(value, protocol=5), 1)


def termes(x):
    if isinstance(x,list):
        if x and isinstance(x[0],str): yield x
        for y in x: yield from termes(y)
    elif isinstance(x,dict):
        for y in x.values(): yield from termes(y)


class Guide:
    def __init__(self, texte):
        self.p=Programme(texte); self.but=regle_victoire(texte)
        ops={t[0] for t in termes(texte)}
        terminal=[t for t in termes(texte) if t[0] in ('niveau_suivant','gagner')]
        direct=[r for r in texte.get('regles',[]) if any(e and e[0] in ('niveau_suivant','gagner') for e in r.get('alors',[]))]
        self.impasse_regle=direct[0] if len(terminal)==1 and len(direct)==1 else None
        self.peut_creer=bool(ops & {'creer','soit_creer','restaurer'})
        self.ops=ops
        self.defs={}
        # Régression d'un indicateur calculé vers son expression, uniquement pour h.
        for t in termes(texte):
            if t[0]=='poser' and len(t)==3 and isinstance(t[2],list):
                if not any(z[:2]==['etat',t[1]] for z in termes(t[2])):
                    self.defs.setdefault(t[1],[]).append(t[2])
        self.coords={}
        self.reductions={};self.producteurs={}
        def subst(x,bind):
            if isinstance(x,str):return bind.get(x,x)
            if isinstance(x,list):return [subst(v,bind) for v in x]
            if isinstance(x,dict):return {k:subst(v,bind) for k,v in x.items()}
            return x
        def scan(effects,loops=(),calls=()):
            for t in effects:
                if not isinstance(t,list) or not t:continue
                op=t[0]
                if op in self.p.mots and op not in calls:
                    d=self.p.mots[op]
                    if d.get('sorte')=='effet':
                        scan(subst(d['corps'],dict(zip(d.get('params',[]),t[1:]))),loops,calls+(op,))
                elif op=='pour':scan(t[3],loops+((t[1],t[2]),),calls)
                elif op=='si_alors':
                    scan(t[2],loops,calls)
                    if len(t)>3:scan(t[3],loops,calls)
                elif op=='poser' and isinstance(t[2],list) and t[2][:2]==['et',['etat',t[1]]]:
                    expr=['et',*t[2][2:]]
                    for var,items in reversed(loops):expr=['tous',var,items,expr]
                    self.reductions.setdefault(t[1],[]).append(expr)
        for rule in texte.get('regles',[]):scan(rule.get('alors',[]))
        def producers(effects,conds=(),bind=None,calls=(),loops=()):
            bind=bind or {}
            for raw in effects:
                t=subst(raw,bind)
                if not isinstance(t,list) or not t:continue
                op=t[0]
                if op in self.p.mots and op not in calls:
                    d=self.p.mots[op]
                    if d.get('sorte')=='effet':producers(d['corps'],conds,dict(zip(d.get('params',[]),t[1:])),calls+(op,),loops)
                elif op=='si_alors':
                    producers(t[2],conds+(t[1],),calls=calls,loops=loops)
                    if len(t)>3:producers(t[3],conds+(['non',t[1]],),calls=calls,loops=loops)
                elif op=='pour':producers(t[3],conds,calls=calls,loops=loops+((t[1],t[2]),))
                elif op=='tant_que':producers(t[2],conds,calls=calls,loops=loops)
                elif op=='poser' and not isinstance(t[2],(list,dict)) and t[2] is not None:
                    expr=['et',*conds]
                    for var,items in reversed(loops):expr=['existe',var,items,expr]
                    if len(list(termes(expr)))<100:
                        self.producteurs.setdefault((t[1],str(t[2])),[]).append(expr)
        for rule in texte.get('regles',[]):
            bind={}
            for k,v in (rule.get('soit') or {}).items():bind['$'+k]=subst(v,bind)
            producers(rule.get('alors',[]),(subst(rule.get('quand',True),bind),),bind)


    def h(self,scene,etat,action, enrichi=True):
        if not self.but:return 1.
        if not enrichi:return float(distance_but(self.p,self.but,scene,etat))
        self.p.etat=etat
        env={'_scene':scene,'_action':action,'_niveau':scene.niveau or 0,'_debut':scene.debut}
        for k,t in (self.but.get('soit') or {}).items():
            try:env[k]=self.p.ev(t,env)
            except Exception:env[k]=None
        self.coords={}
        return self.dist(self.but.get('quand'),env,0)

    def impossible(self,sc,et):
        """Certificat restreint : une collection nécessaire est vide et ne peut croître.
        Désactivé pour plusieurs chemins de victoire et filtres modifiables.
        """
        if self.peut_creer or self.impasse_regle is None:return False
        self.p.etat=et;e={'_scene':sc,'_action':None,'_niveau':sc.niveau or 0,'_debut':sc.debut}
        try:
            for k,v in (self.impasse_regle.get('soit') or {}).items():e[k]=self.p.ev(v,e)
        except Exception:return False
        def test(t,env):
            if not isinstance(t,list) or not t:return False
            op=t[0]
            if op=='et':return any(test(v,env) for v in t[1:])
            if op=='ou':return bool(t[1:]) and all(test(v,env) for v in t[1:])
            if op=='tous':
                try:return any(test(t[3],{**env,t[1][1:]:v}) for v in self.p.ev(t[2],env))
                except Exception:return False
            if op=='existe' and isinstance(t[2],list) and t[2][0]=='objets':
                f=t[2][1]
                if not isinstance(f,dict) or set(f)-{'nom','tag','visible','couleur'}:return False
                # Montrer/recolorer peuvent rendre un objet éligible; s'abstenir.
                if 'visible' in f and 'montrer' in self.ops:return False
                if 'couleur' in f and self.ops & {'recolorer','ecrire','remodeler','poser_motif'}:return False
                try:return not self.p.ev(t[2],env)
                except Exception:return False
            return False
        return test(self.impasse_regle.get('quand'),e)

    def dist(self,t,e,depth):
        if depth>20:return 1.
        ev=lambda x:self.p.ev(x,e)
        try:
            if not isinstance(t,list) or not t:return 0. if ev(t) else 1.
            op,a=t[0],t[1:]
            if op in ['action','dernier_niveau','debut_niveau']:return 0.
            if op in ('et','ou'):
                vals=[self.dist(x,e,depth+1) for x in a]
                return (sum(vals) if op=='et' else min(vals,default=1.))
            if op in ('tous','existe'):
                xs=ev(a[1]) or []
                vals=[self.dist(a[2],{**e,a[0][1:]:x},depth+1) for x in xs]
                return sum(vals) if op=='tous' else min(vals,default=20.)
            if op=='non':
                x=a[0]
                if isinstance(x,list) and x:
                    inv={'=':'!=','!=':'=','>':'<=','>=':'<','<':'>=','<=':'>','et':'ou','ou':'et'}
                    if x[0] in ('et','ou'):return self.dist([inv[x[0]],*(['non',y] for y in x[1:])],e,depth+1)
                    if x[0] in inv:return self.dist([inv[x[0]],*x[1:]],e,depth+1)
                    if x[0]=='non':return self.dist(x[1],e,depth+1)
                return 0. if ev(t) else 1.
            if op=='si':return self.dist(a[1] if ev(a[0]) else a[2],e,depth+1)
            if op=='etat' and a[0] in self.reductions:
                return min(self.dist(v,e,depth+1) for v in self.reductions[a[0]])
            if op=='etat' and not ev(t) and a[0] in self.defs:
                return min(self.dist(v,e,depth+1) for v in self.defs[a[0]])
            if op in self.p.mots and self.p.mots[op].get('sorte','terme')=='terme':
                d=self.p.mots[op];ee={k:v for k,v in e.items() if k.startswith('_')}
                ee.update({k[1:]:ev(v) for k,v in zip(d.get('params',[]),a)})
                return self.dist(d['corps'],ee,depth+1)
            if op=='vide':return float(len(ev(a[0]) or []))
            if op in ['remplit','contact_moteur','chevauche']:
                if ev(t):return 0.
                u,v=map(ev,a[:2]);return 1.+(abs(u['x']-v['x'])+abs(u['y']-v['y']))/4
            if op in ['=','!=','<','<=','>','>=']:
                if op=='=' and isinstance(a[0],list) and a[0][:1]==['etat'] and not isinstance(a[1],(list,dict)):
                    if ev(t):return 0.
                    key=(a[0][1],str(a[1]))
                    if depth<8 and key in self.producteurs:
                        return min(self.dist(v,e,depth+1) for v in self.producteurs[key])
                    if depth<8 and a[0][1] in self.defs:
                        def eqexpr(x):
                            if isinstance(x,list) and x[:1]==['si']:
                                return ['ou',['et',x[1],eqexpr(x[2])],['et',['non',x[1]],eqexpr(x[3])]]
                            if not isinstance(x,list):return True if x==a[1] else ['=',0,1000]
                            return ['=',x,a[1]]
                        return min(self.dist(eqexpr(x),e,depth+1) for x in self.defs[a[0][1]])
                # Contraintes de pixels : distance à un pixel satisfaisant dans le masque.
                pix=next((x for x in a if isinstance(x,list) and x and x[0]=='pixel'),None)
                if pix is not None and not ev(t):
                    obj=ev(pix[1]);x,y=ev(pix[2]),ev(pix[3]);arr=np.asarray(obj['pixels'])
                    other=ev(a[1] if a[0] is pix else a[0]);mask=None
                    if op=='=':mask=arr==other
                    elif op=='!=':mask=arr>=0 if other is None else arr!=other
                    elif op=='>=' and other==0:mask=arr>=0
                    if mask is not None:
                        ys,xs=np.nonzero(mask)
                        return 1.+float(np.min(abs(xs-x)+abs(ys-y)))/4 if len(xs) else 20.
                if any(isinstance(x,list) and x and x[0]=='action' for x in a):return 0.
                if ev(t):return 0.
                x,y=map(ev,a)
                if isinstance(x,(int,float)) and isinstance(y,(int,float)) and not isinstance(x,bool):
                    return max(1.,abs(x-y))
                if isinstance(x,(list,tuple)) and isinstance(y,(list,tuple)):
                    return float(sum(_gel(u)!=_gel(v) for u,v in zip(x,y))+abs(len(x)-len(y)))
            return 0. if ev(t) else 1.
        except Exception:return 1.


def caracteristiques(sc,et):
    # Traits de nouveauté, jamais une clé d'équivalence.
    out=set()
    for i,o in enumerate(sc.sprites):
        out.add(('p',i,o['x'],o['y'],o.get('visible',True)))
        out.add(('d',i,_gel(o.get('pixels'))))
        for k,v in o.get('attrs',{}).items():
            if isinstance(v,(bool,int,float,str,type(None))):out.add(('a',i,k,v))
    for k,v in (et or {}).items():
        if isinstance(v,(bool,str,type(None))):out.add(('e',k,v))
    return out


def planifier(texte,scene,coups,noeuds=200000,secondes=300,etat=None,
              sous_buts=True,macros=True,impasses=True,elagage=True,seed=0,progression=None):
    start=time.monotonic();cpu=time.process_time();prog=ProgrammeCompile(texte);guide=Guide(texte)
    et0=copy.deepcopy(prog.etat if etat is None else etat)
    stats=dict(noeuds=0,developpes=0,doublons=0,sans_effet=0,defaites=0,macros=0,erreurs=0)
    # Deux files complémentaires : distance et nouveauté conditionnée par la distance.
    nodes=[(scene,et0,-1,(),0,{})];q=[];qn=[];expanded=set();seen={(cle(scene,et0),_gel({})):0};features=set();serial=0; transitions={}
    h0=guide.h(scene,et0,None,sous_buts);stats['h_initial']=h0;stats['h_min']=h0;heapq.heappush(q,(h0,0,0));heapq.heappush(qn,(0,h0,0))
    acts=list(coups); click_enabled=any(a[0]=="CLICK" for a in acts); action_cache={}
    acts=acts[seed%len(acts):]+acts[:seed%len(acts)] if acts else []
    def path(i,tail):
        chunks=[tail]
        while i>=0:
            _,_,i0,ch,_,_=nodes[i];chunks.append(ch);i=i0
        return [a for ch in reversed(chunks) for a in ch]
    def done(plan,reason):
        stats.update(secondes=time.monotonic()-start,cpu_s=time.process_time()-cpu,etats=len(seen),raison=reason)
        return plan,stats
    while (q or qn) and stats['noeuds']<noeuds and time.monotonic()-start<secondes:
        heap=qn if sous_buts and stats['developpes']%4==3 and qn else q
        if not heap:heap=qn
        *_,idx=heapq.heappop(heap)
        if idx in expanded:continue
        expanded.add(idx);sc,et,par,ch,g,snap=nodes[idx];stats['developpes']+=1
        nodes[idx]=(None,None,par,ch,g,None)  # garde les parents, libère les scènes développées
        parent_key=(cle(sc,et),_gel(snap));local=set()
        disponibles=acts
        if click_enabled:
            # Recrée les cibles depuis le rendu simulé, donc suit les pièces/caméras.
            from chrysalide.arc3.rendu import sprites
            img=sc.image_complete();ikey=(img.shape,img.tobytes())
            dyn=action_cache.get(ikey)
            if dyn is None:
                fond=int(np.bincount(img.ravel()).argmax());dyn=[]
                for o in sprites(img,fond):
                    pts=[(o[4]+y,o[3]+x) for y,x in o[2]]
                    cy=sum(y for y,x in pts)/len(pts);cx=sum(x for y,x in pts)/len(pts)
                    y,x=min(pts,key=lambda q:(q[0]-cy)**2+(q[1]-cx)**2)
                    dyn.append(('CLICK',int(y),int(x)))
                if len(action_cache)>10000:action_cache.clear()
                action_cache[ikey]=dyn
            disponibles=list(dict.fromkeys(acts+dyn))
        for a in disponibles:
            s,e=cloner(sc,et);chain=[];prog.instantanes=copy.deepcopy(snap);prog._ref.instantanes=prog.instantanes
            repeat=4 if macros and a[0] in ('UP','DOWN','LEFT','RIGHT') else 1
            for rep in range(repeat):
                if stats['noeuds']>=noeuds or time.monotonic()-start>=secondes:break
                prog.etat=e;stats['noeuds']+=1
                if progression is not None:progression(stats['noeuds'])
                tk=(cle(s,e),_gel(prog.instantanes),a) if elagage else None
                cached=transitions.get(tk) if elagage else None
                if cached is not None:
                    s,e=cloner(cached[0],cached[1]);prog.etat=e
                    prog.instantanes=copy.deepcopy(cached[2]);prog._ref.instantanes=prog.instantanes
                    stats['cache_hits']=stats.get('cache_hits',0)+1
                else:
                    try:prog.step(s,a)
                    except Exception as exc:
                        stats['erreurs']+=1;stats.setdefault('premiere_erreur',repr(exc));break
                    e=prog.etat;stats['simulations']=stats.get('simulations',0)+1
                    if elagage:
                        if len(transitions)>=2048:transitions.clear()
                        ss,ee=cloner(s,e);transitions[tk]=(ss,ee,copy.deepcopy(prog.instantanes))
                chain.append(a)
                if s.issue in ('niveau','victoire'):return done(path(idx,tuple(chain)),'but_simule')
                if s.issue is not None:
                    stats['defaites']+=1
                    break
                kk=(cle(s,e),_gel(prog.instantanes))
                if elagage and (kk==parent_key or kk in local):stats['sans_effet']+=1;break
                local.add(kk);ng=g+len(chain)
                if kk in seen and seen[kk]<=ng:stats['doublons']+=1;break
                seen[kk]=ng
                if impasses and guide.impossible(s,e):
                    stats['impasses_prouvees']=stats.get('impasses_prouvees',0)+1
                    break
                h=guide.h(s,e,a,sous_buts)
                stats['h_min']=min(stats['h_min'],h)
                fs=caracteristiques(s,e) if sous_buts else set();bucket=int(h)
                fresh={(bucket,f) for f in fs}-features;features.update((bucket,f) for f in fs)
                sn,en=cloner(s,e);ni=len(nodes);nodes.append((sn,en,idx,tuple(chain),ng,copy.deepcopy(prog.instantanes)));serial+=1
                weight=[.03,.1,.3,0.,.01,.05,.2,.5][seed%8]
                heapq.heappush(q,(h+weight*ng,ng,ni));heapq.heappush(qn,(0 if fresh else 1,h+weight*ng,ni))
                if rep:stats['macros']+=1
    return done(None,'budget' if q or qn else 'espace_epuise')


def _worker_portefeuille(queue, compteur, index, texte, scene, coups, kwargs):
    try:
        plan,stats=planifier(texte,scene,coups,seed=index,
                             progression=lambda n:setattr(compteur[index], 'value', n),**kwargs)
        queue.put((index,plan,stats))
    except Exception as exc:queue.put((index,None,{'raison':'erreur','erreur':repr(exc)}))


def portefeuille(texte,scene,coups,noeuds=200000,secondes=300,processus=8,**kwargs):
    """Portefeuille CPU; budget de nœuds PAR PROCESSUS, temps mural commun.
    Rend le premier plan simulé; l'appelant doit toujours le vérifier dans le jeu.
    """
    import multiprocessing as mp
    import queue as queue_module
    ctx=mp.get_context('spawn');q=ctx.Queue();counts=[ctx.Value('q',0,lock=False) for _ in range(processus)]
    start=time.monotonic();jobs=[];finished=[];plan=None;winner=None
    for i in range(processus):
        p=ctx.Process(target=_worker_portefeuille,args=(q,counts,i,texte,scene,coups,dict(noeuds=noeuds,secondes=secondes,**kwargs)))
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
                 'noeuds_par_processus':[c.value for c in counts],'termines':finished}
