"""Mesure CPU/Metal sur les prédictions enregistrées, sans nouvelle action ni entraînement."""
import argparse,json,time,statistics,hashlib
from pathlib import Path
import numpy as np


def mesurer(source,sortie):
    import mlx.core as mx
    d=json.loads(source.read_text());l=d['diagnostic']['classement']
    x=np.array([[v for v in e['predictions'].values()] for e in l],dtype=np.int32)
    def cpu():return np.sum(x[:,:,None]!=x[:,None,:],axis=(-2,-1))
    def gpu():
        a=mx.array(x);r=mx.sum(a[:,:,None]!=a[:,None,:],axis=(-2,-1));mx.eval(r);return np.array(r)
    with mx.stream(mx.gpu):
        first=time.perf_counter();out=gpu();cold=time.perf_counter()-first
        assert np.array_equal(cpu(),out)
        times={}
        for name,fn in [('cpu',cpu),('gpu_metal',gpu)]:
            ts=[]
            for _ in range(30):
                t=time.perf_counter();r=fn();ts.append(time.perf_counter()-t)
            times[name]={'mediane_s':statistics.median(ts),'min_s':min(ts),'max_s':max(ts)}
    report={'source':str(source.resolve()),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'forme':list(x.shape),'tache':'distances pixels entre predictions par experience',
        'resultats_exacts':True,'gpu_premier_appel_s':cold,'mesures':times,
        'transferts_inclus':True,'sdk_actions':0,'entrainement':False,
        'portee':'microbanc du classement ; ne mesure ni simulation ni recherche ni victoire'}
    sortie.write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);a=p.parse_args();mesurer(a.source,a.sortie)
