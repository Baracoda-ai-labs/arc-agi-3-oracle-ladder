# SPDX-License-Identifier: MIT-0
# ruff: noqa: C408
"""Paires d'actions INDÉPENDANTES déduites de l'ontologie v1 (CW-410, B + G) : entrée de la réduction par ordre partiel.

Deux actions a et b sont déclarées indépendantes (a·b et b·a mènent au même état) si, pour les mécanismes qu'elles
déclenchent (y compris les effets déclenchés à chaque coup effectif : autonomes, horloge, jauge) :
  ecrit(a) ∩ lit(b) = ∅,  ecrit(b) ∩ lit(a) = ∅,  et  ecrit(a) ∩ ecrit(b) ⊆ fluents à écriture COMMUTATIVE.
Écriture commutative : jauge (somme des coûts ; vrai tant que la réserve finale reste au-dessus du seuil, car la
réserve intermédiaire est alors au-dessus aussi) et attribut cyclique (suivant mod n, même opération des deux côtés).
Une lecture d'un fluent commutatif par l'autre action (seuil de défaite, test de cycle) ne casse pas l'indépendance si
c'est la règle de fin de coup qui lit (vérifiée après les deux) : c'est le cas de `defaite_epuisement`.
Bibliothèque sans vérité : la correspondance action → mécanismes vient de la théorie du niveau (ou, au banc, du
diagnostic), jamais d'ici."""
from itertools import combinations

from chrysalide.langue.ontologie_formelle import MECANISMES

COMMUTATIFS = frozenset({"jauge", "attr_cyclique"})
# Pseudo-mécanismes hors MECANISMES : économie (ECONOMIE) et état cyclique (mémoire globale, 7 jeux sur 20).
EXTRA = {"economie": dict(lit=["jauge"], ecrit=["jauge"]),
         "etat_cyclique": dict(lit=["pos", "attr_cyclique"], ecrit=["attr_cyclique"]),
         "annulation": dict(lit=["historique", "pos", "attr", "present"], ecrit=["pos", "attr", "present", "historique"]),
         "lancement": dict(lit=["pos", "attr", "present", "selection"], ecrit=["pos", "attr", "present", "issue"])}
LUS_PAR_FIN_DE_COUP = frozenset({"jauge"})


def contrat(nom):
    m = MECANISMES.get(nom) or EXTRA[nom]
    return set(m["lit"]), set(m["ecrit"])


def effet(mecanismes, toujours=()):
    """(lit, ecrit) d'une action qui déclenche `mecanismes`, plus les mécanismes `toujours` (phase 3–4, à chaque coup)."""
    lit, ecrit = set(), set()
    for n in [*mecanismes, *toujours]:
        lu, e = contrat(n)
        lit |= lu
        ecrit |= e
    # un mécanisme déclenché à chaque coup lit l'historique du coup (ordre des actions) s'il rejoue un trajet
    if any(n in ("memoire_fantome", "autonome_couloir") for n in toujours):
        lit |= {"action", "historique"}
        ecrit |= {"historique"}
    return lit, ecrit


def _commutent(la, ea, lb, eb):
    # lire un fluent commutatif pour l'incrémenter soi-même (suivant mod n, jauge − coût) n'est pas une dépendance
    lus_a = la - LUS_PAR_FIN_DE_COUP - (ea & COMMUTATIFS)
    lus_b = lb - LUS_PAR_FIN_DE_COUP - (eb & COMMUTATIFS)
    return not (ea & lus_b or eb & lus_a) and (ea & eb) <= COMMUTATIFS


def independantes(ma, mb, toujours=()):
    """a·T·b·T contre b·T·a·T (T = mécanismes déclenchés à chaque coup) : a et b commutent entre eux ET chacun avec T."""
    if not ma or not mb:  # effets inconnus ≠ sans effet : prudence
        return False
    la, ea = effet(ma)
    lb, eb = effet(mb)
    if not _commutent(la, ea, lb, eb):
        return False
    if toujours:
        lt, et = effet([], toujours)
        return _commutent(la, ea, lt, et) and _commutent(lb, eb, lt, et)
    return True


def paires_independantes(actions, toujours=()):
    """`actions` : {nom_action: [mécanismes]} → liste triée des paires (a, b) déclarées indépendantes."""
    return sorted((a, b) for a, b in combinations(sorted(actions), 2)
                  if independantes(actions[a], actions[b], toujours))


TRANSLATIONS = frozenset({"deplacement", "blocage", "economie"})


def conditionnelle(ma, mb, toujours=()):
    """Paire dépendante par la seule position, entre deux TRANSLATIONS (flèches) : elles commutent si chacun des quatre
    pas (a puis b, b puis a) est libre. Test à faire à l'état par le planificateur (un pas de plus), pas une loi."""
    if independantes(ma, mb, toujours) or not ma or not mb or toujours and set(toujours) - {"economie"}:
        return None
    if set(ma) <= TRANSLATIONS and set(mb) <= TRANSLATIONS:
        return "les quatre pas sont libres (aucun blocage dans un ordre ni dans l'autre)"
    return None
