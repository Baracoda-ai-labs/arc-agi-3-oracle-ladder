"""Adaptateur optionnel d'annulation observée, borné au contexte et à l'offre."""

from chrysalide.arc3.logique.induction import precedent_pile


def verifier_retours(etats, actions, code):
    return [
        {"index": i, "conforme": etats[i + 1] == precedent_pile(etats, actions, i, code)}
        for i, a in enumerate(actions)
        if a == code
    ]


class AvecMemoire:
    def __init__(
        self, base, code, contexte, contexte_appris, familles=("clic",), position_restauree=False, actions_validees=None
    ):
        self.base = base
        self.code = code
        self.autorise = contexte == contexte_appris and code in base.offre
        self.familles = set(familles)
        self.position_restauree = position_restauree
        self.actions_validees = None if actions_validees is None else set(actions_validees)
        self.depart = (base.depart, ())

    def actions(self, s):
        current, pile = s
        out = list(self.base.actions(current))
        if (
            self.autorise
            and pile
            and pile[-1] is not None
            and (self.position_restauree or current[0] == pile[-1][0])
            and current[3] < self.base.horizon
            and all(v == "continue" for v in current[2])
        ):
            out.append(self.code)
        return out

    def pas(self, s, a):
        if a not in self.actions(s):
            return None
        current, pile = s
        if a == self.code:
            ancien = pile[-1]
            return ((*ancien[:3], current[3] + 1), pile[:-1])
        new = self.base.pas(current, a)
        if new is None:
            return None
        famille = "clic" if isinstance(a, (list, tuple)) else "mouvement"
        # Une famille non étayée bloque le retour : pas de transfert implicite.
        if new[:3] != current[:3]:
            action_couverte = self.actions_validees is None or a in self.actions_validees
            pile = (*pile, current if famille in self.familles and action_couverte else None)
        return (new, pile)
