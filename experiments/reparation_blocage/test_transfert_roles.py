import copy
from pathlib import Path
import cloudpickle
import numpy as np
import pytest
from transfert_roles import reaffecter,RolesReaffectes
from chaine_coherente import Chaine
from chaine_agent_integree import canon
from chrysalide.arc3.langage import Programme

@pytest.fixture(scope='module')
def archive():
    return cloudpickle.loads((Path(__file__).parent/'runs/ka59_controleur_corrige72_1/agent.pkl').read_bytes())

def test_n1_equivalence_mouvement_marqueurs_faces_freinage_et_victoire(archive):
    source=archive.modele_gagnant
    c,d=reaffecter(source,source.grilles[0],[])
    ancien=copy.deepcopy(source.programme)
    replay=Chaine(c.perception,c.programme,source.grilles,source.lots,[],
                 films=[e['images'] if e else None for e in source.films.entrees])
    check,cur=replay.rejouer()
    assert cur and check['transitions']==80 and check['compilation_fidele']
    _,original=source.rejouer()
    for courant in (cur,original):courant[0].step(courant[1],canon(archive.actions[-1]))
    assert cur[1].issue==original[1].issue=='niveau'
    assert np.array_equal(c.perception.rendu(cur[1]),source.perception.rendu(original[1]))
    assert source.programme==ancien

def test_n2_couverture_complete_et_dispatch(archive):
    from session_chaine_generique import agent_transfere
    source=archive.modele_gagnant
    programme=copy.deepcopy(source.programme)
    perception=copy.deepcopy(source.perception.signature_observation())
    nouveau=agent_transfere(archive,archive.images[-1],[1,2,3,4,6])
    preuve=next(e for e in reversed(archive.journal) if e['type']=='memoire_issue_observee')
    confirmes={e['nom'] for e in preuve['candidats'] if e['but_confirme_par_prediction']}
    assert set(nouveau.chaines)=={'transfert_roles/'+n for n in confirmes}
    assert len(confirmes)==2
    for c in nouveau.chaines.values():
        m=c.perception
        assert isinstance(m,RolesReaffectes) and not nouveau.reconstruction
        assert len(nouveau.images)==1 and not nouveau.actions and c._verifie is not None
        assert sorted(p['pixels'].shape for p in m.pieces)==[(3,3),(3,6),(6,3),(6,6)]
        assert len(m.cibles)==4 and len(c.lots)==0
        assert np.array_equal(m.rendu(m.scene(archive.images[-1])),m.vue(archive.images[-1]))
    assert source.programme==programme and source.perception.signature_observation()==perception
    assert nouveau.theorie_precedente is None
    assert nouveau.graine_exploration==getattr(archive,'graine_exploration',0)

def test_translation_instance_ne_change_pas_programme(archive):
    source=archive.modele_gagnant;g=np.asarray(source.grilles[0]);shift=np.roll(g,3,axis=1)
    a,_=reaffecter(source,g,[]);b,_=reaffecter(source,shift,[])
    assert a.programme==b.programme
    assert [(p['x']+3,p['y']) for p in a.perception.pieces]==[(p['x'],p['y']) for p in b.perception.pieces]
    assert np.array_equal(b.perception.rendu(b.perception.scene(shift)),b.perception.vue(shift))

def test_source_regle_modifiee_refuse(archive):
    s=copy.deepcopy(archive.modele_gagnant);s.programme['regles'][0]['quand']=False
    with pytest.raises(ValueError,match='synchronisée'):reaffecter(s,archive.images[-1],[])

def test_sol_cache_ambigu_refuse(archive):
    g=np.array(archive.images[-1],copy=True);g[53,36]=4
    with pytest.raises(ValueError,match='Sol caché ambigu'):reaffecter(archive.modele_gagnant,g,[])

def test_marqueur_complet_modifie_tout_son_rectangle(archive):
    from plan_selection_dynamique import actions_selection
    c,_=reaffecter(archive.modele_gagnant,archive.images[-1],[])
    _,(pc,sc)=c.rejouer()
    grand=next(p for p in sc.sprites if 'piece' in p.get('tags',[]) and p['pixels'].shape==(6,6))
    at=grand['attrs'];a=('MOUSE',grand['y']+at['marqueur_y'],grand['x']+at['marqueur_x'])
    pc.step(sc,a)
    assert all(grand['pixels'][y,x]==c.perception.selection for y,x in at['marqueur_cases'])
    assert any(x[0]=='MOUSE' for x in actions_selection(sc,c.perception))
