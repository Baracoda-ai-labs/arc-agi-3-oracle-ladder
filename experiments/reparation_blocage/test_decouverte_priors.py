import json
from pathlib import Path
import numpy as np
from chaine_agent_integree import lots
from representation_legacy_sans_but import construire
from perception_marqueur_candidat import TrajectoireMarqueurCandidat

def test_presomptions_suspendues_et_controles_maintenus():
    p=Path(__file__).parent/'runs/publics_ref_g0/re86/N1/partie'
    z=np.load(p.with_suffix('.npz'))
    rows=json.loads(p.with_suffix('.json').read_text())['rows'][:8]
    h={'grilles':z['images'][:9],'lots':lots([r['action'] for r in rows])}
    c,r=construire(h,limite_s=2,trajectoire_factory=TrajectoireMarqueurCandidat,presence_prudente=True,prior_solide=False)
    th=c.perception.th_releve
    assert not th.murs_supposes and not th.moves_supposes
    assert not r['admis'] and not r['droit_action']
    assert r['controle']['catalogue_shacl'] and r['controle']['traduction_python']
