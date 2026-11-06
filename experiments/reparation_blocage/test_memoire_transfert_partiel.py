from types import SimpleNamespace
import copy
import numpy as np
import pytest
from memoire_observations import episode_observe,ajouter_episode
from memoire_transfert_partiel import conserver


def episode(gain=True):
 return SimpleNamespace(images=[np.zeros((2,2),dtype=int),np.ones((2,2),dtype=int),np.full((2,2),9)],
   actions=[1,2],issues=['continue','niveau' if gain else 'continue'],films=[[np.ones((2,2))],[np.full((2,2),2),np.full((2,2),9)]],observations_episodes=[])


def test_banque_lineaire_conserve_nonvictoires_et_frontiere_sans_but():
 a=episode();n1=episode_observe(*[getattr(a,k) for k in ('images','actions','issues')],a.films)
 a.images=[x+3 for x in a.images];a.observations_episodes=[n1]
 b=SimpleNamespace(journal=[]);conserver(a,b);conserver(a,b)
 assert len(b.observations_episodes)==2
 ep=b.observations_episodes[-1];p=ep['provenance']
 assert p['transitions_non_victorieuses']==[1] and p['transition_victorieuse']==2
 assert p['image_post_transition_utilisable_comme_but'] is False and p['but_certifie'] is False
 assert len(ep['films'][-1])==2 and np.array_equal(ep['grilles'][-1],a.images[-1])
 assert 'observations_episodes' not in ep
 ep['grilles'][0][0,0]=99
 assert a.images[0][0,0]!=99


def test_provenance_tronquee_ou_modifiee_refusee():
 a=episode();b=SimpleNamespace(journal=[]);conserver(a,b);ep=copy.deepcopy(b.observations_episodes[0]);ep['films'][-1].pop()
 with pytest.raises(ValueError,match='Empreinte'):ajouter_episode(SimpleNamespace(),ep)
 a.images.pop()
 with pytest.raises(ValueError,match='aligne'):conserver(a,SimpleNamespace(journal=[]))


def test_frontiere_interne_et_absence_victoire_refusees():
 a=episode(False)
 with pytest.raises(ValueError,match='Victoire'):conserver(a,SimpleNamespace(journal=[]))
 a=episode();a.issues[0]='niveau'
 with pytest.raises(ValueError,match='frontiere'):conserver(a,SimpleNamespace(journal=[]))


def test_capacite_transport_reste_accessible_sans_activer_identite_ancienne():
 a=episode();a.memoire_mouvement_conjoint={'decalage':[1,1],'but_certifie':False}
 b=SimpleNamespace(journal=[]);sha=conserver(a,b);conserver(a,b)
 assert len(b.hypotheses_capacites_heritees)==1
 h=b.hypotheses_capacites_heritees[0]
 assert h['episode_source_sha256']==sha and not h['active'] and not h['but_certifie']
 assert not hasattr(b,'memoire_mouvement_conjoint')
 h['hypothese']['decalage'][0]=9
 assert a.memoire_mouvement_conjoint['decalage']==[1,1]
