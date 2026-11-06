from types import SimpleNamespace

from operateurs_memoire import AvecMemoire, verifier_retours


def base():
    s = ((0, 0), frozenset(), ("continue",), 0)
    return SimpleNamespace(
        depart=s,
        offre=[6, 7],
        horizon=4,
        actions=lambda s: [("clic", 1, 1)] if s[3] < 4 else [],
        pas=lambda s, a: (s[0], s[1] | {(1, 1)}, s[2], s[3] + 1),
    )


def test_annulation_comptee_et_pas_nouvel_etat_physique():
    b = base()
    m = AvecMemoire(b, 7, "N1", "N1")
    s = m.pas(m.depart, ("clic", 1, 1))
    r = m.pas(s, 7)
    assert r[0][:3] == b.depart[:3] and r[0][3] == 2 and r[1] == ()


def test_pas_transfert_n2_ni_action_non_offerte():
    b = base()
    m = AvecMemoire(b, 7, "N2", "N1")
    s = m.pas(m.depart, ("clic", 1, 1))
    assert 7 not in m.actions(s)
    b.offre = [6]
    m = AvecMemoire(b, 7, "N1", "N1")
    assert 7 not in m.actions(m.pas(m.depart, ("clic", 1, 1)))


def test_pas_retour_apres_terminal():
    m = AvecMemoire(base(), 7, "N1", "N1")
    s = m.pas(m.depart, ("clic", 1, 1))
    terminal = ((s[0][0], s[0][1], ("defaite",), s[0][3]), s[1])
    assert 7 not in m.actions(terminal)


def test_reutilisation_pile_ignore_actions_inertes():
    assert verifier_retours(["a", "b", "b", "a"], ["clic", "inerte", 7], 7) == [{"index": 2, "conforme": True}]


def test_retour_de_position_non_deduit_des_clics_sans_deplacement():
    b = base()
    b.pas = lambda s, a: ((0, -2), s[1] | {(1, 1)}, s[2], s[3] + 1)
    m = AvecMemoire(b, 7, "N1", "N1")
    current = m.pas(m.depart, ("clic", 1, 1))
    assert 7 not in m.actions(current)
    assert m.pas(current, 7) is None
    # Une preuve indépendante est requise pour élargir cette dimension.
    extended = AvecMemoire(b, 7, "N1", "N1", position_restauree=True)
    current = extended.pas(extended.depart, ("clic", 1, 1))
    restored = extended.pas(current, 7)
    assert restored[0][0] == b.depart[0] and restored[0][3] == 2
    assert not AvecMemoire(b, 7, "N3", "N1", position_restauree=True).autorise


def test_preuve_mouvement_ne_generalise_pas_aux_autres_codes():
    b = base()
    b.offre = [3, 4, 7]
    b.actions = lambda s: [3, 4] if s[3] < 4 else []
    b.pas = lambda s, a: ((s[0][0] + (-1 if a == 3 else 1), -2), s[1], s[2], s[3] + 1)
    m = AvecMemoire(
        b, 7, "contexte_mesure", "contexte_mesure", familles=("mouvement",), position_restauree=True, actions_validees=(4,)
    )
    moved = m.pas(m.depart, 4)
    restored = m.pas(moved, 7)
    assert restored[0][0] == b.depart[0]
    assert restored[0][3] == 2
    other = m.pas(m.depart, 3)
    assert 7 not in m.actions(other)
