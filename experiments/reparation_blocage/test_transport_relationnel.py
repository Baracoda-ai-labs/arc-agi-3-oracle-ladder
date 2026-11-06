from pathlib import Path
import numpy as np
from avancer_agent_relais import charger_agent
from relation_clic_observee import proposer_agent


def source():
 return charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_memoire_conjointe69/agent.pkl')


def test_transport_vers_interaction_et_verticalite_provisoire():
 a=source();d=proposer_agent(a,[1,2,3,4,6,7])
 assert d['origine']=='transport_vers_relation' and d['actions']==[2]
 assert d['support_cible']==[36,50]
 assert d['contrat_prediction_partielle']['position_candidate']==[54,20]
 assert d['contrat_prediction_partielle']['forme_candidate']==[55,21]
 assert not d['contrat_prediction_partielle']['but_certifie']


def test_deplacement_non_observe_ne_devient_pas_preuve():
 a=source();proposer_agent(a,[1,2,3,4,6,7]);a.actions.append(2);a.images.append(np.array(a.images[-1]).copy());a.issues.append('continue');a.films.append([a.images[-1]])
 from transport_relationnel import proposer
 assert proposer(a,[1,2,3,4,6,7]) is None
 assert a.memoire_mouvement_conjoint['navigation_a_revoir']
 assert not a.memoire_mouvement_conjoint.get('refutee',False)
 assert not a.memoire_mouvement_conjoint['but_certifie']
