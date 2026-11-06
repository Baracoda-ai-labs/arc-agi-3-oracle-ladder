# SPDX-License-Identifier: MIT-0
"""CW-228 (ft09) : but motif_rel(même, autre), côté théorie de C et côté programme exporté (langage de A)."""
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.theorie import VOISINS8, Theorie, motif_relatif
from chrysalide.arc3.moteur import _sprite
from chrysalide.arc3.ontologie_exec import Scene

UN = frozenset({(0, 0)})


def _monde(veut_meme, couleurs):
    """Cible en (5, 5) : centre 8, marques 0 (« même ») ou 2 (« autre ») ; tuiles d'une case à 4·(dx, dy)."""
    m = [(8, UN, 5, 5)]
    for (dx, dy), meme, c in zip(VOISINS8, veut_meme, couleurs, strict=True):
        m += [(0 if meme else 2, UN, 5 + dx, 5 + dy), (c, UN, 5 + 4 * dx, 5 + 4 * dy)]
    return tuple(m)


def test_motif_relatif():
    veut = [True, False] * 4
    juste = [8 if v else 9 for v in veut]
    assert motif_relatif(_monde(veut, juste), 0, 2)
    assert not motif_relatif(_monde(veut, [9] + juste[1:]), 0, 2)
    assert not motif_relatif(_monde(veut, juste), 2, 0)
    assert not motif_relatif(((8, UN, 5, 5),), 0, 2)  # sans cible : faux


def test_motif_relatif_exporte():
    veut = [True, False] * 4
    for couleurs, attendu in (([8 if v else 9 for v in veut], True), ([9] * 8, False)):
        monde = _monde(veut, couleurs)
        th = Theorie(but=("motif_rel", 0, 2))
        prog, non = exporter(th, (11, 11))
        sc = Scene((11, 11), 5, 5, [_sprite(o) | {"visible": True} for o in monde])
        Programme(prog).step(sc, ("UP",))
        assert not non and (sc.issue == "niveau") == attendu == motif_relatif(monde, 0, 2)


def test_ordonner_proposes():
    from chrysalide.arc3.moteur import ordonner_proposes
    cands = [("remplir", 1, 2), ("sortie", 1, 3), ("sortie", 1, 9), ("motif_rel", 0, 2)]
    assert ordonner_proposes(cands, [["sortie", 1, 9], "motif_rel"]) == [
        ("sortie", 1, 9), ("motif_rel", 0, 2), ("remplir", 1, 2), ("sortie", 1, 3)]
    assert ordonner_proposes(cands, []) == cands


def test_regles_extra(monkeypatch, tmp_path):
    import json

    from chrysalide.arc3.moteur import _exporter
    f = tmp_path / "r.json"
    f.write_text(json.dumps([{"nom": "extra", "phase": 0, "quand": True, "alors": []}]))
    base, _ = _exporter(Theorie(), (5, 5))
    monkeypatch.setenv("CHRYS_REGLES_EXTRA", str(f))
    prog, _ = _exporter(Theorie(), (5, 5))
    assert prog["regles"][-1]["nom"] == "extra" and len(prog["regles"]) == len(base["regles"]) + 1
