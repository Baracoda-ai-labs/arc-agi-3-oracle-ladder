import copy
import numpy as np
from chrysalide.arc3.logique.theorie import Theorie,sous_clic_formes
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.moteur import _sprite
from chrysalide.arc3.ontologie_exec import Scene,rendre
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.sim_rapide import ProgrammeCompile


CROIX=frozenset({(0,0),(2,0),(1,1),(0,2),(2,2)})
CARRE=frozenset((x,y) for x in range(3) for y in range(3))
TROU=CARRE-CROIX


def test_pixels_par_defaut_boite_seulement_formes_explicitement_actives():
    croix=(14,CROIX,2,2);trou=(6,TROU,2,2)
    assert not sous_clic_formes(croix,3,2)
    assert sous_clic_formes(croix,3,2,{CROIX})
    assert not sous_clic_formes(trou,3,2,{CROIX})
    assert not sous_clic_formes(croix,5,2,{CROIX})
    assert Theorie().hitbox_formes==frozenset()


def test_export_boite_forme_exacte_exclut_trou_meme_dimensions():
    th=Theorie(motif=frozenset({(0,0)}),bascule={14:15,15:14},formes_bascule=frozenset({CROIX,CARRE}),
        hitbox_formes=frozenset({CROIX,CARRE}),
        motif_formes=((CROIX,frozenset({(0,0,CROIX),(8,0,CARRE)})),))
    monde=((6,TROU,2,2),(14,CROIX,2,2),(14,CARRE,6,2))
    attendu=th.rendu(th.clic(monde,3,2),(64,64),4)
    assert np.count_nonzero(attendu!=th.rendu(monde,(64,64),4))==14
    programme,non=exporter(th,(64,64));assert not non
    for cls in (Programme,ProgrammeCompile):
        scene=Scene((64,64),4,4,[dict(_sprite(o),couche=0) for o in monde])
        cls(programme).step(scene,('MOUSE',2,3))
        assert np.array_equal(rendre({'vue':scene.vue,'fond':scene.fond,'letterbox':4,'sprites':scene.sprites}),attendu)
    assert th.hitbox_formes==frozenset({CROIX,CARRE})


def test_pas_de_configuration_implicite_dans_export_legacy():
    th=Theorie(motif=frozenset({(0,0)}),bascule={14:15})
    avant=exporter(th,(16,16))
    copie=copy.deepcopy(th);copie.hitbox_formes=frozenset()
    assert exporter(copie,(16,16))==avant
