import copy
import cloudpickle,numpy as np
from pathlib import Path
from chaine_agent_integree import canon,lots
from chaine_coherente import Chaine
from test_revision_garde_commune import sources
from revision_garde_commune import proposer
from memoire_contexte_objets import observer
from types import SimpleNamespace


def fixture():
    a,cs=sources()
    archive=cloudpickle.loads((Path(__file__).parent/'runs/ar25_garde_commune13_1/agent.pkl').read_bytes())
    ch={}
    for i,s in enumerate(cs):
        c,_=proposer(s)
        ch[str(i)]=Chaine(c.perception,c.programme,[g.tolist() for g in archive.images[3:28]],lots(archive.actions[3:27]),[])
    agent=SimpleNamespace(memoire_jeu=archive.memoire_jeu,chaines=ch,actions=archive.actions[:28],journal=[],attente={},reconstruction=False)
    return agent,archive


def test_retour_exact_conserve_programme_calques_et_latent():
    a,s=fixture();programmes={n:copy.deepcopy(c.programme) for n,c in a.chaines.items()}
    r=observer(a,s.images[27],s.images[28],5,'continue')
    assert len(a.modeles_contextes_suspendus)==2 and not a.chaines
    assert not r['prediction_physique']
    a.actions=s.actions[:29];r=observer(a,s.images[28],s.images[29],5,'continue')
    assert len(r['reactives'])==2 and not a.modeles_contextes_suspendus
    for n,c in a.chaines.items():
        assert c.programme==programmes[n] and len(c.lots)==24
        assert c.intervalles_contexte[-1]['actions_non_modelisees']==[5,5]
        assert not c.intervalles_contexte[-1]['prediction_physique_intervalle']
        assert c.rejouer()[1] is not None


def test_faux_retour_et_positions_changees_refuses():
    a,s=fixture();observer(a,s.images[27],s.images[28],5,'continue')
    a.actions=s.actions[:29]
    r=observer(a,s.images[28],s.images[28],5,'continue')
    assert not r['reactives'] and not a.chaines
    image=s.images[29].copy();image[10,10]=(int(image[10,10])+1)%16
    r=observer(a,s.images[28],image,5,'continue')
    assert not r['reactives'] and len(r['refuses'])==2
    assert len(a.modeles_contextes_suspendus)==2


def test_pas_de_suspension_si_autre_effet_observe():
    a,s=fixture();image=s.images[28].copy();image[10,10]=(int(image[10,10])+1)%16
    assert observer(a,s.images[27],image,5,'continue') is None
    assert len(a.chaines)==2


def test_reparation_calques_apres_retour_ne_rejoue_pas_intervalle():
    from chaine_agent_integree import AgentIntegre
    from diagnostic_contexte_transfert import marqueurs
    archive=cloudpickle.loads((Path(__file__).parent/'runs/ar25_memoire_continue_source1/agent.pkl').read_bytes())
    a=AgentIntegre([archive.images[3]],[],[],[],reparation=True)
    a.installer_modele_jeu(copy.deepcopy(archive.memoire_jeu))
    a.images=copy.deepcopy(archive.images[:4]);a.actions=copy.deepcopy(archive.actions[:3])
    a.films=copy.deepcopy(archive.films[:3]);a.issues=copy.deepcopy(archive.issues[:3]);a.debut_contexte=3
    def observe(act,image,film):
        for c in a.chaines.values():
            c.plan={'actions':[canon(act)],**c.signature(),'origine':'test'};c._tracer_plan()
        a.attente={'statut':'experience_conditionnelle','actions':[act],'modeles':list(a.chaines)}
        return a.observer(act,image,film,'continue',source='trace')
    for k in range(3,7):observe(archive.actions[k],archive.images[k+1],archive.films[k])
    original=archive.images[7]
    incompatible=original.copy()
    for color,hosts in marqueurs(original).items():
        if color in (0,9):
            for positions in hosts.values():
                for y,x in positions:incompatible[y,x]=9-color
    assert observe(5,incompatible,[incompatible])['type']=='contexte_modeles_suspendus'
    assert observe(5,original,[original])['type']=='contexte_modeles_reactives'
    observe(archive.actions[7],archive.images[8],archive.films[7])
    assert len(a.chaines)==2 and len(a.actions)==10 and len(a.films)==10
    for c in a.chaines.values():
        assert len(c.lots)==5 and len(c.films.entrees)==5
        assert c.rejouer()[1] is not None
        assert c.intervalles_contexte[0]['actions_non_modelisees']==[5,5]
