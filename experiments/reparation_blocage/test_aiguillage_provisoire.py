import json
from pathlib import Path
import numpy as np
from chaine_agent_integree import AgentIntegre

def test_alternatives_et_sonde_malgre_premiere_admission(monkeypatch):
    import perception_routee
    p=Path(__file__).parent/'runs/re86_ancre_reel_1/N1/partie'
    z=np.load(p.with_suffix('.npz'))
    rows=json.loads(p.with_suffix('.json').read_text())['rows']
    calls=[]
    original=perception_routee.proposer
    def observe(description,historique,toutes=False):
        calls.append(toutes)
        return original(description,historique,toutes=toutes)
    monkeypatch.setattr(perception_routee,'proposer',observe)
    a=AgentIntegre(list(z['images'][:9]),[r['action'] for r in rows[:8]],
        [z[f'film_{i+1}'] for i in range(8)],['continue']*8,
        legacy_sans_but=True,exploration_p1=True,aiguillage_provisoire=True)
    a.reconstruire()
    assert calls==[True]
    assert not a.capacites_differees
    route=next(x for x in a.journal if x['type']=='routage_ontologie')
    assert route['voie_inconnue']=='p1_graphe_observe'
    assert not route['exclusion_par_priorite']
    assert any(x['type']=='representation_legacy' for x in a.journal)
    decision={'actions':[rows[8]['action']]}
    a._suivre_experience(decision)
    assert decision['modeles']
    a.attente=decision
    observation=a.observer(rows[8]['action'],z['images'][9],z['film_9'],'continue')
    assert observation['resultats']
    assert a.attente is None

def test_calques_refuse_contrat_absent():
    from perception_guidee import proposer_calques
    candidats, diagnostic=proposer_calques(object(),None,[],[])
    assert not candidats
    assert 'mobiles' in diagnostic['capacites_manquantes']
    assert diagnostic['retour']=='perception'

def test_incident_reel_coup11_rejoue_sans_sdk():
    p=Path(__file__).parent/'runs/re86_aiguillage_reel_1/N1/partie'
    z=np.load(p.with_suffix('.npz'))
    rows=json.loads(p.with_suffix('.json').read_text())['rows']
    a=AgentIntegre(list(z['images'][:9]),[r['action'] for r in rows[:8]],
        [z[f'film_{i+1}'] for i in range(8)],['continue']*8,
        legacy_sans_but=True,exploration_p1=True,aiguillage_provisoire=True)
    for i in range(8,11):
        if a.reconstruction:a.reconstruire()
        d={'actions':[rows[i]['action']], 'predictions':[[]]}
        a._suivre_experience(d)
        a.attente=d
        a.observer(rows[i]['action'],z['images'][i+1],z[f'film_{i+1}'],'continue')
    assert a.reconstruction
    assert any(x['type']=='revision_calques' and
               x['diagnostic'].get('capacites_manquantes') for x in a.journal)
