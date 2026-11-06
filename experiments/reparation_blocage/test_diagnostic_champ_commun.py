from diagnostic_champ_commun import comparer,reexaminer
from pathlib import Path
from avancer_agent_relais import charger_agent
import copy


def test_entree_champ_ne_valide_pas_population_totale():
    r=comparer([[36,60],[48,24]],[[6,60],[18,24],[48,24]],[(0,0),(3,3)],(64,64),[-30,0])
    assert r['compatible'] and not r['population_totale_verifiee']
    assert r['hors_champ_precedent']==[[48,24]]


def test_divergence_locale_reste_refutee():
    r=comparer([[36,60],[48,24]],[[6,60],[19,24],[48,24]],[(0,0),(3,3)],(64,64),[-30,0])
    assert not r['compatible']


def test_archive_reouverture_conditionnelle_sans_effacer_echec():
    p=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n4_transport16/agent.pkl'
    a=charger_agent(p);m=copy.deepcopy(a.memoire_relation_clic);v=copy.deepcopy(m['validations_prospectives'])
    assert reexaminer(a,m)
    assert not m['refutee'] and not m['population_totale_verifiee']
    assert m['validations_prospectives']==v
    assert a.diagnostics_champ_commun[-1]['diagnostic_ecran']['exact'] is False
