from pathlib import Path
from avancer_agent_relais import charger_agent
from referentiel_visible import estimer

def test_reemploi_estimateur_vertical_sur_translation_horizontale():
    a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n3_heritage29/agent.pkl')
    r=estimer(a.images[-2],a.images[-1],{11,12,14})
    assert r['translation']==[-8,0] and r['retenu']
    assert not r['camera_certifiee']
    assert estimer(a.images[-1],a.images[-1],{11,12,14})['translation']==[0,0]
