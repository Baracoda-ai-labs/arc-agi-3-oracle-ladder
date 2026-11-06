# SPDX-License-Identifier: MIT-0
"""Non-régression (B, CCM-147-C / CCM-189-B) : le programme EXPORTÉ de re86 explique autant de transitions que la théorie
de C sur l'amorce diag4 (40 coups au hasard, graine 0). ≈ 1 s.
Contrôle déjà vu : `2423a5d` faisait tomber le programme à 0,0 pour une théorie à 0,975."""
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]


def test_export_re86_suit_la_theorie():
    sys.path[:0] = [str(R / "experiments/T3.9")]
    import export_contre_theorie as E
    import porte_regles as PR

    from chrysalide.arc3.logique.theorie import rejeu
    b = PR.preparer("re86")
    ok, n, _ = rejeu(E._theorie(b), b["moteur"].tr, libre=False)
    d = PR._detail(b, b["prog"])
    theorie, programme = ok / max(n, 1), sum(d) / max(len(d), 1)
    assert theorie > 0.5, f"théorie de re86 trop basse ({theorie:.3f}) : le test ne contrôle plus l'export"
    assert programme >= theorie - 0.05, f"export perdu : programme {programme:.3f} contre théorie {theorie:.3f}"
