"""Évaluation hors préfixe, aucune interaction avec le SDK."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from chaine_agent_integree import lots
from representation_legacy_sans_but import construire
from perception_marqueur_candidat import TrajectoireMarqueurCandidat

R=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    files=[R/n for n in ('perception_marqueur_candidat.py','representation_legacy_sans_but.py','PROTOCOLE_PERCEPTION_BORD_RE86.md','auditer_perception_bord.py')]
    frozen={str(p.relative_to(R)):sha(p) for p in files}
    p=R/'runs/publics_ref_g0/re86/N1/partie'
    z=np.load(p.with_suffix('.npz'))
    rows=json.loads(p.with_suffix('.json').read_text())['rows']
    h={'grilles':z['images'][:9], 'lots':lots([x['action'] for x in rows[:8]])}
    report={'code_sha256':frozen,'archive_sha256':{ext:sha(p.with_suffix(ext)) for ext in ('.json','.npz')},'prefixe':8,'sdk_actions':0,'profils':{}}
    for name,factory in [('pixels_herites',None),('marqueur_identite_bord',TrajectoireMarqueurCandidat)]:
        start=time.process_time()
        c,r=construire(h,limite_s=2,echelle=(1,0,0),trajectoire_factory=factory)
        tr,th=c.perception.tr,c.perception.th_releve
        # On réutilise strictement le masque du préfixe.
        mask=np.ones(tr.cases[0].shape,dtype=bool)
        for y,x in tr.exclues:mask[y,x]=False
        def err(e,g):return int(np.count_nonzero((th.rendu(e,tr.taille,tr.fond)!=g)&mask))
        records=[];resets=[];free=tr.etat(z['images'][8])
        for i in range(8,len(rows)):
            obs=z['images'][i];target=z['images'][i+1]
            state=tr.etat(obs)
            action=rows[i]['action']
            if action==0:
                resets.append(i+1);free=tr.etat(target);continue
            from chrysalide.arc3.moteur import _codes_c
            a=_codes_c(lots([action]))[0]
            if a is None:raise ValueError('Action non prise en charge')
            pred,_=th.pas(state,a,tr.taille)
            free,_=th.pas(free,a,tr.taille)
            records.append({'coup':i+1,'reconstruction_pixels':err(state,obs),'prediction_pixels':err(pred,target),'libre_pixels':err(free,target)})
        report['profils'][name]={'controle_prefixe':r,'cpu_s':time.process_time()-start,'resets_non_predits':resets,'n_suite':len(records),'reconstructions_exactes':sum(x['reconstruction_pixels']==0 for x in records),'predictions_exactes':sum(x['prediction_pixels']==0 for x in records),'libre_exactes':sum(x['libre_pixels']==0 for x in records),'records':records}
    out=R/'AUDIT_PERCEPTION_BORD_RE86.json';out.write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps({k:{x:y for x,y in v.items() if x!='records'} for k,v in report['profils'].items()},ensure_ascii=False))

if __name__=='__main__':main()
