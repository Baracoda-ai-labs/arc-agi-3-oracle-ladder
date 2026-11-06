import pytest
import mesure_phases_agent as m


def clocks(monkeypatch,values):
    it=iter(values);monkeypatch.setattr(m,'horloges',lambda:dict(zip(('mur_s','cpu_parent_s','cpu_enfants_recoltes_s'),next(it))))

class Agent:
    def __init__(self):self.journal=[];self.images=[0];self.actions=[];self.chaines={};self.reconstruction=True
    @m.mesurer('reconstruction')
    def reconstruire(self):
        self.journal.append({'type':'admission','controle':{'rejeu':True}});self.chaines['a']=1
    @m.mesurer('decision')
    def decider(self):self.reconstruire();return {'statut':'plan','actions':[2]}


def test_inclusif_pas_double_compte_et_contrat(monkeypatch):
    clocks(monkeypatch,[(0,0,0),(1,1,0),(4,3,2),(6,5,2)])
    a=Agent();assert a.decider()=={'statut':'plan','actions':[2]}
    inner,outer=[e for e in a.journal if e['type']=='mesure_phase_agent']
    assert inner['durees_inclusives']==dict(mur_s=3,cpu_parent_s=2,cpu_enfants_recoltes_s=2)
    assert outer['durees_inclusives']==dict(mur_s=6,cpu_parent_s=5,cpu_enfants_recoltes_s=2)
    assert outer['durees_hors_enfants_instrumentes']==dict(mur_s=3,cpu_parent_s=3,cpu_enfants_recoltes_s=0)
    assert inner['parent_phase']=='decision' and outer['parent_phase'] is None
    assert outer['evenements_admission']==outer['evenements_admission_valides']==1
    assert outer['contexte_entree']['raison_causale'].startswith('non_instrumentee')
    assert m.PILE.get()==()


def test_exception_originale_et_pile_nettoyee(monkeypatch):
    clocks(monkeypatch,[(0,0,0),(2,1,0)])
    class A(Agent):
        @m.mesurer('decision')
        def mauvais(self):raise ValueError('originale')
    a=A()
    with pytest.raises(ValueError,match='originale'):a.mauvais()
    assert a.journal[-1]['exception']=='ValueError' and not m.PILE.get()


def test_sans_journal_pas_changement():
    class A:
        @m.mesurer('decision')
        def f(self,x):return x
    x=object();assert A().f(x) is x


def test_recursion_pas_somme_des_trois_inclusifs(monkeypatch):
    clocks(monkeypatch,[(0,0,0),(1,1,0),(2,2,0),(3,3,0),(5,5,0),(8,8,0)])
    class A(Agent):
        @m.mesurer('decision')
        def f(self,n):return self.f(n-1) if n else {'statut':'fin'}
    a=A();a.f(2);events=a.journal
    assert [e['profondeur'] for e in events]==[2,1,0]
    assert events[-1]['durees_inclusives']['mur_s']==8
    assert sum(e['durees_hors_enfants_instrumentes']['mur_s'] for e in events)==8
