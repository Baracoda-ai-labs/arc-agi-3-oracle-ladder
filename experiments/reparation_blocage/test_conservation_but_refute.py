from pathlib import Path
import numpy as np
from avancer_agent_relais import charger_agent,decision_suivante

R=Path(__file__).parent/'runs'

def test_vrai_prefixe_conserve_regles_et_refute_but_sans_rejouer_sdk():
    a=charger_agent(R/'preflight_ka59_n3_transfert_26-10_1/agent.pkl')
    import copy,json
    source=copy.deepcopy(next(iter(a.chaines.values())).programme)
    rows=json.loads((R/'relais_ka59_contact1/N3/partie.json').read_text())['rows']
    with np.load(R/'relais_ka59_contact1/N3/partie.npz',allow_pickle=False) as z:
        for i in range(8):
            d=decision_suivante(a,[1,2,3,4,6]);assert d['actions']==[rows[i]['action']]
            o=a.observer(rows[i]['action'],z['images'][i+1],z[f'film_{i+1}'],'continue',source='trace')
    assert o['resultats'][0]['statut']=='but_refute'
    assert len(a.chaines)==1
    actif=next(iter(a.chaines.values()))
    assert actif.but_inconnu and not actif.refute
    assert actif.rejouer()[0]['transitions']==8
    assert not any(r.get('alors')==[['niveau_suivant']] for r in actif.programme['regles'])
    c=next(iter(a.modeles_but_refute.values()))
    assert c.programme==source and c.refute and c.plan is None
    assert len(c.lots)==8 and len(c.grilles)==9
    assert c.contre_exemples[-1]['statut']=='but_refute'
    assert c.contre_exemples[-1]['differences']==[]
