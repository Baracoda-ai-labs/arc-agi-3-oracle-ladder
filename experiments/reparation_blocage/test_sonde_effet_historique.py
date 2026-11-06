from pathlib import Path
from avancer_agent_relais import charger_agent
from perception_navigation_provisoire import construire
from relation_clic_observee import proposer_agent


def source():return charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n3_sondes1/agent.pkl')


def test_identites_multiples_et_question_sans_choisir_copie():
 a=source();v,p=construire(a.images,a.actions)
 assert len(v.mobiles)==2 and not p['selection_par_coordonnee']
 d=proposer_agent(a,[1,2,3,4,6,7])
 assert d['actions']==[7] and d['origine']=='experience_effet_historique'
 c=d['contrat_hypotheses'];assert c['cardinalite']==2 and c['historique']!=c['translation_constante']
 assert not c['annulation_certifiee'] and d['but']=='inconnu'


def test_n2_identite_unique_pas_regression_et_offre():
 a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_trace40/../lf52_n2_case_vide40/agent.pkl')
 v,p=construire(a.images[20:36],a.actions[20:35]);assert p['voie']=='identite_unique' and len(v.mobiles)==1
 from sonde_effet_historique import proposer
 assert proposer(source(),[1,2,3,4,6]) is None
