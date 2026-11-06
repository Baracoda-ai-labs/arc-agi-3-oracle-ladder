from test_routage_classes import charger
from chaine_coherente import Chaine

def test_refus_continue_sans_supprimer_hypotheses(monkeypatch):
 a=charger('m0r0',False);a.recherche_briques='dreamcoder';appels=[]
 def refuser(c,**kw):
  appels.append(c)
  return {'statut':'aucun_plan'}
 monkeypatch.setattr(Chaine,'proposer',refuser)
 a.decider([1,2,3,4,6])
 attendus=[c for n,c in a.chaines.items() if not n.startswith('perception_sans_but')]
 assert len(appels)==len(attendus)>1
 assert set(map(id,appels))==set(map(id,attendus))

def test_premier_plan_verifie():
 a=charger('m0r0',False);a.recherche_briques='dreamcoder'
 d=a.decider([1,2,3,4,6])
 assert d['actions']==[1]
 assert all(p['issue']!='defaite' for p in d['predictions'][0])
 r=[x for x in a.journal if x['type']=='recherche_briques'][-1]
 assert len(r['modeles_explores'])==1 and len(a.chaines)>1
