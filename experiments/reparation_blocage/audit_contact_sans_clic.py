"""Audit causal sur archive : induction au premier contact, suffixe tenu à l'écart."""
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
from roles_observes import PerceptionRoles
from chaine_coherente import Chaine
from chaine_agent_integree import lots, canon
from revision_faces_contact import proposer


def auditer(source, sortie, coup):
    debut=time.process_time(); trace=source/'N1/partie'
    with np.load(trace.with_suffix('.npz')) as z:
        images=z['images']; rows=json.loads(trace.with_suffix('.json').read_text())['rows']
        actions=[r['action'] for r in rows]
        films=[z[f'film_{i+1}'] for i in range(len(actions))]
        perception=PerceptionRoles(images[:coup],actions[:coup-1])
        resultats=[]
        # Les buts existants ne sont ni modifiés ni choisis à partir du suffixe.
        for but in perception.buts[:3]:
            original=Chaine(perception,perception.programme(but),images[:coup+1].tolist(),
                lots(actions[:coup]),[],films=films[:coup])
            corrige,diagnostic=proposer(original)
            record={'but_existant':but,'diagnostic':diagnostic,'suffixe':[]}
            if corrige is not None:
                _,(programme,scene)=corrige.rejouer()
                for i in range(coup,len(actions)):
                    programme.step(scene,canon(actions[i]))
                    attendu=perception.rendu(scene);vu=perception.vue(images[i+1])
                    record['suffixe'].append({'coup':i+1,'ecart_vue':int((attendu!=vu).sum()),
                        'ecart_natif':int((attendu!=images[i+1]).sum())})
            resultats.append(record)
    rapport={'source':str(source),'empreintes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (trace.with_suffix('.json'),trace.with_suffix('.npz'))},
        'induction_jusqua':coup,'reinduction_suffixe':False,'sdk_actions':0,
        'portee':'vue conservee avec masque existant ; ecart natif inclut ce masque',
        'cpu_s':time.process_time()-debut,'resultats':resultats}
    sortie.write_text(json.dumps(rapport,indent=2));return rapport


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--sortie',type=Path,required=True);p.add_argument('--coup',type=int,required=True)
    a=p.parse_args();r=auditer(a.source,a.sortie,a.coup)
    print(json.dumps({'modeles':len(r['resultats']),'admis':sum(x['diagnostic']['admis'] for x in r['resultats']),
        'cpu_s':r['cpu_s'],'sdk_actions':0}))
