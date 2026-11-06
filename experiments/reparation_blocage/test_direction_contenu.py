import json
from pathlib import Path
import numpy as np
from retour_perception import charger,reviser,decrire
from loi_orientation import prefixe
from direction_contenu import DirectionContenu
R=Path(__file__).parent

def test_reacquisition_sur_contact_et_palette():
 base=R/'runs/transfert_commun_cd82_1/reel/N1/partie';fs=json.loads((R/'orientations_dc.json').read_text())['fonctions'];_,_,ids,_,_,_=prefixe(base,fs)
 eps=[charger(base,4),charger(R/'runs/session_perception_arc1/N1/partie',37)]
 r=reviser(eps,ids);assert r['representation']=='contenu_dans_contour' and not r['journal'][-1]['conflits'] and not r['journal'][-1]['manquants']
 # Bijection des couleurs : la relation ne dépend d'aucun numéro de palette.
 mapping=np.arange(16)[::-1]
 es=[([mapping[x] for x in ims],acts,[[mapping[x] for x in film] for film in films]) for ims,acts,films in eps]
 q=decrire(es,lambda:DirectionContenu(ids),[0]);assert q['exemples']==r['exemples']
