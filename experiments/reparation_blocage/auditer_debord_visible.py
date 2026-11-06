"""Deux traces réservées, correction ablatée, aucun appel au jeu."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from chaine_agent_integree import lots
from representation_legacy_sans_but import construire
from perception_marqueur_candidat import TrajectoireMarqueurCandidat
from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.moteur import _codes_c
from chrysalide.arc3.logique.presence import preuves_presence
R=Path(__file__).resolve().parent
ROOT=R.parents[1]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    z=np.load(p.with_suffix('.npz'));return z['images'],json.loads(p.with_suffix('.json').read_text())['rows']
def key(a,action,b):
    return hashlib.sha256(a.astype('int16').tobytes()+json.dumps(action,sort_keys=True).encode()+b.astype('int16').tobytes()).hexdigest()
def factory(gs,actions):
    try:return TrajectoireMarqueurCandidat(gs,actions)
    except ValueError as e:
        if str(e)!='Aucune coupure par marqueur géométrique':raise
        return Trajectoire(gs,actions,ech=(1,0,0))

def main():
    paths=[R/'auditer_debord_visible.py',R/'PROTOCOLE_DEBORD_VISIBLE.md',R/'perception_marqueur_candidat.py',R/'representation_legacy_sans_but.py',R/'paquet/chrysalide/arc3/logique/theorie.py',R/'paquet/chrysalide/arc3/logique/export_langage.py',R/'paquet/chrysalide/arc3/logique/induction.py',R/'paquet/chrysalide/arc3/logique/presence.py']
    reference=json.loads((R/'AUDIT_DEPLACEMENT_POUSSE.json').read_text())
    report={'comparaison_retrospective':True,'baseline_cache_sha':digest(R/'AUDIT_DEPLACEMENT_POUSSE.json'),'empreintes_code':{str(p.relative_to(R)):digest(p) for p in paths},'sdk_actions':0,'jeux':{}}
    for game in ('re86','lf52'):
        p=R/f'runs/publics_ref_g0/{game}/N1/partie'
        q=ROOT/f'experiments/E_franzen/t1_controle/runs/on2_pub_g1/{game}/N1/partie'
        gs,rows=load(p)
        known={key(gs[i],r['action'],gs[i+1]) for i,r in enumerate(rows)}
        hist={'grilles':gs[:9],'lots':lots([r['action'] for r in rows[:8]])}
        candidates={}
        for enabled in (True,):
            start=time.process_time()
            c,control=construire(hist,limite_s=2,trajectoire_factory=factory,presence_prudente=True,dedoublonne_poussee=True,debord_visible=True)
            candidates[str(enabled)]=(c,control,time.process_time()-start)
        # Réserve lue seulement après apprentissage figé des deux bras.
        obs,held=load(q)
        entry={'archives':{str(x.relative_to(ROOT)):digest(x) for base in (p,q) for x in (base.with_suffix('.json'),base.with_suffix('.npz'))},'bras':{}}
        for label,(c,control,cpu) in candidates.items():
            tr,th=c.perception.tr,c.perception.th_releve
            mask=np.ones(tr.cases[0].shape,dtype=bool)
            for y,x in tr.exclues:mask[y,x]=False
            def err(e,g):return int(np.count_nonzero((th.rendu(e,tr.taille,tr.fond)!=g)&mask))
            records=[];duplicates=0;resets=[];seen=set(known);start=time.process_time()
            for i,row in enumerate(held):
                action=row['action'];k=key(obs[i],action,obs[i+1])
                if k in seen:duplicates+=1;continue
                seen.add(k)
                if action==0:resets.append(i+1);continue
                state=tr.etat(obs[i]);a=_codes_c(lots([action]))[0]
                pred,_=th.pas(state,a,tr.taille)
                records.append({'coup':i+1,'transition_sha256':k,'reconstruction_pixels':err(state,obs[i]),'prediction_pixels':err(pred,obs[i+1])})
            entry['bras'][label]={'controle':control,'perception':type(tr).__name__,'consomme':sorted(map(list,th.consomme)),'lie':sorted(map(list,th.lie)),'doublons_exclus':duplicates,'resets_hors_mesure':resets,'n':len(records),'exactes':sum(x['prediction_pixels']==0 for x in records),'reconstruction_exacte':sum(x['reconstruction_pixels']==0 for x in records),'cpu_induction_s':cpu,'cpu_prediction_s':time.process_time()-start,'records':records}
        entry['bras']['False']=reference['jeux'][game]['bras']['True']
        a,b=(entry['bras'][x]['records'] for x in ('False','True'))
        assert [r['transition_sha256'] for r in a]==[r['transition_sha256'] for r in b]
        entry['comparaison']={'gains':sum(x['prediction_pixels']!=0 and y['prediction_pixels']==0 for x,y in zip(a,b)),'pertes':sum(x['prediction_pixels']==0 and y['prediction_pixels']!=0 for x,y in zip(a,b))}
        entry['comparaison']['anciens_succes_conserves']=all(y['prediction_pixels']==0 for x,y in zip(a,b) if x['prediction_pixels']==0)
        report['jeux'][game]=entry
    (R/'AUDIT_DEBORD_VISIBLE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({g:{'comparaison':v['comparaison'],'bras':{k:{x:y for x,y in b.items() if x not in ('records','controle')} for k,b in v['bras'].items()}} for g,v in report['jeux'].items()},ensure_ascii=False))
if __name__=='__main__':main()
