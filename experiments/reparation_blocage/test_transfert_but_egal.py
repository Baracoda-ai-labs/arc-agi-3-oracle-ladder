"""Admission d'un prior renommé : fidélité complète et but supplémentaire."""
from types import SimpleNamespace
import pytest
from chrysalide.arc3 import moteur
from chrysalide.arc3.logique import faits, induction, theorie, transfert


@pytest.mark.parametrize('flag,exactes,but_local,but_prior,attendu', [
    ('1',3,None,('absent',9),True),
    ('0',3,None,('absent',9),False),
    ('1',2,None,('absent',9),False),
    ('1',3,('absent',8),('absent',9),False),
    ('1',3,None,None,False),
])
@pytest.mark.parametrize('conserver', [False, True])
def test_prior_but_egal(monkeypatch, flag, exactes, but_local, but_prior, attendu, conserver):
    attendu = attendu or (conserver and flag == '0' and exactes == 3 and but_local is None and but_prior is not None)
    ancien = theorie.Theorie(bascule={9:12}, but=('absent',9))
    local = theorie.Theorie(bascule={8:12}, but=but_local)
    prior = theorie.Theorie(bascule={8:12}, but=but_prior)
    tr = SimpleNamespace(actions=[1,1,1], exclues=frozenset({(0,0)}), taille=(3,3))
    monkeypatch.setenv('CHRYS_TRANSFERT',flag)
    monkeypatch.setenv('CHRYS_TRANSFERT_FUSION','0')
    monkeypatch.setenv('CHRYS_ECONOMIE','0')
    monkeypatch.setenv('CHRYS_PERCEPTION_PORTEFEUILLE','0')
    monkeypatch.setattr(faits,'Trajectoire',lambda *a,**kw:tr)
    monkeypatch.setattr(moteur,'_trajectoire_heritee',lambda *a:tr)
    appels = iter([local] if conserver else [ancien,local])
    inductions=[]
    def induire(*a,**kw):
        inductions.append(kw.get('anciennes'))
        return next(appels),{}
    monkeypatch.setattr(induction,'induire',induire)
    monkeypatch.setattr(theorie,'rejeu',lambda t,_:(0 if t.bascule == {9:12} else exactes if t is prior else 3,3,None))
    monkeypatch.setattr(transfert,'transferer',lambda *a:(prior,{9:8},exactes))
    monkeypatch.setattr(moteur,'_simulateur_exact',lambda h:None)
    exportes=[]
    def exporter(t,taille):
        exportes.append(t)
        return None,['arret du test avant planification']
    monkeypatch.setattr(moteur,'_exporter',exporter)
    lot={'actions':[{'action':'UP'}]}
    m=moteur.MoteurC(budget=1, theorie_precedente=ancien if conserver else None)
    m.proposer({'grilles':[[[0]]]*4,'lots':[lot]*3,'precedents':[{'grilles':[[[0]]]*4,'lots':[lot]*3,'finale':lot}]})
    assert (m.infos.get('but_transfere_hypothese') is True) == attendu
    assert any(t is prior for t in exportes) == attendu
    if attendu:
        assert exportes[0] is prior
    assert local.but == but_local and ancien.bascule == {9:12}
    if conserver:
        assert len(inductions) == 1
        assert inductions[0] is not ancien and inductions[0] is not m.theorie_precedente
        assert ancien.hors_jeu == frozenset() and m.theorie_precedente.hors_jeu == frozenset()


@pytest.mark.parametrize('complet', [False, True])
def test_complement_refute_doit_rejouer_tout(monkeypatch, complet):
    ancien = theorie.Theorie(bascule={9:12}, but=('motif_rel',0,2))
    local = theorie.Theorie(bascule={8:12}, but=ancien.but)
    complement = theorie.Theorie(bascule={12:8})
    tr = SimpleNamespace(actions=[1,1,1], exclues=frozenset(), taille=(3,3))
    monkeypatch.setenv('CHRYS_TRANSFERT','0')
    monkeypatch.setenv('CHRYS_TRANSFERT_FUSION','0')
    monkeypatch.setenv('CHRYS_ECONOMIE','0')
    monkeypatch.setenv('CHRYS_PERCEPTION_PORTEFEUILLE','0')
    monkeypatch.setattr(moteur,'_trajectoire_heritee',lambda *a:tr)
    observations=[]
    def induire(sources, **kw):
        observations.append(sources[0][1])
        return (complement if sources[0][1] == [2] else local), {}
    monkeypatch.setattr(induction,'induire',induire)
    def rejeu(t,_):
        if t.bascule == {9:12}:
            return 0,3,0
        return (3,3,None) if complet and t.bascule == {8:12,12:8} else (2,3,2)
    monkeypatch.setattr(theorie,'rejeu',rejeu)
    monkeypatch.setattr(transfert,'transferer',lambda *a:(ancien,{},0))
    monkeypatch.setattr(moteur,'_simulateur_exact',lambda h:None)
    monkeypatch.setattr(moteur,'_exporter',lambda *a:(None,['arret avant planification']))
    lot={'actions':[{'action':'UP'}]}
    m=moteur.MoteurC(budget=1,theorie_precedente=ancien)
    m.proposer({'grilles':[[[0]]]*4,'lots':[lot]*3})
    assert observations == [None,None,[2]]
    assert m.infos['revision_prior']['admis'] == complet
    assert m.th_releve.bascule == ({8:12,12:8} if complet else {8:12})
    assert m.th_releve.but == ancien.but
    assert local.bascule == {8:12} and ancien.bascule == {9:12}


