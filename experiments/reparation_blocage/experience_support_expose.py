"""Une sonde de précondition inconnue, aucune prédiction de sécurité inventée."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from boucle_navigation_visible import sauver
from boucle_objets_variables import LaboP1
from experience_refermeture_N3_bp35 import charger_prefixe
from preflight_interventions_bp35 import charger

R=Path(__file__).parent
PREFIXES=[('bp35_navigation_visible_reprise1/N1',None),('remontee_bp35_reel1/N2',None),('route_phase_N3_reel2/N3',6)]
from support_planificateur_audit import preparer
_modele,_h,_cs,_z,_j,_regle=preparer()
_image=_z['images'][6];_cx,_cy=_modele.position(_image)
_ys,_xs=np.nonzero(np.isin(_image,list(_modele.palette)))
_candidates=sorted((abs(x-_cx),x,y) for x,y in _regle['pixels_xy'] if y==_cy and _image[y,x]==_modele.sol and (x<_xs.min() or x>_xs.max()))
if not _candidates: raise ValueError('Aucun pixel expose admissible')
_,_x,_y=_candidates[0]
ACTION=['clic',_x,_y]

def main(out, executer):
    out.mkdir(parents=True,exist_ok=False)
    m,*_=charger()
    z,_=charger_prefixe(PREFIXES[-1][0]); target=z['images'][6]
    matches=[]; count=0
    for d in (R/'runs').iterdir():
        if not d.is_dir() or not ('bp35' in d.name.lower() or d.name.startswith(('route_phase_N3','contact_N3','horloges_N3','annulation_N3','refermeture_N3','support_occupe','support_expose'))): continue
        for p in d.glob('N*/partie.json'):
            if not p.with_suffix('.npz').exists(): continue
            j=json.loads(p.read_text()); zz=np.load(p.with_suffix('.npz'))
            for i,a in enumerate(j['actions']):
                count+=1
                if a==ACTION and np.array_equal(zz['images'][i],target): matches.append([str(p),i])
    pre={'action':ACTION,'position_avant':m.position(target),'doublons':matches,'actions_inspectees':count,'acces_attendu':[15,43,6],'nouveau':1,'risque':'defaite, deplacement ou effet inconnu ; aucune garantie de securite','issues':['ignore: occupation interdite ou hitbox inconnue','fermeture: clic central intercepte compatible','controle deplace','defaite','autre'],'limite_nouveaute':'index cible archives N*/partie ; pas exhaustif hors index'}
    sauver(out/'preflight.json',pre)
    if matches or not executer: print(json.dumps(pre)); return
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('*.py')}
    sauver(out/'sources.json',sources)
    labs=[]; result={}; status='initialisation'; init=0
    try:
        for level,(name,n) in enumerate(PREFIXES,1):
            if level==1:
                init+=1
                lab=LaboP1('bp35',1,'/Users/ts/models/chrysalide3/experiments/G/publics20c',out/'N1/partie')
            else: lab=labs[-1].next_level(out/f'N{level}/partie')
            labs.append(lab); z,j=charger_prefixe(name)
            for i,a in enumerate(j['actions'][:n]):
                im,film=lab.play(a,purpose='acces_support_occupe')
                if not np.array_equal(im,z['images'][i+1]) or not np.array_equal(film,z[f'film_{i+1}']): raise ValueError(f'Acces divergent niveau{level} coup{i+1}')
            if level<3 and not lab.won: raise ValueError('Acces non gagne')
        if 6 not in lab.actions_disponibles: raise ValueError('Clic indisponible')
        before=lab.image.copy()
        if not np.array_equal(before,target): raise ValueError('Etat cible different')
        im,film=lab.play(ACTION,purpose='sonde_support_expose_unique')
        result={'frames':len(film),'pixels_changes_hors_hud':int(np.sum(im[:-1]!=before[:-1])),'etat_sdk':lab.rows[-1]['state'],'niveaux':lab.rows[-1]['levels_completed'],'victoire_N3':lab.won,'positions_film':[]}
        for frame in film:
            try: result['positions_film'].append(m.position(frame))
            except (ValueError,IndexError): result['positions_film'].append(None)
        status='experience_terminee'
    except (ValueError,RuntimeError,IndexError,KeyError,TypeError) as exc: status='arret:'+repr(exc)
    finally:
        sauver(out/'comparaison.json',result)
        bilan={'statut':status,'coups_par_niveau':[len(l.rows) for l in labs],'coups_total':sum(len(l.rows) for l in labs),'initialisations':init,'resets':0,'sources_inchangees':all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in sources.items())}
        sauver(out/'bilan.json',bilan); print(json.dumps(bilan)); print(json.dumps(result))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--sortie',type=Path,required=True);ap.add_argument('--executer',action='store_true');a=ap.parse_args();main(a.sortie,a.executer)
