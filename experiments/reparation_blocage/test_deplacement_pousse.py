import copy
import numpy as np
import pytest
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.sim_rapide import ProgrammeCompile
from chrysalide.arc3.moteur import MoteurFormel
from chrysalide.arc3.logique.plan_langage import cle_complete

P=frozenset({(0,0)})

@pytest.mark.parametrize('enabled,delta',[(False,2),(True,1)])
def test_poussee_deplacement_meme_effet_trois_moteurs(enabled,delta):
    th=Theorie(moves={(2,4):(1,0),(3,4):(1,0)},poussables=frozenset({3}),dedoublonne_poussee=enabled)
    monde=((2,P,2,2),(3,P,3,2))
    attendu,_=th.pas(monde,4,(64,64))
    assert next(o[2] for o in attendu if o[0]==3)==3+delta
    prog,non=exporter(th,(64,64));assert not non
    m=MoteurFormel();g=th.rendu(monde,(64,64),0)
    pi,pc=Programme(prog),ProgrammeCompile(prog)
    si,sc=m.scene(g),m.scene(g)
    for _ in range(2):
        pi.step(si,('RIGHT',));pc.step(sc,('RIGHT',))
        assert np.array_equal(m.rendu(si),th.rendu(attendu,(64,64),0))
        assert cle_complete(si,pi.etat)==cle_complete(sc,pc.etat)
        attendu,_=th.pas(attendu,4,(64,64))


def test_effet_different_conserve():
    th=Theorie(moves={(2,4):(1,0),(3,4):(0,1)},poussables=frozenset({3}),dedoublonne_poussee=True)
    e,_=th.pas(((2,P,2,2),(3,P,3,2)),4,(64,64))
    assert next(o[2:] for o in e if o[0]==3)==(4,3)


def test_poussee_bloquee_ne_marque_pas_un_deplacement():
    th=Theorie(moves={(2,4):(1,0),(3,4):(0,1)},poussables=frozenset({3}),solides=frozenset({4}),dedoublonne_poussee=True)
    e,_=th.pas(((2,P,2,2),(3,P,3,2),(4,P,4,2)),4,(64,64))
    assert next(o[2:] for o in e if o[0]==2)==(2,2)
    assert next(o[2:] for o in e if o[0]==3)==(3,3)
