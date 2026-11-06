from pathlib import Path
from avancer_agent_relais import charger_agent
from sonde_commande_contextuelle import proposer

P=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n3_commun36/agent.pkl'

def test_contexte45_reouvre_commande_sans_direction_imposee():
    a=charger_agent(P);d=proposer(a,[1,2,3,4,6,7])
    assert d['actions']==[1] and 'direction' in d['abstentions']
    assert d['suivi']['images_non_resolues']==[32]
    assert not d['modeles']

def test_meme_contexte_inerte_non_reteste():
    a=charger_agent(P);a.actions.append(1);a.images.append(a.images[-1].copy())
    assert proposer(a,[1,2,3,4,6,7])['actions']==[2]
