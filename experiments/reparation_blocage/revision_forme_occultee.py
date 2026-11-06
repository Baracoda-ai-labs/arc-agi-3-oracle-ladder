"""Complétion provisoire d'une forme dont un fragment vient d'être découvert.

Le fragment doit prolonger un hôte connu, avoir été couvert initialement par
un autre hôte déplacé, puis passer le rejeu exact de tout le préfixe.
"""
import copy
import numpy as np
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import _codes_c
from chrysalide.arc3.logique.theorie import cells, VOISINS8
from chrysalide.arc3.logique.export_langage import exporter


def reviser(source, grilles, lots, films=None):
    def chaine(vue, programme):
        return Chaine(vue, programme, grilles, lots, source.actions,
                      coups_deja_joues=len(lots), reserve=source.limite,
                      films=films, origine='revision_forme_occultee_prefixe')
    controle, etat = chaine(source.perception, source.programme).rejouer()
    diag = {'admis': False, 'controle_avant': controle, 'prefixe_actions': len(lots),
            'hypothese': 'forme_revelee_derriere_hote_mobile', 'promotion_durable': False}
    if etat is not None:
        return None, dict(diag, refus='aucune_divergence')
    vue = copy.deepcopy(source.perception)
    th, tr = vue.th_releve, vue.tr
    actions = _codes_c(lots)
    if not th.porteur or not th.hotes or actions is None or tr._carte:
        return None, dict(diag, refus='representation_non_prise_en_charge')
    initial = tr.etats[0]
    monde = initial
    for action in actions:
        monde, _ = th.pas(monde, action, tr.taille)
    pred = th.rendu(monde, tr.taille, tr.fond)
    observe = vue.vue(grilles[-1])
    erreurs = np.argwhere(pred != observe)
    if not len(erreurs):
        return None, dict(diag, refus='divergence_non_finale')
    ajouts, contraintes = {}, set()
    def couleur(c):
        return c % 16 if c >= 16 else c
    for y, x in erreurs:
        x, y = int(x), int(y)
        if pred[y, x] != tr.fond or observe[y, x] == tr.fond:
            return None, dict(diag, refus='ecart_non_revelation')
        voisins = {(x+dx, y+dy) for dx, dy in VOISINS8}
        candidats = [o for o in monde if (o[0], o[1]) in th.hotes
                     and couleur(o[0]) == observe[y, x] and cells(o) & voisins]
        if len(candidats) != 1:
            return None, dict(diag, refus='hote_revele_ambigu')
        o = candidats[0]
        origines = [a for a in initial if a[:2] == o[:2]]
        if len(origines) != 1:
            return None, dict(diag, refus='identite_forme_ambigue')
        origine = origines[0]
        dx, dy = x-o[2], y-o[3]
        if dx < 0 or dy < 0:
            return None, dict(diag, refus='changement_ancrage_non_pris_en_charge')
        cache = (origine[2]+dx, origine[3]+dy)
        supports = [h for h in initial if h != origine and (h[0], h[1]) in th.hotes
                    and cache in cells(h) and any(q[:2] == h[:2] and q[2:] != h[2:] for q in monde)]
        if len(supports) != 1 or supports[0][0] == origine[0]:
            return None, dict(diag, refus='occultation_initiale_non_etablie')
        ajouts.setdefault(origine[:2], set()).add((dx, dy))
        contraintes.add((supports[0][0], origine[0]))
    formes = {(c, f): f | ajouts.get((c, f), set()) for c, f in th.hotes}
    changement = {f: formes[c, f] for c, f in ajouts}
    if any(f in changement and formes[c, f] != changement[f] for c, f in th.hotes):
        return None, dict(diag, refus='forme_partagee_ambigue')
    tr.etats = [tuple((o[0], formes.get(o[:2], o[1]), *o[2:]) for o in e) for e in tr.etats]
    tr._bruts = [tuple((o[0], formes.get(o[:2], o[1]), *o[2:]) for o in e) for e in tr._bruts]
    for (c, f), code in list(tr.formes.items()):
        if (code, f) in formes:
            tr.formes[c, formes[code, f]] = code
    th.hotes = frozenset((c, formes[c, f]) for c, f in th.hotes)
    th.saut_sel = tuple((changement.get(f0, f0), changement.get(f1, f1), p)
                       for f0, f1, p in th.saut_sel)
    th.formes = {c: changement.get(f, f) for c, f in th.formes.items()}
    # La case nouvellement complétée était réellement cachée : le couvrant
    # doit être devant. Les calques existants portent déjà cette contrainte.
    for _ in range(len(contraintes)+1):
        change = False
        for dessus, dessous in sorted(contraintes):
            couche = th.couches()
            if couche(dessus) <= couche(dessous):
                th.calques_observes[dessus] = couche(dessous)+1
                change = True
        if not change:
            break
    else:
        return None, dict(diag, refus='contraintes_calques_cycliques')
    vue._couches = th.couches()
    for k in ('_index_tr', '_index'):
        vue.__dict__.pop(k, None)
    programme, non = exporter(th, tr.taille)
    if non:
        return None, dict(diag, refus='export_incomplet')
    candidat = chaine(vue, programme)
    controle, courant = candidat.rejouer()
    diag.update(controle=controle, admis=courant is not None,
                pixels_completes=sum(map(len, ajouts.values())),
                contraintes_calques=len(contraintes),
                but_conserve=th.but == source.perception.th_releve.but,
                mouvements_conserves=th.moves == source.perception.th_releve.moves)
    if courant is None:
        return None, diag
    candidat.activer_atms()
    return candidat, diag
