from pathlib import Path
import cloudpickle,json,numpy as np
from tester_experience_contexte_relais import preparer_prediction
from chaine_agent_integree import canon


def test_prediction_prospective_puis_observation_sdk_archivee():
    b=Path(__file__).parent/'runs'
    c=cloudpickle.loads((b/'ar25_experience_alternative49_reel1/candidat_apres.pkl').read_bytes())
    ds=json.loads((b/'ar25_experience_alternative49_reel1/experience.json').read_text())
    d=ds[-1]['decision'];z=np.load(b/'relais_ar25_memoire_continue1/N2/partie.npz')
    # La prédiction a été enregistrée avant le vrai coup51 ; le harnais avait omis le plan.
    assert np.array_equal(c.perception.vue(z['images'][51]),np.array(d['choix']['prediction_image']))
    preparer_prediction(c,d['actions'][0])
    r=c.observer(canon(d['actions'][0]),z['images'][51],source='trace',film=z['film_51'])
    assert r['statut']=='transition_confirmee' and r['pixels_ecart']==0
