import copy,json
from pathlib import Path
from test_routage_classes import charger
from dreamcoder_mots import appliquer,taille_arbre
R=Path(__file__).parent

def test_heldout_expansion_rejeu_compilation_decision():
 off=charger('m0r0',False);d0=off.decider([1,2,3,4,6])
 on=charger('m0r0',False);on.dreamcoder_mots=True;d1=on.decider([1,2,3,4,6])
 assert d0['actions']==d1['actions']
 assert set(off.chaines)==set(on.chaines)
 used=[]
 for n,c in on.chaines.items():
  check,state=c.rejouer()
  assert state is not None and all(check.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele'))
  assert c.programme['mots'];used.extend(c.programme['mots'])
  # Predictions on each offered direction compare real executable macros, not expansions.
  from chaine_agent_integree import canon
  for a in (1,2,3,4):
   assert on._predire(c,canon(a))==off._predire(off.chaines[n],canon(a))
 assert len(set(used))>=1
 print('HELDOUT',len(on.chaines),'models',len(set(used)),'macros')

def test_hygiene_collision_et_evaluation_paresseuse():
 import pytest
 b=json.load(open(R/'dreamcoder_bibliotheque.json'))
 a=charger('m0r0',False);a.reconstruire();p=next(iter(a.chaines.values())).programme
 q,preuve=appliquer(p,b);assert preuve['expansion_exacte'] and preuve['noeuds_apres']<preuve['noeuds_avant']
 collision=copy.deepcopy(p);collision['mots']={next(iter(b['mots'])):{'params':[],'corps':True}}
 with pytest.raises(ValueError):appliquer(collision,b)
 from dreamcoder_mots import correspond
 assert not correspond('$dc0',['elem',[],1],['$dc0'],{})
 # Alpha-renaming external object variable preserves matching without capturing another variable.
 from dreamcoder_mots import substituer
 renamed=substituer(p,{'$o':'$renomme'})
 _,proof=appliquer(renamed,b);assert proof['expansion_exacte'] and proof['mots_utilises']
