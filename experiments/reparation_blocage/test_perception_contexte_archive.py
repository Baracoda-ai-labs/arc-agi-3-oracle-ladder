from pathlib import Path
import json,numpy as np
from perception_contexte_archive import proposer
from chaine_agent_integree import canon

R=Path(__file__).parent/'runs/transfert_modele_commun_ar25_1/N2/partie'

def data():
    z=np.load(R.with_suffix('.npz'));rows=json.loads(R.with_suffix('.json').read_text())['rows']
    return z,rows


def test_prefixe_et_suffixe_separes_masque_anterieur():
    z,rows=data();passe=list(z['images'][:18]);images=list(z['images'][17:23])
    c,d=proposer(passe,images,[r['action'] for r in rows[17:22]])
    assert d['admis'] and d['transitions_masque']==17 and not d['but_appris']
    assert (15,63) in c.perception.hud
    assert not any(r['alors']==[['niveau_suivant']] for r in c.programme['regles'])
    check,(pc,sc)=c.rejouer();assert check['transitions']==5 and check['compilation_fidele']
    for k in [22,23]:
        pc.step(sc,canon(rows[k]['action']))
        assert np.array_equal(c.perception.rendu(sc),c.perception.vue(z['images'][k+1]))


def test_pas_de_masque_depuis_futur_ni_effet_cache():
    z,rows=data();images=list(z['images'][17:23]);actions=[r['action'] for r in rows[17:22]]
    assert proposer([z['images'][17]],images,actions)[0] is None
    assert proposer(list(z['images'][:17]),images,actions)[0] is None
    images=[g.copy() for g in images];images[-1][10:12,10:12]=2
    assert proposer(list(z['images'][:18]),images,actions)[0] is None
