import copy
import json
from pathlib import Path

import cloudpickle
import numpy as np

from chaine_agent_integree import AgentIntegre, canon
from transfert_modele_c import reaffecter

R = Path(__file__).parent


def cas():
    p = R/'runs/session_re86_transfert_c1/N2/partie'
    z = np.load(p.with_suffix('.npz'))
    rows = json.loads(p.with_suffix('.json').read_text())['rows']
    s = cloudpickle.loads((R/'runs/session_re86_buts_conserves1/modele_gagnant_local.pkl').read_bytes())
    c, _ = reaffecter(s, z['images'][0], [canon(k) for k in (1,2,3,4,5)])
    a = AgentIntegre([z['images'][0]], [], [], [], revision_projection=True,
                    exploration_p1=True, limite=200)
    a.chaines = {'transfert': c}
    a.reconstruction = False
    a.releves_p1 = {0}
    return a, z, rows


def observer_archive(a, z, rows, i):
    action = rows[i]['action']
    d = {'actions':[action], 'predictions':[[]]}
    a._suivre_experience(d)
    a.attente = d
    return a.observer(action, z['images'][i+1], z[f'film_{i+1}'], 'continue')


def test_revision_automatique_prefixe_et_sonde_suivante():
    a,z,rows = cas()
    avant = copy.deepcopy(a.chaines['transfert'].perception.th_releve)
    observer_archive(a,z,rows,0)
    c = a.chaines['transfert/projection_selection']
    assert c.rejouer()[1] is not None
    assert len(c.lots) == len(a.actions) == c.coups == 1
    assert c.grilles == [g.tolist() for g in a.images]
    assert c.perception.th_releve.moves == avant.moves
    assert c.perception.th_releve.porteur == avant.porteur
    d = a.decider([1,2,3,4,5], secondes=2)
    assert d['actions'] and d['actions'][0] in (1,2,3,4)
    assert d['origine'] == 'consequence_revision'


def test_suffixe_images_fige_limite_aux_selections():
    a,z,rows = cas()
    observer_archive(a,z,rows,0)
    c = a.chaines['transfert/projection_selection']
    _,(pc,scene) = c.rejouer()
    for i in range(1,len(rows)):
        assert rows[i]['action'] == 5
        pc.step(scene,canon(rows[i]['action']))
        assert np.array_equal(c.perception.rendu(scene),c.perception.vue(z['images'][i+1]))
    assert scene.issue is None and 'GAME_OVER' in rows[-1]['state']


def test_historique_plus_long_non_tronque(monkeypatch):
    import revision_perception_selection
    import revision_solidite
    import chaine_agent_integree
    a,z,rows = cas()
    observer_archive(a,z,rows,0)
    c = a.chaines['transfert/projection_selection']
    avant = len(c.grilles)
    monkeypatch.setattr(revision_perception_selection,'reviser',lambda *x,**kw:
        (_ for _ in ()).throw(AssertionError('Ne pas réviser seulement le dernier couple')))
    monkeypatch.setattr(revision_solidite,'proposer',lambda *x,**kw:([],{}))
    monkeypatch.setattr(chaine_agent_integree,'proposer_calques',lambda *x,**kw:([],{}))
    faux = z['images'][2].copy()
    faux[0,0] = (int(faux[0,0])+1)%16
    d = {'actions':[5], 'predictions':[[]]}
    a._suivre_experience(d);a.attente=d
    a.observer(5,faux,[faux],'continue')
    assert len(c.grilles) == avant+1 and len(c.lots) == 2
    assert any(e['type']=='revision_perception_selection_limitee' for e in a.journal)
