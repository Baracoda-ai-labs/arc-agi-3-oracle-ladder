import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from arbitre_capacites_partielles import proposer_navigation


def agent_trace():
    p=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_trace40/partie'
    j=json.loads(p.with_suffix('.json').read_text())
    with np.load(p.with_suffix('.npz')) as z:
        return SimpleNamespace(actions=j['actions'],images=list(z['images'].copy()),
            films=[z[f'film_{i+1}'].copy() for i in range(40)],issues=['continue']*40)


def test_navigation_connue_contexte_nouveau_au_lieu_reduction_deja_vue():
    from relation_clic_observee import proposer_agent
    a=agent_trace();d=proposer_agent(a,[1,2,3,4,6,7])
    assert d['origine']=='arbitrage_capacites_coexistantes' and d['actions']==[2]
    c=d['contrat_prediction_partielle']
    assert c['position_avant']==[36,50] and c['position_candidate']==[36,56]
    assert 'garde_de_contact' in c['abstentions'] and not c['but_certifie']


def test_observation_inerte_comptee_pas_repetition_meme_sonde():
    a=agent_trace();a.actions.append(2);a.images.append(a.images[-1].copy())
    assert proposer_navigation(a,[2]) is None


def test_offre_et_abstention_sans_navigation_observee():
    a=agent_trace();assert proposer_navigation(a,[6,7]) is None
    a.images=a.images[:3];a.actions=a.actions[:2]
    assert proposer_navigation(a,[1,2,3,4]) is None


def test_meme_position_action_reouverte_si_contexte_change():
    a=agent_trace();a.actions.append(2);a.images.append(a.images[-1].copy())
    assert proposer_navigation(a,[2]) is None
    a.actions.append(['clic',10,10]);nouvelle=a.images[-1].copy();nouvelle[10,10]=14;a.images.append(nouvelle)
    assert proposer_navigation(a,[2])['actions']==[2]
