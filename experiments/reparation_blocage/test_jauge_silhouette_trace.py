import json
from pathlib import Path
import numpy as np
from session_chaine_generique import nouvel_agent
from perception_silhouette_atlas import SilhouetteAtlas
from chaine_agent_integree import canon
from test_silhouette_atlas import TRACE


def test_prefixe_quatre_jauge_puis_commande_inedite_reservee(tmp_path):
    with np.load(TRACE) as z:
        gs=list(z['images'][:5]);films=[z[f'film_{k}'] for k in range(1,5)]
    v=SilhouetteAtlas(gs,[3,4,3,4])
    assert v.hud and any(r['admis'] for r in v.preuves_jauge)
    assert not v.contradictions_statiques
    a=nouvel_agent(gs,[3,4,3,4],films,['continue']*4);a.reconstruire()
    assert 'silhouette_atlas' in a.chaines
    c=a.chaines['silhouette_atlas'];check,(pc,sc)=c.rejouer()
    assert check['rejeu'] and check['compilation_fidele'] and c.but_inconnu
    assert np.array_equal(v.rendu(sc),v.vue(gs[-1]))
    # Le suffixe n'est ouvert qu'après construction/admission figées.
    with np.load(TRACE) as z:reserve=z['images'][5].copy()
    assert 7 not in v.lois
    pc.step(sc,canon(7))
    erreurs=np.argwhere(v.rendu(sc)!=v.vue(reserve)).tolist()
    rapport={'prefixe_actions':4,'suffixe_reserve':5,'commande_suffixe':7,'commande_couverte':False,
        'admission_prefixe':check,'jauge':v.preuves_jauge,'pixels_masques':len(v.hud),
        'prediction_sans_loi_ecarts_vue':len(erreurs),'differences':erreurs,
        'victoire':False,'source':'trace_1; campagne_1 metrique invalidee par harnais'}
    out=Path(__file__).parent/'runs/audit_jauge_silhouette_prefixe4_suffixe5';out.mkdir(exist_ok=True)
    (out/'rapport.json').write_text(json.dumps(rapport,indent=2,default=int))
    assert rapport['commande_couverte'] is False
