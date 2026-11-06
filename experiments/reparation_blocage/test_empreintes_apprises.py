import json
from pathlib import Path
from loi_orientation import prefixe
from apprendre_empreintes import apprendre
R=Path(__file__).parent

def test_plan_induit_sans_region_ni_palette_fournie():
 base=R/'runs/transfert_commun_cd82_1/reel/N1/partie';fs=json.loads((R/'orientations_dc.json').read_text())['fonctions'];_,_,ids,_,_,_=prefixe(base,fs)
 r,plan=apprendre([base,R/'runs/session_perception_arc1/N1/partie'],ids)
 assert not r['erreurs'] and r['modeles_visuels_candidats']>=1 and plan
 assert len(r['prediction_prochain_coup']['canvas'])>0
 assert r['etat_observe']!=r['prediction_prochain_coup']
 assert r['selecteurs']
