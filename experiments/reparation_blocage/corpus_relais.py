"""Nouveaux journaux du relais vers le corpus existant, sans futur dans les entrées."""
import json,hashlib,argparse
from pathlib import Path
import numpy as np
from corpus_decouverte import exemple,sauver


def exporter(run,lots,sortie):
    sortie.mkdir(parents=True,exist_ok=False);index=[];vus=set()
    meta=json.loads((run/'provenance.json').read_text())
    for lot in lots:
        bilan=json.loads((lot/'bilan.json').read_text());niveau=bilan['etat_sdk']['niveau']
        p=run/f'N{niveau}/partie';rows=json.loads(p.with_suffix('.json').read_text())['rows']
        actions=[r['action'] for r in rows]
        offset=sum(len(json.loads((run/f'N{n}/partie.json').read_text())['rows']) for n in range(1,niveau))
        with np.load(p.with_suffix('.npz')) as z:
            images=z['images'];films=[z[f'film_{i+1}'] for i in range(len(rows))]
            for path in sorted(lot.glob('decision_*.json')):
                obs=path.with_name(path.name.replace('decision_','observation_',1))
                if not obs.exists():continue
                d=json.loads(path.read_text());o=json.loads(obs.read_text());k=o['coup']
                ident,entree,cible=exemple(images,films,actions,k,d,o)
                if ident in vus:continue
                vus.add(ident);dest=sortie/ident;dest.mkdir()
                entree.update(niveau=niveau,coups_campagne_avant=offset+k-1)
                np.savez_compressed(dest/'entree.npz',images=images[:k],**{f'film_{i+1}':films[i] for i in range(k-1)})
                np.savez_compressed(dest/'resultat.npz',image=images[k],film=films[k-1])
                sauver(dest/'entree.json',entree);sauver(dest/'resultat.json',cible)
                index.append({'id':ident,'jeu':meta['jeu'],'niveau':niveau,'coup':k,
                    'source':str(path.resolve()),'partition':'developpement_deja_consulte'})
    sauver(sortie/'index.json',index)
    sauver(sortie/'manifest.json',{str(p.relative_to(sortie)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sortie.rglob('*') if p.is_file()})
    return {'exemples':len(index),'entrainement':False,'imitation_action_autorisee':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--lots',type=Path,nargs='+',required=True);p.add_argument('--sortie',type=Path,required=True)
    a=p.parse_args();print(json.dumps(exporter(a.run,a.lots,a.sortie)))
