"""Admission des capacités intégrées et prédictions avant expérience, sans SDK."""
import hashlib
import json
from pathlib import Path
import numpy as np
from chaine_agent_integree import lots
from perception_clics_couples import proposer
from chrysalide.arc3.logique.export_langage import exporter


def main():
    base=Path(__file__).parent;source=base/'runs/session_ft09_cycle3_1/N5'
    z=np.load(source/'partie.npz');images=z['images'][:101].copy()
    rows=json.loads((source/'partie.json').read_text())['actions'][:100]
    films=[z[f'film_{i+1}'] for i in range(100)]
    candidats=proposer(images,lots(rows),films)
    rapport={'source':str(source.resolve()),'sdk':0,'calibration':8,'observations':100,
             'candidats':[c.diagnostic_hitbox for c in candidats],'experiences':[]}
    assert len(candidats)>=2, rapport
    assert all(exporter(c.perception.th_releve,c.perception.tr.taille)[0]==c.programme for c in candidats)
    commun=next(c.perception.tr for c in candidats if c.diagnostic_hitbox['connexite']==8 and c.diagnostic_hitbox['interaction']=='boite')
    for act in sorted({a for c in candidats for a in c.actions}):
        case=commun.action_cases(('clic',act[2],act[1]))
        objets=[o for o in commun.etats[-1] if (case[1]-o[2],case[2]-o[3]) in o[1]]
        if not objets:continue
        o=objets[0];xs=[x+o[2] for x,y in o[1]];ys=[y+o[3] for x,y in o[1]]
        if any(min(xs)<=a[1]<=max(xs) and min(ys)<=a[2]<=max(ys) for a in commun.actions):continue
        predictions=[];rendus=[]
        for c in candidats:
            _,(pc,sc)=c.rejouer();avant=c.perception.rendu(sc).copy()
            pc.step(sc,act);apres=c.perception.rendu(sc)
            rendus.append(apres)
            predictions.append({'hypothese':str(c.diagnostic_hitbox['connexite'])+'_'+c.diagnostic_hitbox['interaction'],
                'pixels_changes':int(np.count_nonzero(avant!=apres)),
                'sha256':hashlib.sha256(apres.tobytes()).hexdigest(),'issue':sc.issue})
        ecart=max(int(np.count_nonzero(a!=b)) for i,a in enumerate(rendus) for b in rendus[i+1:])
        if ecart:
            rapport['experiences'].append(dict(action=['clic',act[2],act[1]],nouveau_bouton=True,
                pixels_ecart=ecart,predictions=predictions,statut='prediction_non_testee'))
    rapport['experiences'].sort(key=lambda d:(-d['pixels_ecart'],d['action'][1:]))
    rapport['recommandee']=rapport['experiences'][0] if rapport['experiences'] else None
    (base/'AUDIT_HITBOX_CLICS_COUPLES.json').write_text(json.dumps(rapport,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'admis':len(candidats),'hypotheses':[c.diagnostic_hitbox['interaction'] for c in candidats],
        'experiences':len(rapport['experiences']),'recommandee':rapport['recommandee']},ensure_ascii=False))

if __name__=='__main__':main()
