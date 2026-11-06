from pathlib import Path
import cloudpickle,json,numpy as np
from experience_contexte_alternatif import proposer_experience

R=Path(__file__).parent

def donnees():
    a=cloudpickle.loads((R/'runs/ar25_contexte37_restaure1/agent.pkl').read_bytes())
    alt=cloudpickle.loads((R/'runs/ar25_contexte_alternatif_archive22/candidat.pkl').read_bytes())
    p=R/'runs/transfert_modele_commun_ar25_1/N2/partie'
    z=np.load(p.with_suffix('.npz'));rows=json.loads(p.with_suffix('.json').read_text())['rows']
    return a,next(iter(a.chaines.values())),alt,[(list(z['images']),[r['action'] for r in rows])]


def test_acces49_attend_vraie_image_et_ne_predis_pas_switch():
    a,p,alt,archives=donnees();r=proposer_experience(p,alt,a.images,a.actions,list(range(1,8)),archives)
    assert r['statut']=='acces_contexte_observe' and r['actions']==[5]
    assert r['prediction_image'] is None and r['suite'].startswith('attendre_image_reelle')
    assert not proposer_experience(p,alt,a.images,a.actions,[1,2,3,4],archives)['actions']


def test_image46_observee_discriminante_et_inedite():
    a,p,alt,archives=donnees();images=a.images[:47];actions=a.actions[:46]
    r=proposer_experience(p,alt,images,actions,list(range(1,8)),archives)
    assert r['statut']=='experience_contexte_alternatif'
    assert r['choix']['pixels_modifies_alternatif']>0 and r['choix']['pixels_contraste_effets']>0
    assert r['actions'][0] in [3,4]
    # Une transition déjà observée au même état ne doit pas être reproposée.
    ancien=(images+[np.asarray(r['choix']['prediction_image'])],actions+r['actions'])
    offre=r['actions']
    assert not proposer_experience(p,alt,images,actions,offre,archives+[ancien])['actions']


def test_refuse_image_non_admissible_et_reference_absente():
    a,p,alt,archives=donnees()
    assert not proposer_experience(p,alt,a.images[:43],a.actions[:42],list(range(1,8)),archives)['actions']
    assert not proposer_experience(p,alt,[a.images[46]],[],list(range(1,8)),[])['actions']
