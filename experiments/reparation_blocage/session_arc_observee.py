"""Une session SDK bornée, commandes et prédictions persistées avant chaque action."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from boucle_objets_variables import ICI, LaboP1
from PIL import Image

from chrysalide.qwen.images import PAL


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sortie',type=Path,required=True);args=ap.parse_args()
    out=args.sortie;out.mkdir(parents=True,exist_ok=False)
    lab=LaboP1('ka59',1,'/Users/ts/models/chrysalide3/experiments/G/publics20c',out/'N1/partie')
    journal=[];appels=0
    def save():
        (out/'journal.json').write_text(json.dumps(journal,ensure_ascii=False,indent=2))
        Image.fromarray(PAL[lab.image]).resize((640,640),Image.Resampling.NEAREST).save(out/'courant.png')
        b={'coups_reels':len(lab.rows),'appels_step_tentes':appels,'initialisations':1,
            'niveaux_gagnes':int(lab.won),'jeu_gagne':lab.partie_gagnee,'fini':lab.finished}
        (out/'bilan.json').write_text(json.dumps(b,indent=2));print(json.dumps(b),flush=True)
    try:
        r=ICI/'runs/guidage_ka59_fige1/N1'
        with np.load(r/'partie.npz') as z:archive=z['images'].copy()
        rows=json.loads((r/'partie.json').read_text())['rows']
        if not np.array_equal(archive[0],lab.image): raise ValueError('Initial différent')
        for k,row in enumerate(rows):
            appels+=1;g,_=lab.play(row['action'],purpose='restauration_comptee')
            if lab.finished or not np.array_equal(g,archive[k+1]): raise ValueError('Restauration différente')
        save()
        for ligne in sys.stdin:
            if ligne.strip()=='fermer': break
            try:
                req=json.loads(ligne);p=Path(req['experience']);raw=p.read_bytes();e=json.loads(raw)
                entry={'experience':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'avant':len(lab.rows),'resultats':[]}
                journal.append(entry);save()
                actions=e['actions']
                if not 1<=len(actions)<=12: raise ValueError('1 à 12 coups maximum par expérience')
                if len(e.get('predictions',[]))!=len(actions): raise ValueError('Prédiction exigée pour chaque coup')
                for k,a in enumerate(actions):
                    if lab.finished or len(lab.rows)>=80: break
                    code=a if type(a) is int else 6
                    offre=[int(getattr(x,'value',x)) for x in lab.actions_disponibles]
                    if code not in offre: raise ValueError('Action indisponible')
                    appels+=1;g,film=lab.play(a,purpose=e['question'])
                    tests=[]
                    for h in e['predictions'][k]:
                        pred=np.array(h['image']);obs=g.copy()
                        for y,x in e.get('hud',[]): pred[y,x]=obs[y,x]=0
                        diff=int(np.count_nonzero(pred!=obs))
                        tests.append({'nom':h['nom'],'pixels_ecart':diff,'fin_predite':h.get('fin',False),
                            'conforme':diff==0 and bool(h.get('fin',False))==lab.won})
                    entry['resultats'].append({'coup':len(lab.rows),'comparaisons':tests,'frames':len(film),
                                               'victoire_sdk':lab.won})
                    save()
                    if lab.finished or not any(t['conforme'] for t in tests): break
            except Exception as ex:  # noqa: BLE001 — refus du contrôleur conservé
                journal.append({'erreur':repr(ex)});save()
            if lab.finished or len(lab.rows)>=80: break
    finally: save()


if __name__=='__main__': main()
