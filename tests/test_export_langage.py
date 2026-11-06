"""CW-196 (D) : l'export d'une théorie de C dans le langage de A rejoue EXACTEMENT theorie.pas / theorie.clic
(poussée, solides, poursuivants, saut, téléportation, clics), sur des mondes tirés au hasard (objets d'une case)."""
import random

import pytest

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.moteur import _sprite
from chrysalide.arc3.ontologie_exec import Scene

UN = frozenset({(0, 0)})
NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT"}
MOVES = {(8, 1): (0, -1), (8, 2): (0, 1), (8, 3): (-1, 0), (8, 4): (1, 0)}


def _monde(rng, w, h, effectifs):
    cases = rng.sample([(x, y) for x in range(w) for y in range(h)], sum(effectifs.values()))
    out, i = [], 0
    for c, n in effectifs.items():
        for _ in range(n):
            out.append((c, UN, *cases[i]))
            i += 1
    return tuple(out)


def _vu_c(monde):
    return sorted((o[0], o[2], o[3]) for o in monde)


def _vu_a(sc):
    return sorted((int(s["pixels"].max()), s["x"], s["y"]) for s in sc.sprites if s.get("visible", True))


def _comparer(th, effectifs, actions, graines=range(30), w=7, h=7):
    prog, non = exporter(th, (w, h))
    assert not non
    for g in graines:
        rng = random.Random(g)
        monde = _monde(rng, w, h, effectifs)
        sc, p = Scene((h, w), 0, 0, [_sprite(o) | {"visible": True} for o in monde]), Programme(prog)
        for t in range(25):
            a = rng.choice(actions)
            if isinstance(a, tuple):
                monde = th.clic(monde, a[1], a[2])
                k = min(64 // w, 64 // h)
                p.step(sc, ("MOUSE", (64 - h * k) // 2 + a[2] * k, (64 - w * k) // 2 + a[1] * k))
            else:
                monde, _ = th.pas(monde, a, (w, h))
                p.step(sc, (NOMS[a],))
            assert _vu_a(sc) == _vu_c(monde), (g, t, a)


def test_poussee_et_solides():
    _comparer(Theorie(moves=dict(MOVES), solides=frozenset({9}), poussables=frozenset({3})), {8: 1, 3: 4, 9: 5}, [1, 2, 3, 4])


def test_poursuivants():
    _comparer(Theorie(moves=dict(MOVES), solides=frozenset({9}), poussables=frozenset({3}), autonomes={5: 8}),
              {8: 1, 3: 2, 9: 4, 5: 2}, [1, 2, 3, 4])


def test_saut_et_teleportation():
    th = Theorie(moves=dict(MOVES), solides=frozenset({9}), saut={(8, 2): (0, 2), (8, 4): (2, 0)}, teleports={6: (0, 1)})
    _comparer(th, {8: 1, 9: 6, 6: 3}, [1, 2, 3, 4])


def test_clics():
    th = Theorie(motif=frozenset({(0, 0), (1, 0), (0, 1)}), bascule={2: 4, 4: 2})
    w = h = 6
    clics = [("clic", x, y) for x in range(w) for y in range(h)]
    _comparer(th, {2: 10, 4: 10}, clics, w=w, h=h)


def test_clics_avec_zone():
    """CW-228 (ft09) : seuls les objets dans la boîte d'un cadre de la couleur `zone`, plus grand qu'eux, basculent."""
    cadre = frozenset({(x, y) for x in range(5) for y in range(5) if x in (0, 4) or y in (0, 4)})
    th = Theorie(motif=UN, bascule={2: 4, 4: 2}, zone=7)
    w = h = 7
    prog, non = exporter(th, (w, h))
    assert not non
    for g in range(10):
        rng = random.Random(g)
        tuiles = [(rng.choice([2, 4]), UN, x, y) for x in (1, 2, 3, 5, 6) for y in (1, 2, 3, 5) if rng.random() < 0.7]
        monde = ((7, cadre, 0, 0), *tuiles)
        sc, p = Scene((h, w), 0, 0, [_sprite(o) | {"visible": True} for o in monde]), Programme(prog)
        for t in range(20):
            x, y = rng.randrange(w), rng.randrange(h)
            monde = th.clic(monde, x, y)
            k = min(64 // w, 64 // h)
            p.step(sc, ("MOUSE", (64 - h * k) // 2 + y * k, (64 - w * k) // 2 + x * k))
            assert sorted(o[:1] + o[2:] for o in monde if o[0] != 7) == [v for v in _vu_a(sc) if v[0] != 7], (g, t)


def test_fond_solide():
    """ls20 : on n'avance que sur une case couverte par un autre objet (le sol, couleur 4)."""
    th = Theorie(moves=dict(MOVES), fond_solide=True)
    prog, non = exporter(th, (7, 7))
    assert not non
    for g in range(30):
        rng = random.Random(g)
        sol = rng.sample([(x, y) for x in range(7) for y in range(7)], 25)
        monde = tuple([(4, UN, x, y) for x, y in sol] + [(8, UN, *sol[0])])
        sc, p = Scene((7, 7), 0, 0, [_sprite(o) | {"visible": True} for o in monde]), Programme(prog)
        for t in range(25):
            a = rng.choice([1, 2, 3, 4])
            monde, _ = th.pas(monde, a, (7, 7))
            p.step(sc, (NOMS[a],))
            assert _vu_a(sc) == _vu_c(monde), (g, t, a)


def test_annulation_en_pile():
    """induction.precedent_pile : chaque coup qui CHANGE l'état empile l'état d'avant ; UNDO dépile (rien si vide)."""
    th = Theorie(moves=dict(MOVES), solides=frozenset({9}), poussables=frozenset({3}), annule=7)
    prog, non = exporter(th, (7, 7))
    assert not non
    for g in range(30):
        rng = random.Random(g)
        monde = _monde(rng, 7, 7, {8: 1, 3: 3, 9: 5})
        sc, p, pile = Scene((7, 7), 0, 0, [_sprite(o) | {"visible": True} for o in monde]), Programme(prog), []
        for t in range(40):
            a = rng.choice([1, 2, 3, 4, 7, 7])
            if a == 7:
                monde = pile.pop() if pile else monde
                p.step(sc, ("UNDO",))
            else:
                m2, _ = th.pas(monde, a, (7, 7))
                if m2 != monde:
                    pile.append(monde)
                monde = m2
                p.step(sc, (NOMS[a],))
            assert _vu_a(sc) == _vu_c(monde), (g, t, a)


@pytest.mark.parametrize("champ", ["exclusif", "teleports_cases"])
def test_non_exporte_reste_signale(champ):
    th = Theorie(motif=UN, bascule={2: 4}, zone=7 if champ == "zone" else None, exclusif=champ == "exclusif",
                 derives={5: (2, "x", 6)} if champ == "derives" else {},
                 teleports_cases={(1, 1): (0, 2)} if champ == "teleports_cases" else {})
    assert exporter(th, (5, 5))[1]


def _image_c(th, monde, w, h):
    return {(x, y): o[0] for o in sorted(monde, key=lambda o: th.couches()(o[0])) for x, y in
            [(o[2] + a, o[3] + b) for a, b in o[1]] if 0 <= x < w and 0 <= y < h}


def _image_a(sc, w, h):
    out = {}
    for s in sorted([s for s in sc.sprites if s.get("visible", True)], key=lambda s: s["couche"]):
        px = s["pixels"]
        for j in range(px.shape[0]):
            for i in range(px.shape[1]):
                if px[j, i] >= 0 and 0 <= s["x"] + i < w and 0 <= s["y"] + j < h:
                    out[(s["x"] + i, s["y"] + j)] = int(px[j, i])
    return out


@pytest.mark.parametrize("sens,a2", [("x", 6), ("x", 7), ("y", 6), ("xy", 7)])
def test_reflets_image(sens, a2):
    """theorie.deriver (reflet, clé tuple) : même IMAGE que le langage (découpage en objets non comparé)."""
    th = Theorie(moves=dict(MOVES), solides=frozenset({9}), derives={("r", 6): ((frozenset({8}), sens, a2, True))})
    prog, non = exporter(th, (7, 7))
    assert not non
    for g in range(20):
        rng = random.Random(g)
        monde = tuple(th.deriver(list(_monde(rng, 7, 7, {8: 1, 9: 6})), (7, 7)))
        sc, p = Scene((7, 7), 0, 0, [_sprite(o) | {"visible": True} for o in monde]), Programme(prog)
        for t in range(20):
            a = rng.choice([1, 2, 3, 4])
            monde, _ = th.pas(monde, a, (7, 7))
            p.step(sc, (NOMS[a],))
            assert _image_a(sc, 7, 7) == _image_c(th, monde, 7, 7), (g, t, a)


@pytest.mark.parametrize("a2", [6, 7])
def test_miroir_image(a2):
    """theorie.deriver (miroir, clé simple) : l'objet D existant devient source ∪ reflet(source)."""
    th = Theorie(moves=dict(MOVES), derives={6: (8, "x", a2)})
    prog, non = exporter(th, (7, 7))
    assert not non
    for g in range(20):
        rng = random.Random(g)
        brut = _monde(rng, 7, 7, {8: 1, 6: 1})  # scène = objets perçus (formes à décalages ≥ 0) ; C dérive aussitôt
        monde = tuple(th.deriver(list(brut), (7, 7)))
        sc, p = Scene((7, 7), 0, 0, [_sprite(o) | {"visible": True} for o in brut]), Programme(prog)
        for t in range(15):
            a = rng.choice([1, 2, 3, 4])
            monde, _ = th.pas(monde, a, (7, 7))
            p.step(sc, (NOMS[a],))
            assert _image_a(sc, 7, 7) == _image_c(th, monde, 7, 7), (g, t, a)


def test_clics_formes_bascule():
    """ft09 N3 : seules les formes vues basculer basculent ; un objet d'une autre forme (interface) reste tel quel."""
    deux = frozenset({(0, 0), (1, 0)})
    th = Theorie(motif=UN, bascule={2: 4, 4: 2}, formes_bascule=frozenset({UN}))
    w = h = 6
    prog, non = exporter(th, (w, h))
    assert not non
    monde = ((2, UN, 1, 1), (2, deux, 3, 3), (4, UN, 0, 5))
    sc, p = Scene((h, w), 0, 0, [_sprite(o) | {"visible": True} for o in monde]), Programme(prog)
    for x, y in ((1, 1), (3, 3), (4, 3), (0, 5)):
        monde = th.clic(monde, x, y)
        k = min(64 // w, 64 // h)
        p.step(sc, ("MOUSE", (64 - h * k) // 2 + y * k, (64 - w * k) // 2 + x * k))
        assert _vu_a(sc) == _vu_c(monde), (x, y)
    assert (2, deux, 3, 3) in monde and (4, UN, 1, 1) in monde and (2, UN, 0, 5) in monde


def test_mort_exportee():
    """CCM-177-B : theorie.mort ('contact', a, b) → le programme perd quand a recouvre b (comme theorie.meurt)."""
    th = Theorie(moves=dict(MOVES), mort=("contact", 8, 6))
    prog, non = exporter(th, (7, 7))
    assert not non
    for g in range(20):
        rng = random.Random(g)
        monde = _monde(rng, 7, 7, {8: 1, 6: 4})
        sc, p = Scene((7, 7), 0, 0, [_sprite(o) | {"visible": True} for o in monde]), Programme(prog)
        for _t in range(15):
            a = rng.choice([1, 2, 3, 4])
            monde, _ = th.pas(monde, a, (7, 7))
            p.step(sc, (NOMS[a],))
            mort = th.meurt(monde)
            assert (sc.issue == "defaite") == mort, (g, _t)
            if mort:
                break


def test_champ_inconnu_signale():
    """Un champ ajouté à Theorie, inconnu de l'export, est déclaré non exporté (plus de disparition silencieuse)."""
    from dataclasses import field, make_dataclass
    T2 = make_dataclass("T2", [("nouveau", dict, field(default_factory=dict))], bases=(Theorie,))
    assert exporter(T2(), (5, 5))[1] == []
    assert exporter(T2(nouveau={1: 2}), (5, 5))[1] == ["champ inconnu de l'export : nouveau"]


def test_selection_cachee():
    """CCM-132-C : sélecteur SPACE, classes (8, 3) ; seules les lois de la classe sélectionnée s'appliquent."""
    from chrysalide.arc3.logique.theorie import VIRTUEL
    mv = dict(MOVES) | {(3, a): v for (_c, a), v in MOVES.items()}
    th = Theorie(moves=mv, solides=frozenset({9}), selection=(5, (8, 3), 0))
    prog, non = exporter(th, (7, 7))
    assert not non and prog["etat"]["sel"] == 0
    for g in range(20):
        rng = random.Random(g)
        monde = _monde(rng, 7, 7, {8: 1, 3: 1, 9: 4})
        sc, p = Scene((7, 7), 0, 0, [_sprite(o) | {"visible": True} for o in monde]), Programme(prog)
        for t in range(25):
            a = rng.choice([1, 2, 3, 4, 5, 5])
            monde, _ = th.pas(monde, a, (7, 7))
            p.step(sc, (({5: "SPACE"} | NOMS)[a],))
            assert _vu_a(sc) == _vu_c([o for o in monde if o[0] != VIRTUEL]), (g, t, a)


def test_debordement():
    """CCM-132-C : une classe qui « déborde » peut sortir en partie de la grille (au moins une case reste)."""
    deux = frozenset({(0, 0), (1, 0)})
    th = Theorie(moves=dict(MOVES), debordent=frozenset({8}))
    prog, non = exporter(th, (6, 6))
    assert not non
    for g in range(20):
        rng = random.Random(g)
        brut = ((8, deux, rng.randrange(5), rng.randrange(6)),)
        monde = brut
        sc, p = Scene((6, 6), 0, 0, [_sprite(o) | {"visible": True} for o in brut]), Programme(prog)
        for t in range(25):
            a = rng.choice([1, 2, 3, 4])
            monde, _ = th.pas(monde, a, (6, 6))
            p.step(sc, (NOMS[a],))
            assert _image_a(sc, 6, 6) == _image_c(th, monde, 6, 6), (g, t, a)
