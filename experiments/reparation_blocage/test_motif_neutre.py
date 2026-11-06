import pytest

from chrysalide.arc3.logique.theorie import Theorie, VOISINS8, motif_ecarts
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.sim_rapide import ProgrammeCompile
from chrysalide.arc3.moteur import _sprite
from chrysalide.arc3.ontologie_exec import Scene


def cible(neutre=False, erreur=False, manque=False, origine=8):
    col = {(origine, 8): 7}
    for i, (dx, dy) in enumerate(VOISINS8):
        col[origine+dx, 8+dy] = 3 if neutre and i == 0 else (1 if i % 2 else 2)
        if not (manque and i == 0):
            col[origine+4*dx, 8+4*dy] = 7 if i % 2 else 6
    if erreur:
        dx, dy = VOISINS8[1]
        col[origine+4*dx, 8+4*dy] = 6
    return tuple((k, frozenset({(0, 0)}), x, y) for (x, y), k in col.items())


def verifier(monde, but, attendu):
    th = Theorie(but=but)
    assert th.atteint(monde) is attendu
    texte, non = exporter(th, (32, 32))
    assert not non
    for moteur in (Programme, ProgrammeCompile):
        scene = Scene((32, 32), 0, 0, [dict(_sprite(o), couche=0) for o in monde])
        moteur(texte).step(scene, ('WAIT',))
        assert (scene.issue == 'niveau') is attendu
    return texte


def test_argument_vide_preserve_contrat_et_export():
    monde = cible()
    assert verifier(monde, ('motif_rel', 1, 2), True) == verifier(
        monde, ('motif_rel', 1, 2, ()), True)
    verifier(cible(erreur=True), ('motif_rel', 1, 2, ()), False)


@pytest.mark.parametrize('manque', [False, True])
def test_neutre_detecte_cible_sans_contrainte_meme_sans_case_distante(manque):
    monde = cible(neutre=True, manque=manque)
    verifier(monde, ('motif_rel', 1, 2), False)
    verifier(monde, ('motif_rel', 1, 2, (3,)), True)
    assert motif_ecarts(monde, 1, 2, (3,)) == 0


def test_neutre_ne_masque_pas_contrainte_ni_seconde_cible():
    monde = cible() + cible(neutre=True, erreur=True, origine=22)
    verifier(monde, ('motif_rel', 1, 2), True)
    verifier(monde, ('motif_rel', 1, 2, (3,)), False)
    assert motif_ecarts(monde, 1, 2, (3,)) == 1
    verifier((), ('motif_rel', 1, 2, (3,)), False)
    verifier(cible(neutre=True), ('motif_rel', 1, 2, (4,)), False)


@pytest.mark.parametrize('role', ['meme', 'autre', 'neutre'])
@pytest.mark.parametrize('cible_distante', ['meme', 'autre', 'absente'])
@pytest.mark.parametrize('remapper', [False, True])
def test_roles_concurrents_et_palette(role, cible_distante, remapper):
    monde = cible(neutre=True, manque=True)
    dx, dy = VOISINS8[0]
    if cible_distante != 'absente':
        monde += ((7 if cible_distante == 'meme' else 6,
                   frozenset({(0, 0)}), 8+4*dx, 8+4*dy),)
    palette = {1:11, 2:4, 3:9, 6:2, 7:13} if remapper else {k:k for k in (1,2,3,6,7)}
    monde = tuple((palette[k], f, x, y) for k,f,x,y in monde)
    but = ('motif_rel', palette[1], palette[2], (), ((palette[3], role),))
    attendu = role == 'neutre' or role == cible_distante
    verifier(monde, but, attendu)
    assert motif_ecarts(monde, *but[1:]) == (0 if attendu else 1)


@pytest.mark.parametrize('neutres,roles', [
    ((), ((3,'inconnu'),)), ((), ((1,'autre'),)),
    ((3,), ((3,'meme'),)), ((), ((3,'meme'),(3,'autre'))),
    ((1,), ()),
])
def test_roles_invalides_refuses_par_theorie_et_export(neutres, roles):
    th = Theorie(but=('motif_rel',1,2,neutres,roles))
    with pytest.raises(ValueError):
        th.atteint(cible(neutre=True))
    with pytest.raises(ValueError):
        exporter(th,(32,32))


def test_roles_vides_conservent_exactement_export_ancien():
    th = Theorie(but=('motif_rel',1,2))
    avant = exporter(th,(32,32))
    th.but = ('motif_rel',1,2,(),())
    assert exporter(th,(32,32)) == avant
