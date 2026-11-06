import copy
import numpy as np
import pytest
from test_chaine_coherente import exemple
from chaine_agent_integree import AgentIntegre
from readmission_episode import installer,proposer


def test_instance_initiale_rejouee_sans_plan_ni_ancien_etat():
    c,image=exemple();c.proposer();p=copy.deepcopy(c.programme);signature=c.signature()
    a=AgentIntegre([np.array(image(3))],[],[],[])
    a.modeles_episode_precedent={'ancien':c}
    essais=installer(a,[4]);n=a.chaines['episode_precedent/ancien']
    assert essais[0]['admis'] and not a.reconstruction
    assert n.programme==p and n.plan is None and n.but_hypothese_non_confirmee
    assert not n.lots and len(n.grilles)==1
    assert c.signature()==signature and c.plan is not None
    _,(pc,sc)=n.rejouer();pc.step(sc,('RIGHT',))
    assert np.array_equal(n.perception.rendu(sc),n.perception.vue(image(4)))


def test_source_refutee_et_disposition_non_supportee_refusees():
    c,image=exemple();c.refute=True
    with pytest.raises(ValueError,match='réfutée'):proposer(c,image(3),[],100)
    c.refute=False;c.grilles[-1]=image(3)
    with pytest.raises(ValueError,match='source non admissible'):proposer(c,image(3),[],100)
    c,_=exemple()
    with pytest.raises(ValueError,match='sans adaptateur'):proposer(c,image(5),[],100)


def test_vieux_snapshot_et_refus_ne_desactivent_pas_acquisition():
    _,image=exemple();a=AgentIntegre([np.array(image(3))],[],[],[])
    assert installer(a,[4])==[] and a.reconstruction and not a.chaines


def test_defaite_exacte_conserve_physique_mais_pas_surete_ni_plan():
    from readmission_episode import conserver_physique_terminale
    c,image=exemple();assert c.adopter_plan([('RIGHT',),('RIGHT',)])['statut']=='plan_simule_valide'
    r=c.observer(('RIGHT',),image(5),termine=True,source='jeu')
    assert r['statut']=='fin_sans_victoire' and c.refute
    bank=conserver_physique_terminale({'ancien':c},[{'nom':'ancien',**r}])
    n=proposer(bank['ancien'],image(3),[('RIGHT',)],100)
    assert n.preuve_defaite_physique_exacte['surete_refutee']
    assert n.plan is None and n.but_hypothese_non_confirmee and c.refute
    assert len(bank['ancien'].lots)==2  # terminal physique inclus, pas troncature


def test_defaite_avec_ecart_physique_jamais_archivee():
    from readmission_episode import conserver_physique_terminale
    c,image=exemple();c.adopter_plan([('RIGHT',),('RIGHT',)])
    r=c.observer(('RIGHT',),image(4),termine=True,source='jeu')
    assert not r['image_exacte']
    assert conserver_physique_terminale({'ancien':c},[{'nom':'ancien',**r}])=={}


def test_ancienne_refutation_but_nest_pas_effacee_par_terminal_exact():
    from readmission_episode import conserver_physique_terminale
    c,image=exemple();c.adopter_plan([('RIGHT',),('RIGHT',)])
    r=c.observer(('RIGHT',),image(5),termine=True,source='jeu')
    c.contre_exemples.insert(0,{'statut':'but_refute','differences':[],
                               'issue_predite':'niveau'})
    assert conserver_physique_terminale({'ancien':c},[{'nom':'ancien',**r}])=={}
