import json
from pathlib import Path
import numpy as np
from chaine_agent_integree import AgentIntegre
from representation_legacy_sans_but import construire
R=Path(__file__).parent

def entree():
    h=json.loads((R/'runs/legacy_effet_ft09_1/prefixe.json').read_text())
    return h,[['clic',x['actions'][0]['col'],x['actions'][0]['row']] for x in h['lots']]

def test_induction_sans_recherche_but(monkeypatch):
    from chrysalide.arc3.moteur import MoteurC
    def interdit(*args):raise AssertionError('chercheur de but appele')
    monkeypatch.setattr(MoteurC,'proposer',interdit)
    c,r=construire(entree()[0]);assert r['admis'] and r['controle']['transitions']==17
    assert c.perception.th_releve.but is None and r['droit_action'] is False

def test_decision_prospective_et_effet_tenu_a_part():
    h,a=entree();m=AgentIntegre(h['grilles'],a,h['films'],['continue']*len(a),legacy_sans_but=True,decouverte_courte=True)
    d=m.decider([6]);assert d['actions']==[['clic',37,37]] and d['but']=='absent_experience'
    held=json.loads((R/'runs/legacy_effet_ft09_1/reserve.json').read_text())[-1]
    c=m.chaines[d['modele_plan']];pred=np.array(d['predictions'][0][0]['image'])
    assert np.array_equal(pred,c.perception.vue(held['image']))

def test_flag_desactive_et_action_non_offerte():
    h,a=entree();old=AgentIntegre(h['grilles'],a,h['films'],['continue']*len(a));old.reconstruire()
    assert 'perception_sans_but_legacy' not in old.chaines
    new=AgentIntegre(h['grilles'],a,h['films'],['continue']*len(a),legacy_sans_but=True)
    assert not new.decider([])['actions']

def test_catalogue_refuse_bloque_admission(monkeypatch):
    from chaine_coherente import Chaine
    monkeypatch.setattr(Chaine,'catalogue',lambda _:False)
    h,a=entree();m=AgentIntegre(h['grilles'],a,h['films'],['continue']*len(a),legacy_sans_but=True)
    m.reconstruire();assert 'perception_sans_but_legacy' not in m.chaines
