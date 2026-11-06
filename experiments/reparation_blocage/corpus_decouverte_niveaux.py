"""Étend l'export existant aux niveaux suivants sans confondre coûts et futurs."""
import json,hashlib
from pathlib import Path
import numpy as np
from corpus_decouverte import exemple,sauver

def exporter(run,sortie):
    sortie.mkdir(parents=True,exist_ok=False)
    meta=json.loads((run/'etat.json').read_text());index=[];offset=0
    for niveau in sorted(run.glob('N[0-9]*'),key=lambda p:int(p.name[1:])):
        rows=json.loads((niveau/'partie.json').read_text())['rows'];actions=[r['action'] for r in rows]
        with np.load(niveau/'partie.npz') as z:
            images=z['images'];films=[z[f'film_{i+1}'] for i in range(len(rows))]
            dossiers=run.glob('decision_coup_*') if niveau.name=='N1' else niveau.glob('decision_coup_*')
            for folder in sorted(dossiers):
                if not (folder/'observation.json').exists():continue
                obs=json.loads((folder/'observation.json').read_text());d=json.loads((folder/'decision.json').read_text());k=obs['coup']
                ident,entree,cible=exemple(images,films,actions,k,d,obs)
                p=sortie/ident;p.mkdir()
                entree.update(niveau=int(niveau.name[1:]),coups_campagne_avant=offset+k-1)
                np.savez_compressed(p/'entree.npz',images=images[:k],**{f'film_{i+1}':films[i] for i in range(k-1)})
                np.savez_compressed(p/'resultat.npz',image=images[k],film=films[k-1])
                sauver(p/'entree.json',entree);sauver(p/'resultat.json',cible)
                index.append(dict(id=ident,source=str(folder.resolve()),jeu=meta['jeu'],niveau=niveau.name,
                    coup_niveau=k,coups_campagne_avant=offset+k-1,partition='developpement_deja_consulte'))
        offset+=len(rows)
    sauver(sortie/'index.json',index)
    sauver(sortie/'manifest.json',{str(p.relative_to(sortie)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sortie.rglob('*') if p.is_file()})
    return dict(exemples=len(index),coups_reels_source=offset,entrainement=False,action_optimale=None)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);a=p.parse_args()
    print(json.dumps(exporter(a.run,a.sortie)))
