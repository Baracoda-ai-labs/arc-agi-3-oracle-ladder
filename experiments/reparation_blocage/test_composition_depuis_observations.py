from pathlib import Path
import cloudpickle
from composition_depuis_observations import proposer_composition

R=Path(__file__).parent

def donnees():
    a=cloudpickle.loads((R/'runs/ar25_memoire_episodes52_1/agent.pkl').read_bytes())
    p=next(iter(a.modeles_contextes_suspendus.values()))['chaine']
    alt=cloudpickle.loads((R/'runs/ar25_contexte_alternatif_archive22/candidat.pkl').read_bytes())
    return a,p,alt


def test_fenetre_fournie_selection_et_suffixe_independants():
    a,p,alt=donnees();images_avant=cloudpickle.dumps(a.images)
    c,d=proposer_composition(p,alt,a.images[45:],a.actions[45:],a.issues[45:],a.films[45:])
    assert c is not None,d
    assert d['fin_apprentissage']==2
    assert d['suffixe_validation']==[3,7]
    assert d['controle']['compilation_fidele'] and d['mode_courant']==0
    assert [x['transition'] for x in d['commutations']]==[1,2]
    assert c.grilles[-1]==a.images[-1].tolist()
    assert cloudpickle.dumps(a.images)==images_avant


def test_retour_manquant_et_suffixe_faux_refuses():
    a,p,alt=donnees()
    assert proposer_composition(p,alt,a.images[:4],a.actions[:3],secondes=5)[0] is None
    images=[g.copy() for g in a.images];images[-1][10,10]=2
    c,d=proposer_composition(p,alt,images,a.actions,a.issues,a.films)
    assert c is None and d['refus']=='suffixe_refute'
    issues=list(a.issues);issues[5]='defaite'
    assert proposer_composition(p,alt,a.images,a.actions,issues,a.films)[0] is None


def test_historique_complet_refuse_ancien_contreexemple_sans_redecouper():
    a,p,alt=donnees()
    c,d=proposer_composition(p,alt,a.images,a.actions,a.issues,a.films)
    assert c is None and d['refus']=='suffixe_refute' and d['refus_blocant']
    assert [x['transition'] for x in d['commutations']]==[3,28]
    assert d['fin_apprentissage']==28 and d['transition_divergence']==42
