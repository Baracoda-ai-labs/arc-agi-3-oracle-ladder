import json
from pathlib import Path
import numpy as np
from session_chaine_generique import agent_prefixe


def test_prefixe_confronte_premier_coup_reel_sans_incident_atms():
    r=Path(__file__).parent
    a,_,_=agent_prefixe(r/'runs/legacy_effet_ft09_1/prefixe.json')
    p=r/'runs/session_ft09_buts_conserves1/N1/partie'
    rows=json.loads(p.with_suffix('.json').read_text())['rows']
    z=np.load(p.with_suffix('.npz'))
    d=a.decider([6],secondes=30)
    assert d['actions']==[rows[-1]['action']]
    o=a.observer(rows[-1]['action'],z['images'][-1],z['film_18'],'continue')
    assert o['coup']==18 and o['modeles_survivants']
    assert all(x['statut']=='transition_confirmee' for x in o['resultats'])
    assert a.attente is None
