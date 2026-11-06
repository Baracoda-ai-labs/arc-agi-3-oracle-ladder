from pathlib import Path
import json,cloudpickle,numpy as np
from composition_contextes_objets import composer
from chaine_coherente import Chaine
from chaine_agent_integree import lots

R=Path(__file__).parent

def donnees():
    a=cloudpickle.loads((R/'runs/ar25_retour_apres_mouvement51/agent.pkl').read_bytes())
    p=next(iter(a.modeles_contextes_suspendus.values()))['chaine']
    alt=cloudpickle.loads((R/'runs/ar25_contexte_alternatif_archive22/candidat.pkl').read_bytes())
    commutations=[(a.images[45],a.actions[45],a.images[46],0),
                  (a.images[46],a.actions[46],a.images[47],1),
                  (a.images[49],a.actions[49],a.images[50],0)]
    return a,p,alt,commutations


def test_51_mouvement_et_52_retour_tenus_a_part():
    a,p,alt,trans=donnees();c,d=composer(p,alt,trans,a.images[45])
    assert c is not None,d
    test=Chaine(c.perception,c.programme,[g.tolist() for g in a.images[45:53]],lots(a.actions[45:52]),c.actions,films=a.films[45:52])
    check,state=test.rejouer()
    assert state is not None,check
    assert check['compilation_fidele'] and check['transitions']==7
    assert state[0].etat['contexte_actif']==0
    assert sum('niveau_suivant' in str(r) for r in c.programme['regles'])==1


def test_archive_alternative_et_retour_manquant_refuse():
    a,p,alt,trans=donnees()
    assert composer(p,alt,[trans[0]],a.images[45])[0] is None
    src=R/'runs/transfert_modele_commun_ar25_1/N2/partie';z=np.load(src.with_suffix('.npz'))
    rows=json.loads(src.with_suffix('.json').read_text())['rows']
    c,d=composer(p,alt,trans,z['images'][17],mode_initial=1)
    assert c is not None,d
    t=Chaine(c.perception,c.programme,[g.tolist() for g in z['images'][17:25]],lots([r['action'] for r in rows[17:24]]),c.actions)
    check,state=t.rejouer();assert state is not None,check
    assert check['compilation_fidele']
