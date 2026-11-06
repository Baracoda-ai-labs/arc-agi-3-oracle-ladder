"""Bornes de recherche en nœuds pour le code v4 (non modifié) : on enveloppe ses recherches pour neutraliser la limite
en secondes et ne garder que leurs limites en nœuds (`maxnodes`). Les résultats ne dépendent alors plus de la charge machine."""
import boucle_v4.fantome_general as fg
import boucle_v4.poussee_generale as pg

GRAND = 10 ** 9
_fg_solve = fg.FantomeGeneral.solve
_pg_solve = pg.PousseeGenerale.solve
_pg_sub = pg.PousseeGenerale.subgoal


def _fs(self, s=None, seconds=2, maxmacros=5, maxnodes=5000):
    return _fg_solve(self, s, GRAND, maxmacros, maxnodes)


def _ps(self, s=None, seconds=3, maxnodes=80000):
    return _pg_solve(self, s, GRAND, maxnodes)


def _psub(self, s, seconds=2, maxnodes=60000):
    return _pg_sub(self, s, GRAND, maxnodes)


def activer():
    fg.FantomeGeneral.solve = _fs
    pg.PousseeGenerale.solve = _ps
    pg.PousseeGenerale.subgoal = _psub
