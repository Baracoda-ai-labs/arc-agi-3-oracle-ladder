from pathlib import Path
from avancer_agent_relais import charger_agent
from arbitre_capacites_partielles import proposer_navigation

def test_compteur_changeant_ne_priorise_pas_toujours_la_meme_commande():
    a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_commun54/agent.pkl')
    avant=a.images[-1].copy();d=proposer_navigation(a,[1,2,3,4,6,7])
    assert d['origine']=='arbitrage_capacites_coexistantes'
    assert d['actions']==[2]
    assert d['preuve']['repetitions_position_action']==0
    assert d['preuve']['contexte_integral_pour_exclusion']
    assert (a.images[-1]==avant).all()
    assert not d['contrat_prediction_partielle']['but_certifie']

def test_repetition_reste_possible_si_seule_commande_offerte():
    a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_commun54/agent.pkl')
    d=proposer_navigation(a,[1])
    assert d['actions']==[1] and d['preuve']['repetitions_position_action']>=8