@pytest.mark.parametrize('voie', ['but_suppose','planifier','plan_langage'])
def test_theorie_retenue_correspond_au_programme_sans_flags(monkeypatch, voie):
    from chrysalide.arc3.logique import plan
    from chrysalide.arc3.logique.export_langage import exporter
    source = theorie.Theorie(moves={(2,1):(0,-1)}, but=None if voie=='but_suppose' else ('absent',3,3))
    local = theorie.Theorie(moves={(1,1):(0,-1)})
    tr = SimpleNamespace(actions=[1], exclues=frozenset(), taille=(3,3), etats=[(),()])
    for nom in ('CHRYS_TRANSFERT','CHRYS_ECONOMIE','CHRYS_CHAINE_COHERENTE','CHRYS_REPARATION_BLOCAGE','CHRYS_PERCEPTION_PORTEFEUILLE'):
        monkeypatch.setenv(nom,'0')
    monkeypatch.setenv('CHRYS_BUT_SUPPOSE','1')
    monkeypatch.setenv('CHRYS_PLAN_LANGAGE','1')
    monkeypatch.setattr(moteur,'_trajectoire_heritee',lambda *a:tr)
    monkeypatch.setattr(induction,'induire',lambda *a,**kw:(local,{}))
    monkeypatch.setattr(theorie,'rejeu',lambda *a:(1,1,None))
    monkeypatch.setattr(theorie,'monde_final',lambda *a:())
    monkeypatch.setattr(moteur,'_simulateur_exact',lambda *a:None)
    monkeypatch.setattr(moteur,'_mdl',lambda *a:{})
    monkeypatch.setattr(moteur,'_garde',lambda m,c,t,p:p)
    monkeypatch.setattr(plan,'planifier',lambda *a,**kw:([1] if voie=='planifier' else None,1))
    monkeypatch.setattr(moteur,'_plan_langage',lambda *a,**kw:[{'action':'UP'}])
    def supposer(c,*a):
        from dataclasses import replace
        return replace(c,but=('absent',3,3)),[1],1
    monkeypatch.setattr(moteur,'_but_suppose',supposer)
    m=moteur.MoteurC(budget=1,theorie_precedente=source)
    r=m.proposer({'grilles':[[[0]]]*2,'lots':[{'actions':[{'action':'UP'}]}]})
    assert r is not None, m.infos
    assert m.th_plan is m.th_releve
    assert m.th_plan.moves == source.moves
    assert m.th_plan.but == ('absent',3,3)
    assert exporter(m.th_plan,tr.taille)[0] == r[1]


def test_deux_contre_exemples_avant_admission(monkeypatch):
    prior=theorie.Theorie(bascule={7:8},but=('motif_rel',0,2))
    local=theorie.Theorie(bascule={9:8},but=prior.but)
    tr=SimpleNamespace(actions=[1]*3,exclues=frozenset(),taille=(3,3))
    for nom in ('CHRYS_TRANSFERT','CHRYS_TRANSFERT_FUSION','CHRYS_ECONOMIE','CHRYS_PERCEPTION_PORTEFEUILLE'):
        monkeypatch.setenv(nom,'0')
    monkeypatch.setattr(moteur,'_trajectoire_heritee',lambda *a:tr)
    observes=[]
    def induire(sources,**kw):
        ts=sources[0][1];observes.append(ts)
        return (local if ts is None else theorie.Theorie(bascule={8:12} if ts==[1] else {12:9})),{}
    def rejeu(t,_):
        n=sum(t.bascule.get(k)==v for k,v in ((9,8),(8,12),(12,9)))
        return n,3,None if n==3 else n
    monkeypatch.setattr(induction,'induire',induire)
    monkeypatch.setattr(theorie,'rejeu',rejeu)
    monkeypatch.setattr(transfert,'transferer',lambda *a:(prior,{},0))
    monkeypatch.setattr(moteur,'_simulateur_exact',lambda h:None)
    monkeypatch.setattr(moteur,'_exporter',lambda *a:(None,['arret avant planification']))
    m=moteur.MoteurC(budget=1,theorie_precedente=prior)
    m.proposer({'grilles':[[[0]]]*4,'lots':[{'actions':[{'action':'UP'}]}]*3})
    assert observes==[None,None,[1],[2]]
    assert m.infos['revision_prior']['admis']
    assert [e['apres'] for e in m.infos['revision_prior']['etapes']]==[2,3]
    assert m.th_releve.bascule=={9:8,8:12,12:9}
    assert local.bascule=={9:8}
