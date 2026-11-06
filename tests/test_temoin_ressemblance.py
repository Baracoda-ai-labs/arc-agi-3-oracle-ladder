import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments/G"))
from temoin_ressemblance import classer  # noqa: E402


def _o(x, y, px):
    return {"x": x, "y": y, "pixels": px}


def test_jumeau_premier_puis_meme_forme_puis_reste():
    pil = _o(5, 5, [[14]])
    jumeau = _o(9, 9, [[542]])  # 512 + 14 + 16 : même couleur rendue, même forme
    meme_forme = _o(1, 1, [[4]])
    autre = _o(2, 2, [[4, 4], [4, -1]])
    fond = _o(0, 0, [[2] * 20] * 20)
    r = classer([fond, autre, meme_forme, pil, jumeau], 3, (20, 20))
    assert [o for _s, o in r] == [jumeau, meme_forme, autre]
    assert r[0][0] == 3.0 and r[1][0] == 2.0


def test_permutation_sans_effet():
    pil, a, b = _o(5, 5, [[14]]), _o(9, 9, [[542]]), _o(1, 1, [[4]])
    assert [o for _s, o in classer([a, b, pil], 2)] == [o for _s, o in classer([b, pil, a], 1)]
