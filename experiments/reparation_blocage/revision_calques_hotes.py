"""Hypothèse locale de calques par rôle hôte, admise seulement par rejeu exact.

Réutilise les classes de formes et les calques observés existants ; aucun nom
de jeu, couleur, coordonnée ni suffixe n'entre dans la proposition.
"""
import copy

from chaine_coherente import Chaine
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique.faits import reclasser_formes


def reviser(source, grilles, lots, films=None):
    """Retourne une chaîne admise ou None, et le diagnostic du préfixe fourni.

    L'appelant conserve le contexte d'export utilisé par sa théorie (par exemple
    le choix d'attribution d'hôte par boîte), comme pour toute réexportation.
    """
    def chaine(vue, programme):
        return Chaine(vue, programme, grilles, lots, source.actions,
                      coups_deja_joues=len(lots), reserve=source.limite,
                      films=films, origine='revision_calques_hotes_prefixe')

    controle_avant, ancien = chaine(source.perception, source.programme).rejouer()
    diag = {'admis': False, 'prefixe_actions': len(lots),
            'controle_avant': controle_avant, 'hypothese': 'hotes_devant_non_hotes',
            'promotion_durable': False}
    if ancien is not None:
        return None, dict(diag, refus='aucune_divergence')
    vue = copy.deepcopy(source.perception)
    th, tr = vue.th_releve, vue.tr
    if getattr(tr, '_carte', None):
        return None, dict(diag, refus='classes_comportement_a_reaffecter')
    if not th.porteur or not th.hotes:
        return None, dict(diag, refus='role_hote_absent')
    # Les lois doivent déjà porter sur le marqueur ; ne pas déplacer implicitement
    # une loi couleur vers seulement quelques objets de cette couleur.
    classes = {c for c, _ in th.hotes}
    dependances = ({c for c, _ in th.moves} | set(th.poussables) |
                   set(th.solides) | set(th.autonomes))
    if classes & dependances or th.peint_contact:
        return None, dict(diag, refus='lois_classe_a_reaffecter')
    init = tr.etats[0]
    occupees = {o[0] for o in init} | set(tr.formes.values())
    fm = {}
    for c, f in sorted(th.hotes, key=lambda q: (q[0], tuple(sorted(q[1])))):
        if any(o[0] == c and (o[0], o[1]) not in th.hotes for o in init):
            libre = next((k for k in range(272 + c % 16, 512, 16)
                          if k not in occupees), None)
            if libre is None:
                return None, dict(diag, refus='classes_formes_epuisees')
            fm[c, f] = libre
            occupees.add(libre)
    if not fm:
        return None, dict(diag, refus='aucune_classe_partagee')
    couches = th.couches()
    # Le marqueur reste au-dessus ; seuls les objets non marqueurs imposent
    # le plancher de la couche commune des hôtes.
    autres = [couches(o[0]) for o in init
              if (o[0], o[1]) not in th.hotes and o[0] != th.porteur[0]]
    decalage = max(0, max(autres, default=0) + 1 - min(couches(c) for c in classes))
    calques = {fm.get((c, f), c): couches(c) + decalage for c, f in th.hotes}
    tr.formes.update(fm)
    tr.etats = [reclasser_formes(e, fm) for e in tr.etats]
    tr._bruts = [reclasser_formes(e, fm) for e in tr._bruts]
    th.hotes = frozenset((fm.get((c, f), c), f) for c, f in th.hotes)
    th.calques_observes.update(calques)
    vue._couches = th.couches()
    for k in ('_index_tr', '_index'):
        vue.__dict__.pop(k, None)
    programme, non = exporter(th, tr.taille)
    if non:
        return None, dict(diag, refus='export_incomplet')
    candidat = chaine(vue, programme)
    controle, courant = candidat.rejouer()
    diag.update(controle=controle, admis=courant is not None,
                classes_raffinees=len(fm), but_conserve=th.but == source.perception.th_releve.but,
                mouvements_conserves=th.moves == source.perception.th_releve.moves)
    if courant is None:
        return None, diag
    candidat.activer_atms()
    return candidat, diag
