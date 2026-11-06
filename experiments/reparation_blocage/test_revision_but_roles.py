import copy
from pathlib import Path
import cloudpickle
import numpy as np
from chaine_coherente import Chaine
from chaine_agent_integree import lots, canon
from revision_but_roles import proposer

R = Path(__file__).parent/'runs'

def source_observee():
    a = cloudpickle.loads((R/'preflight_ka59_n3_transfert_26-10_1/agent.pkl').read_bytes())
    b = cloudpickle.loads((R/'ka59_n3_controleur_fige1/agent.pkl').read_bytes())
    c = copy.deepcopy(next(iter(a.chaines.values())))
    for i, action in enumerate(b.actions):
        c.plan = {'actions': [list(canon(action))], **c.signature()}
        r = c.observer(canon(action), b.images[i+1], film=b.films[i])
        assert r['image_exacte']
    assert r['statut'] == 'but_refute'
    return c

def test_but_revoque_dynamique_et_historique_conserves():
    c = source_observee()
    avant = copy.deepcopy(c.programme)
    new, d = proposer(c)
    assert new is not None and d['admis']
    assert d['controle']['transitions'] == 8 and d['controle']['compilation_fidele']
    assert new.programme['regles'] == [r for r in avant['regles'] if r['nom'] != 'toutes_cibles_hypothese']
    assert c.programme == avant and c.refute
    assert new.grilles == c.grilles and new.lots == c.lots
    assert new.perception.signature_observation() == c.perception.signature_observation()
    assert new.but_inconnu and new.plan is None and not d['candidats_buts_admis']
    assert any(h['non_couverts'] and not h['pieces_actuelles_de_meme_forme'] for h in d['couverture_hypotheses'])

def test_ecart_physique_interdit_reparation_du_but_seul():
    c = source_observee()
    c.contre_exemples[-1]['differences'] = [{'x': 1, 'y': 1}]
    assert proposer(c)[0] is None

def test_but_absent_ou_autre_effet_refuse():
    c = source_observee()
    next(r for r in c.programme['regles'] if r['nom']=='toutes_cibles_hypothese')['alors'].append(['niveau_suivant'])
    assert proposer(c)[0] is None
