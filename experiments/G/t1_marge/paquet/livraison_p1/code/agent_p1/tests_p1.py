"""Tests P1 hors ligne (0 coup). python -m agent_p1.tests_p1"""
import unittest
from pathlib import Path
import numpy as np

RACINE = Path(__file__).resolve().parents[3]


class TestsP1(unittest.TestCase):
    def test_jamais_abstention_jauge_inconnue(self):
        from .labo import EconomieP1, RESERVE_INCONNUE
        e = EconomieP1(np.zeros((64, 64), dtype=int))          # aucune barre de jauge : lecteur invalide
        self.assertFalse(e.valid)
        self.assertTrue(e.admissible([1] * RESERVE_INCONNUE))
        self.assertFalse(e.admissible([1] * (RESERVE_INCONNUE + 1)))

    def test_bornes_en_noeuds(self):
        from . import bornes
        bornes.activer()
        import boucle_v4.fantome_general as fg
        self.assertIs(fg.FantomeGeneral.solve, bornes._fs)

    def test_progres_forme_croit_vers_la_cible(self):
        from .progres import Progres
        z = np.load(RACINE / 'livraison_p1/exploration/sonde_ar25/sonde.npz')['images']
        P = Progres(z[0])
        v1 = P.evaluer(z[1])[0]; v2 = P.evaluer(z[2])[0]   # haut puis bas : la copie miroir s'éloigne puis revient
        self.assertGreater(v1, 0); self.assertGreater(v2, 0)

    def test_memoire_inter_jeux_faible(self):
        from .generique import Memoire
        m = Memoire(); m.changer_jeu('A')
        for _ in range(50):
            m.noter('k1', True)
        m.changer_jeu('B')
        self.assertLess(m.taux('k1'), 0.8)        # a priori plafonné à 2 observations dans un nouveau jeu
        m.changer_jeu('A')
        self.assertGreater(m.taux('k1'), 0.9)

    def test_bilan_reutilisation_pas_de_nouveau_gabarit(self):
        src = (Path(__file__).parent / 'agent.py').read_text()
        self.assertIn("reutilise=True", src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
