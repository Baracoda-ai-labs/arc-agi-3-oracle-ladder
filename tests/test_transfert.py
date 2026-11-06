"""D (CW-234) : transfert d'une théorie quand les couleurs changent d'un niveau à l'autre."""
from types import SimpleNamespace

from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.logique.transfert import couleurs, renommer, transferer

UN = frozenset({(0, 0)})


def test_renommer_tous_les_champs():
    th = Theorie(moves={(2, 1): (0, -1)}, solides=frozenset({9}), poussables=frozenset({3}), bascule={4: 5, 5: 4},
                 zone=7, consomme=frozenset({(2, 6)}), but=("sortie", 2, 6))
    t2 = renommer(th, {9: 11, 6: 13, 7: 14})
    assert t2.solides == {11} and t2.consomme == {(2, 13)} and t2.zone == 14 and t2.but == ("sortie", 2, 13)
    assert t2.moves == th.moves and couleurs(th) == {2, 3, 4, 5, 6, 7, 9}


def test_transferer_choisit_la_bonne_couleur():
    """Niveau courant : la couleur 4 de la théorie n'existe plus, la 8 est nouvelle ; la bascule 4↔5 devient 8↔5."""
    th = Theorie(motif=frozenset({(0, 0)}), bascule={4: 5, 5: 4})
    tr = SimpleNamespace(etats=[((8, UN, 1, 1), (5, UN, 3, 3))], exclues=frozenset())

    def rejeu(t_, _tr):
        return (2 if t_.bascule == {8: 5, 5: 8} else 0, 2)
    t2, m, ok = transferer(th, tr, rejeu)
    assert m == {4: 8} and ok == 2 and t2.bascule == {8: 5, 5: 8}


def test_rien_ne_manque_rien_ne_change():
    th = Theorie(bascule={4: 5})
    tr = SimpleNamespace(etats=[((4, UN, 1, 1), (5, UN, 3, 3))], exclues=frozenset())
    t2, m, _ = transferer(th, tr, lambda t_, _tr: (0, 1))
    assert m == {} and t2 is th
