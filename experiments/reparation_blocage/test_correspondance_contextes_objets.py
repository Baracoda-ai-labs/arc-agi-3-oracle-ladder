from pathlib import Path
import copy,cloudpickle,numpy as np
from correspondance_contextes_objets import apprendre,reaffecter_observation

R=Path(__file__).parent

def donnees():
    a=cloudpickle.loads((R/'runs/ar25_retour_apres_mouvement51/agent.pkl').read_bytes())
    principal=next(iter(a.modeles_contextes_suspendus.values()))['chaine']
    alt=cloudpickle.loads((R/'runs/ar25_contexte_alternatif_archive22/candidat.pkl').read_bytes())
    return a,principal,alt


def test_mapping_puis_image52_tenue_a_part_programme_identique():
    a,p,alt=donnees();programme=copy.deepcopy(p.programme)
    mapping,diag=apprendre(p,alt,[(a.images[45],a.images[46]),(a.images[49],a.images[50])])
    assert diag['admis'] and not diag['commutation_dynamique_apprise']
    assert dict(mapping)[('mobile',0)]==('mobile',1)
    assert dict(mapping)[('mobile',1)]==('statique',1)
    assert dict(mapping)[('statique',1)]==('mobile',0)
    c,d=reaffecter_observation(p,a.images[52])
    assert d['admis'] and d['programme_identique'] and d['garde_commune_conservee']
    assert c.programme==programme and p.programme==programme
    assert d['but_conserve'] and d['calques']==len(p.perception.points)
    assert c.perception.base.statiques[1]['x']!=p.perception.base.statiques[1]['x']
    assert np.array_equal(c.perception.rendu(c.rejouer()[1][1]),c.perception.vue(a.images[52]))


def test_paire_avec_mouvement_ou_pixel_nouveau_refusee():
    a,p,alt=donnees()
    assert apprendre(p,alt,[(a.images[49],a.images[51])])[0] is None
    faux=a.images[52].copy();faux[10,10]=2
    assert reaffecter_observation(p,faux)[0] is None
