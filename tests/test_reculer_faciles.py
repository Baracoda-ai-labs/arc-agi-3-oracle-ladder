# SPDX-License-Identifier: MIT-0
"""E (CW-354.3), écrit par C : un but jamais vrai sur ≥ 5 états vus, atteint par un plan d'UN coup, passe après les autres
(CHRYS_RECULER_FACILES) ; éteint : le 1er but planifiable est pris."""
from types import SimpleNamespace

import chrysalide.arc3.moteur as M


def test_but_facile_recule(monkeypatch):
    plans = {("sortie", 3, 1): ["UP"], ("sortie", 3, 2): ["UP", "UP", "LEFT"]}
    monkeypatch.setattr(M, "_candidats_buts", lambda th, tr, p=(): [("sortie", 3, 1), ("sortie", 3, 2)])
    import chrysalide.arc3.logique.plan as P
    import chrysalide.arc3.logique.theorie as T
    monkeypatch.setattr(P, "planifier", lambda tb, *a, **k: (plans[tb.but], []))
    monkeypatch.setattr(T, "monde_final", lambda tb, tr: ())
    th = SimpleNamespace(pour_but=lambda x: SimpleNamespace(but=x))
    tr = SimpleNamespace(etats=[()] * 8, taille=(4, 4))
    monkeypatch.setenv("CHRYS_RECULER_FACILES", "0")
    assert M._but_suppose(th, tr, [1], 100, 0, 1e9)[0].but == ("sortie", 3, 1)
    monkeypatch.setenv("CHRYS_RECULER_FACILES", "1")
    assert M._but_suppose(th, tr, [1], 100, 0, 1e9)[0].but == ("sortie", 3, 2)
