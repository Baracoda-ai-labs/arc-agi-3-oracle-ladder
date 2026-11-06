"""Prototype local : révélation d'un trou et ancrage observé d'une sélection."""
import copy
import os
from contextlib import contextmanager

import numpy as np

from chaine_coherente import Chaine
from chrysalide.arc3.moteur import NOMS
from chrysalide.arc3.logique.faits import cellules
from chrysalide.arc3.logique.theorie import porteuse
from chrysalide.arc3.logique.export_langage import exporter


@contextmanager
def porteur_boite():
    ancien = os.environ.get('CHRYS_PORTEUR_BOITE')
    os.environ['CHRYS_PORTEUR_BOITE'] = '1'
    try:
        yield
    finally:
        if ancien is None:
            os.environ.pop('CHRYS_PORTEUR_BOITE', None)
        else:
            os.environ['CHRYS_PORTEUR_BOITE'] = ancien


def reviser(source, avant, apres, action, film=None):
    vue = copy.deepcopy(source.perception)
    vue.contexte_export = {**getattr(vue, 'contexte_export', {}), 'CHRYS_PORTEUR_BOITE': '1'}
    th, tr = vue.th_releve, vue.tr
    if not th.porteur or action != (NOMS[th.porteur[1]],):
        raise ValueError('Une sélection observée est requise')
    monde = tr.etats[0]
    marqueurs = [o for o in monde if o[0] == th.porteur[0]]
    if len(marqueurs) != 1:
        raise ValueError('Marqueur source ambigu')
    m0 = marqueurs[0]
    p0, p1 = vue.vue(avant), vue.vue(apres)
    with porteur_boite():
        h0 = porteuse(monde, m0, {c for c, _ in th.hotes})
        if h0 is None:
            raise ValueError('Hôte source absent')
        x, y = m0[2:]
        trou = (x-h0[2], y-h0[3])
        if p1[y, x] != tr.fond or trou not in h0[1]:
            raise ValueError('Aucun trou révélé sous le marqueur')
        reste = cellules(h0) - {(x, y)}
        if any(p0[v, u] != p1[v, u] for u, v in reste):
            raise ValueError('La forme hôte a aussi changé : diagnostic distinct requis')
        h0_repare = (h0[0], h0[1]-{trou}, h0[2], h0[3])
        monde = tuple(h0_repare if o == h0 else o for o in monde)
        # Le parseur existant classe le marqueur dans la boîte d'une pièce creuse.
        observes = tr.etat(apres)
        marqueurs1 = [o for o in observes if o[0] == th.porteur[0]]
        if len(marqueurs1) != 1:
            raise ValueError('Marqueur après sélection ambigu')
        m1 = marqueurs1[0]
        h1 = porteuse(monde, m1, {c for c, _ in th.hotes})
        if h1 is None or h1[0] == h0[0]:
            raise ValueError('Nouvel hôte non identifié')
        parametre = (h0_repare[1], h1[1], (m1[2]-h1[2], m1[3]-h1[3]))
        th.saut_sel = tuple(q for q in th.saut_sel if q[0] != h0_repare[1]) + (parametre,)
        th.hotes = frozenset((c, h0_repare[1] if c == h0[0] and f == h0[1] else f)
                            for c, f in th.hotes)
        tr.etats = [monde]
        tr._bruts = [monde]
        for k in ('_index_tr', '_index'):
            vue.__dict__.pop(k, None)
        programme, non = exporter(th, tr.taille)
        if non:
            raise ValueError('Export incomplet : ' + repr(non))
        c = Chaine(vue, programme, [np.asarray(avant).tolist(), np.asarray(apres).tolist()],
            [{'actions': [{'action': action[0]}]}], source.actions,
            coups_deja_joues=1, reserve=source.limite, films=[film],
            origine='revision_perception_selection_prefixe')
        controle, courant = c.rejouer()
    diag = {'controle': controle, 'admis': courant is not None,
        'prefixe_actions': 1, 'trou_revele_classe': h0[0],
        'point_revele': [x, y], 'hote_selectionne_classe': h1[0],
        'ancrage_observe': list(parametre[2]),
        'mouvements_conserves': th.moves == source.perception.th_releve.moves,
        'porteur_conserve': th.porteur == source.perception.th_releve.porteur,
        'parametre_saut_sel_provisoire': True,
        'forme_complete_hote_cible_connue': False,
        'but_conserve': th.but == source.perception.th_releve.but}
    if courant is not None:
        c.activer_atms()
    return c, diag
