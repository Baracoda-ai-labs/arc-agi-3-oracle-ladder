import json
from pathlib import Path
import numpy as np
from loi_orientation import prefixe
from retour_perception import reviser,decrire
R=Path(__file__).parent

def charger(base,n):
 z=np.load(str(base)+'.npz');j=json.loads(Path(str(base)+'.json').read_text())
 return (list(z['images'][:n+1]),[x['action'] for x in j['rows'][:n]],[z[f'film_{i+1}'] for i in range(n)])

def test_films_declenchent_retour_et_changent_description():
 base=R/'runs/transfert_commun_cd82_1/reel/N1/partie'
 fs=json.loads((R/'orientations_dc.json').read_text())['fonctions'];_,_,ids,_,_,_=prefixe(base,fs)
 episodes=[charger(base,4),charger(R/'runs/direction_revision_arc2/N1/partie',21)]
 r=reviser(episodes,ids)
 assert r['representation']=='relation_dirigee'
 assert r['journal'][0]['conflits'] and not r['journal'][1]['conflits']
 assert sum(map(len,r['exemples'].values()))==25
 assert not r['promotion_durable']

def test_description_qui_fusionne_les_etats_est_refusee():
 class Fausse:
  def voir(self,x):return {0:x}
 r=decrire([([0,1,0,2],[1,2,1],[[1],[0],[2]])],Fausse,[0])
 assert r['conflits'] and r['conflits'][0]['action']==1
