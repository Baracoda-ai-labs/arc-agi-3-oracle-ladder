"""Comparaison hors SDK, même historique figé et même reconstruction gagnante."""
import copy
import json
import os
import time
from pathlib import Path
from chaine_coherente import Chaine
from chrysalide.arc3.logique.export_langage import exporter
import reprise_niveaux_observes as reprise


def main(iterer=False, quinze=False, grounding=False, distance_cycle=False):
    base=Path(__file__).parent
    source=base/'runs/session_ft09_transfert_n4_1'
    meta=json.loads((source/'etat.json').read_text())
    rows=json.loads((source/'N4/partie.json').read_text())['rows']
    assert meta['niveau']==4 and len(rows)==200, (meta['niveau'],len(rows))
    os.environ.update(CHRYS_BUT_SUPPOSE='1',CHRYS_TRANSFERT='0',CHRYS_CHAINE_COHERENTE='0',CHRYS_REPARATION_BLOCAGE='0')
    original=reprise.MoteurC
    rapport={'source':str(source.resolve()),'prefixe_N4':200,'sdk':0,'bras':[]}
    for budget in ((15,) if quinze else (2,) if iterer or grounding else (2,15)):
        arm={'budget_N4':budget,'niveaux':[]}
        from chrysalide.arc3.logique import induction
        from chrysalide.arc3.logique.theorie import rejeu
        from chrysalide.arc3.logique.transfert import fusionner
        induction_originale=induction.induire
        def affiner(sources,**kwargs):
            th,infos=induction_originale(sources,**kwargs)
            if len(sources)!=1 or sources[0][1] is not None:return th,infos
            tr=sources[0][0];ok,n,premier=rejeu(th,tr)
            while premier is not None:
                complement,_=induction_originale([(tr,[premier],None)],limite_s=.2)
                candidat=fusionner(th,complement)
                apres,total,suivant=rejeu(candidat,tr)
                arm.setdefault('revisions',[]).append(dict(avant=ok,apres=apres,total=total,indice=premier))
                if apres<=ok:break
                th,ok,premier=candidat,apres,suivant
            return th,infos
        if iterer:induction.induire=affiner
        class AuditMoteur(original):
            def proposer(self,h):
                niveau=len(h.get('precedents',[]))+1
                if niveau==4:self.budget=budget
                debut=time.monotonic()
                r=super().proposer(h)
                detail={'niveau':niveau,'duree':time.monotonic()-debut,'infos':copy.deepcopy(self.infos),
                        'but':repr(getattr(self,'th_plan',None).but if getattr(self,'th_plan',None) else self.th_releve.but if self.th_releve else None),
                        'plan':r[0] if r else None}
                arm['niveaux'].append(detail)
                if niveau==4:
                    arm['memoire_N3']=repr(self.theorie_precedente.but if self.theorie_precedente else None)
                    th=getattr(self,'th_plan',None) or self.th_releve
                    if th:
                        arm['bascule']=th.bascule
                        prog,non=exporter(th,self.tr.taille)
                        c=Chaine(self,prog,h['grilles'],h['lots'],[],coups_deja_joues=len(h['lots']),
                                 reserve=len(h['lots'])+self.infos.get('reserve_plan',{}).get('coups',0))
                        ck,etat=c.rejouer();arm.update(controle=ck,admissible=etat is not None,non_exporte=non)
                        if grounding and etat is not None:
                            from chrysalide.arc3.moteur import _clics_offerts,_plan_langage
                            from chrysalide.arc3.logique.theorie import centres_motifs,cells,VOISINS8
                            from chrysalide.arc3.logique.plan import distance_but
                            clics=_clics_offerts(th,self.tr)
                            col={q:o[0] for o in self.tr.etats[-1] for q in cells(o)}
                            centres=centres_motifs(col,{0,2})
                            arm['grounding']=dict(clics=clics,score=distance_but(th,self.tr.etats[-1]),
                                centres=[(z,col[z]) for z in centres],
                                contraintes=[dict(case=(z[0]+4*dx,z[1]+4*dy),centre=col[z],meme=col[z[0]+dx,z[1]+dy]==0,
                                    actuel=col.get((z[0]+4*dx,z[1]+4*dy))) for z in centres for dx,dy in VOISINS8])
                            t=time.monotonic()
                            if distance_cycle:
                                import numpy as np
                                from chrysalide.arc3.logique.plan_langage import planifier_langage
                                from chrysalide.arc3.moteur import _lot_c,nom_action
                                assert th.motif == frozenset({(0,0)}) and not th.moves and not th.autonomes
                                contraintes=arm['grounding']['contraintes']
                                palette=set(th.bascule)|set(th.bascule.values())
                                groupes=[]
                                for obj in self.tr.etats[-1]:
                                    cs=cells(obj)
                                    req=[q for q in contraintes if tuple(q['case']) in cs]
                                    if not req:continue
                                    acceptables={k for k in palette if all((k==q['centre'])==q['meme'] for q in req)}
                                    assert acceptables
                                    couts={}
                                    for debut_c in palette:
                                        k=debut_c;vus=set();n=0
                                        while k not in vus and k not in acceptables:
                                            vus.add(k);k=th.bascule.get(k,k);n+=1
                                        couts[debut_c]=n if k in acceptables else float('inf')
                                    groupes.append((tuple(req[0]['case']),couts))
                                def score(scene,etat):
                                    couleurs={}
                                    for sp in scene.sprites:
                                        if not sp['visible']:continue
                                        p=np.asarray(sp['pixels']);ys,xs=np.nonzero(p>=0)
                                        couleurs.update({(sp['x']+int(x),sp['y']+int(y)):int(p[y,x]) for y,x in zip(ys,xs)})
                                    return sum(couts.get(couleurs.get(q),float('inf')) for q,couts in groupes)
                                pc,sc=etat
                                coups=[nom_action(_lot_c(a,self.tr)) for a in clics]
                                seq,inf=planifier_langage(prog,sc,coups,secondes=15,noeuds=20000,etat=pc.etat,estimer=score)
                                arm['distance_cycle']=dict(score_initial=score(sc,pc.etat),groupes=len(groupes),infos=inf)
                                pl=[{'action':a[0],'row':a[1],'col':a[2]} for a in seq] if seq else None
                            else:
                                pl=_plan_langage(self,prog,h,[],15,clics=clics)
                            arm['fallback_clics']=dict(duree=time.monotonic()-t,infos=self.infos.get('plan_langage'),plan=pl)
                            if pl:
                                r=(pl,prog);self.th_plan=self.th_releve=th
                                detail['plan']=pl
                        if r:
                            arm['source_synchronisee']=prog==r[1] and exporter(self.th_releve,self.tr.taille)[0]==r[1]
                            arm['adoption']=c.adopter_plan([Chaine.action_tuple(x) for x in r[0]])
                return r
        reprise.MoteurC=AuditMoteur
        try:
            a,_,_=reprise.preparer(source)
            arm['reprise_admise']=True
            arm['plan_final']=a.chaines['p1_but_hypothese'].plan
        except Exception as exc:
            arm.update(reprise_admise=False,erreur=repr(exc))
        finally:
            reprise.MoteurC=original
            induction.induire=induction_originale
        rapport['bras'].append(arm)
        print(json.dumps({'budget':budget,'reprise':arm['reprise_admise'],'erreur':arm.get('erreur'),
                          'N4':next((n for n in arm['niveaux'] if n['niveau']==4),None)},ensure_ascii=False),flush=True)
    out=base/('AUDIT_BUDGET_REPRISE_FT09_N4_ITERE.json' if iterer else 'AUDIT_BUDGET_REPRISE_FT09_N4_RUNTIME.json')
    if quinze:out=out.with_stem(out.stem+'_15S')
    if grounding:out=out.with_stem(out.stem+'_CLICS')
    if distance_cycle:out=out.with_stem(out.stem+'_DISTANCE')
    out.write_text(json.dumps(rapport,ensure_ascii=False,indent=2,default=str)+'\n')

if __name__=='__main__':
    import sys
    main(iterer='--iterer' in sys.argv,quinze='--quinze' in sys.argv,grounding='--grounding' in sys.argv,distance_cycle='--distance-cycle' in sys.argv)
