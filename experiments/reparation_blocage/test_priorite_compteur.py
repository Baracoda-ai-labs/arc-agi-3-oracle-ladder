"""Heuristique seule : le compteur reste dans la clé intégrale et les images."""
import copy
from types import SimpleNamespace
import numpy as np
from exploration_p1_prefixe import priorite_compteur


def exemple():
    images=[]
    for i in range(10):
        g=np.zeros((16,24),dtype=int);g[0,i:]=2;g[7:10,8:11]=4;images.append(g)
    episode={'grilles':images,'actions':[1]*9,'issues':['continue']*9}
    ex=SimpleNamespace(cle=lambda g:np.asarray(g).tobytes(),aretes={},
        candidats=lambda g:[1,2],priorite=lambda a,g:2-a)
    return ex,episode


def test_repetition_reordonne_sans_changer_graphe_ni_observations():
    ex,e=exemple();avant=[g.copy() for g in e['grilles']];graphe=copy.deepcopy(ex.aretes)
    a,raison,d=priorite_compteur(ex,[e],e['grilles'][-1],[1,2],1,'exploration_nouvelle')
    assert a==2 and d['decision_changee'] and d['cellules_compteur_hypothese']>0
    assert not d['preuve_inertie'] and d['films_intermediaires_non_evalues']
    assert ex.aretes==graphe and all(np.array_equal(a,b) for a,b in zip(avant,e['grilles']))
    assert ex.cle(e['grilles'][0])!=ex.cle(e['grilles'][-1])


def test_masque_vide_et_chemin_et_risque_conservent_choix():
    ex,e=exemple()
    court={k:v[:2] if k=='grilles' else v[:1] for k,v in e.items()}
    assert priorite_compteur(ex,[court],court['grilles'][-1],[1,2],1,'exploration_nouvelle')[0]==1
    assert priorite_compteur(ex,[e],e['grilles'][-1],[1,2],1,'vers_meilleure_frontiere')[0]==1
    assert priorite_compteur(ex,[e],e['grilles'][-1],[1,2],1,'exploration_nouvelle',{2})[0]==1
    ex.aretes[ex.cle(e['grilles'][-1])]={2:'mort'}
    assert priorite_compteur(ex,[e],e['grilles'][-1],[1,2],1,'exploration_nouvelle')[0]==1


def test_cycle_deux_vues_penalise_repetition_malgre_effet():
    ex,e=exemple()
    for i,g in enumerate(e['grilles']):
        g[7:10,8:11]=4 if i%2==0 else 5
    e['actions']=[1 if i%2==0 else 2 for i in range(9)]
    ex.candidats=lambda im:[1,2,3]
    ex.priorite=lambda a,im:3-a
    avant=[g.copy() for g in e['grilles']]
    a,raison,d=priorite_compteur(ex,[e],e['grilles'][-1],[1,2,3],2,'exploration_nouvelle')
    assert a!=2 and d['decision_changee']
    assert d['repetitions_choix_initial']==4 and d['repetitions_choix_final']==0
    assert not d['preuve_inertie'] and not ex.aretes
    assert all(np.array_equal(a,b) for a,b in zip(avant,e['grilles']))
