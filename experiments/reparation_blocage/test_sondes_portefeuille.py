from types import SimpleNamespace
import numpy as np
import sondes_portefeuille as sp


def test_portefeuille_mixte_ne_desactive_pas_experience(monkeypatch):
    image=np.zeros((2,2));perception=SimpleNamespace(vue=lambda g:g)
    c=SimpleNamespace(perception=perception,diagnostic_hitbox={'interaction':'boite'})
    autre=SimpleNamespace(perception=perception)
    a=SimpleNamespace(chaines={'perception_clics/3':c,'nouveau_but':autre},images=[image],actions=[],journal=[],attente=None)
    a.dossier=lambda offre:None
    a._choisir_sonde_utile=lambda dossier,candidats:(candidats[0],{'test':'deux_modeles'})
    a._suivre_experience=lambda r:None
    monkeypatch.setattr(sp,'actions_modele',lambda c,offre:[('MOUSE',1,2)])
    r=sp.proposer(a,[6])
    assert r['actions']==[['clic',2,1]] and a.attente is r


def test_action_deja_observee_meme_etat_non_rejouee(monkeypatch):
    image=np.zeros((2,2));c=SimpleNamespace(perception=SimpleNamespace(vue=lambda g:g),diagnostic_hitbox={})
    a=SimpleNamespace(chaines={'a':c,'b':c},images=[image,image],actions=[['clic',2,1]],journal=[])
    a.dossier=lambda offre:None
    def choisir(dossier,candidats):
        assert candidats==[]
        return None,{'refus':'pas_action_nouvelle'}
    a._choisir_sonde_utile=choisir
    monkeypatch.setattr(sp,'actions_modele',lambda c,offre:[('MOUSE',1,2)])
    assert sp.proposer(a,[6]) is None


def test_meme_image_buts_distincts_produit_experience_utile():
    from chaine_agent_integree import AgentIntegre
    objets={n:SimpleNamespace(description_perception=lambda:{'masque':[]}) for n in ('a','b')}
    a=SimpleNamespace(chaines=objets)
    a._predire=lambda c,action:{'image':[[1]],'issue':'niveau' if c is objets['a'] else None}
    dossier=SimpleNamespace(reserve=20,coups_payes=0,signature=lambda:'test')
    candidat=(1,'a',('MOUSE',1,1))
    choix,d=AgentIntegre._choisir_sonde_utile(a,dossier,[candidat])
    assert choix==candidat and d['choix']['information_convention_uniforme']==1
    assert d['choix']['predictions']['a']['issue']=='niveau'
    assert d['choix']['predictions']['b']['issue']=='continue'
    a._predire=lambda c,action:{'image':[[1]],'issue':None}
    choix,d=AgentIntegre._choisir_sonde_utile(a,dossier,[candidat])
    assert choix is None
