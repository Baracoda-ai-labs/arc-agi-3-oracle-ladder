# SPDX-License-Identifier: MIT-0
"""F (CW-451, suffisance de l'état, correctif 1) : la mesure combinée de C (`experiments/films_p1/combo.py`, paquet v2),
avec la clé d'état de l'exploration générique modifiée par `CHRYS_F_CLE` :
  - absent : inchangé (contrôle au coup près contre `combo/fg_g*`) ;
  - `bande3` : le bord masqué fait 3 pixels au lieu de 1 (jauges et compteurs collés au bord : sc25, sb26).
Usage : CHRYS_FILMS_P1=3 CHRYS_G_NOUV=1 [CHRYS_F_CLE=bande3] python -B combo_cle.py <jeux> <sortie> [--graine g]"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "films_p1"))
import combo

if os.environ.get("CHRYS_F_CLE") == "bande3":
    def masque(self, im):
        m = im.copy()
        m[:3, :] = m[-3:, :] = 0
        m[:, :3] = m[:, -3:] = 0
        for (x, y) in self.compteurs:
            m[y, x] = 0
        return m
    combo.GEN2.Explorateur.masque = masque

if __name__ == "__main__":
    combo.main()
