"""Raccord du pilote et contrat décision/observation ; archive réelle, aucun SDK."""
import copy
import numpy as np
import pytest
from test_revision_solidite import cas
from session_chaine_generique import nouvel_agent


def test_activation_par_le_pilote_et_defaut_off(monkeypatch):
    monkeypatch.delenv('CHRYS_BOUCLE_AGENT',raising=False)
    assert not nouvel_agent([np.zeros((64,64),int)],[],[],[]).boucle_reparation
    monkeypatch.setenv('CHRYS_BOUCLE_AGENT','1')
    monkeypatch.setenv('CHRYS_BOUCLE_AGENT_SONDES','2')
    a=nouvel_agent([np.zeros((64,64),int)],[],[],[])
    assert a.boucle_reparation and a.budget_sondes_reparation==2


def test_experience_attend_observation_et_budget_borne(monkeypatch):
    monkeypatch.delenv('CHRYS_SONDE_REVISION_PRIORITAIRE',raising=False)
    a,_,_=cas()
    a.boucle_reparation=True
    a.budget_sondes_reparation=1
    a.sondes_reparation_emises=0
    r=a.decider([1,2,3,4],secondes=30)
    assert r['origine']=='consequence_revision' and r['predictions'][0]
    assert r['prefixe_sha256'] and a.attente is r
    assert a.journal[-1]['type']=='boucle_reparation_decision'
    with pytest.raises(ValueError,match='Observation requise'):
        a.decider([1,2,3,4],secondes=30)
    assert a.sondes_reparation_emises==1
    # Une réponse SIMULÉE exerce observer, pas une victoire/expérience ARC.
    pred=next(p for p in r['predictions'][0] if p['nom']==r['modele_revision'])
    image=np.asarray(pred['image'])
    a.observer(r['actions'][0],image,np.asarray([image]),'continue')
    assert a.attente is None
    assert r['question_revision'] in a.sondes_revision_resolues
    assert a._sonder_revision([1,2,3,4]) is None
