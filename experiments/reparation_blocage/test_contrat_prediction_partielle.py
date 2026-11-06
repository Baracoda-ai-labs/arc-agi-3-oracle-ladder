from pathlib import Path
import numpy as np
from contrat_prediction_partielle import contrat_relation, verifier
from relation_clic_observee import composantes


def donnees():
    p=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_trace40/partie.npz'
    with np.load(p) as z:
        return z['images'].copy()


def contrat(images):
    forme=next(f for c,f,x,y in composantes(images[1]) if (x,y)==(13,15))
    return contrat_relation({'action':['clic',27,15],'forme':list(map(list,forme)),
                             'sources':[[13,15],[19,15]],'destination':[25,15]})


def test_relation_exacte_ne_certifie_ni_navigation_ni_but():
    im=donnees();c=contrat(im);r=verifier(c,im[1],['clic',27,15],im[2])
    assert r['exact'] is True
    assert not r['modele_complet'] and not r['but_certifie']
    assert 'navigation' in r['abstentions'] and 'images_intermediaires' in r['abstentions']


def test_mouvement_reel_hors_perimetre_est_inconnu_pas_immobile():
    im=donnees();r=verifier(contrat(im),im[22],3,im[23])
    assert np.any(im[22,1:]!=im[23,1:])
    assert r['exact'] is None and r['raison']=='action_hors_perimetre'


def test_attribut_non_predit_ne_refute_pas_relation_mais_reste_inconnu():
    im=donnees();apres=im[2].copy();apres[35,32]=5
    r=verifier(contrat(im),im[1],['clic',27,15],apres)
    assert r['exact'] is True and not r['modele_complet']
    r=verifier(contrat(im),im[1],['clic',27,15],im[1])
    assert r['statut']=='refute_dans_perimetre'


def test_frontiere_victoire_ne_certifie_pas_un_but_partiel():
    im=donnees();r=verifier(contrat(im),im[1],['clic',27,15],im[2],'niveau')
    assert r['exact'] is None and not r['but_certifie']


def test_controleur_attache_et_verifie_le_contrat_sans_modifier_choix():
    from test_relation_clic_observee import trace,avancer_trace
    from relation_clic_observee import proposer_agent,actualiser
    a=trace(24);proposer_agent(a,[6]);avancer_trace(a,25)
    d=proposer_agent(a,[6])
    assert d['actions']==[['clic',42,18]]
    assert d['contrat_prediction_partielle']['but_certifie'] is False
    avancer_trace(a,26);actualiser(a)
    assert a.diagnostic_prediction_partielle['statut']=='confirme_partiellement'
    assert not a.diagnostic_prediction_partielle['modele_complet']
