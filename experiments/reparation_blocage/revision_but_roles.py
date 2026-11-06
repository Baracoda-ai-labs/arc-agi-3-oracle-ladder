"""Révoquer une issue contredite sans réinduire les lois de déplacement."""
import copy
import numpy as np
from chaine_coherente import Chaine, empreinte
from transfert_roles import RolesReaffectes


def couverture(vue):
    """Correspondances de supports observés ; leur rôle n'est pas une vérité."""
    groupes = {}
    for s in vue.statiques:
        # Les couches de sol révélé ne proposent pas de nouvelles cibles.
        if s.get('couche', 0) < 0:
            continue
        px = np.asarray(s['pixels'])
        couleurs = set(map(int, np.unique(px))) - {-1}
        if len(couleurs) != 1 or px.size >= np.asarray(vue.image).size:
            continue
        support = px >= 0
        cle = (support.shape, support.tobytes())
        groupes.setdefault(cle, []).append((s, next(iter(couleurs))))
    hypotheses = []
    for groupe in groupes.values():
        couleurs = sorted({col for _, col in groupe})
        if len(couleurs) < 2:
            continue
        for col in couleurs:
            cibles = [s for s, couleur in groupe if couleur == col]
            autres = [s for s, couleur in groupe if couleur != col]
            if not cibles or not autres:
                continue
            h, w = np.asarray(cibles[0]['pixels']).shape
            deja = {(x, y, ww, hh) for x, y, ww, hh, _ in vue.cibles}
            centres = [(int(s['x']), int(s['y']), w, h) for s in cibles]
            hypotheses.append({'forme': [h, w], 'classe_cible_candidate': col,
                'centres': centres, 'couverts': sum(t in deja for t in centres),
                'non_couverts': sum(t not in deja for t in centres),
                'correspondants': [(int(s['x']), int(s['y'])) for s in autres],
                'role_non_confirme': True,
                'pieces_actuelles_de_meme_forme': sum(np.asarray(p['pixels']).shape == (h,w) for p in vue.pieces)})
    return hypotheses


def proposer(source):
    diagnostic = {'admis': False, 'but_confirme': False, 'nouvelle_physique': False}
    if type(source.perception) is not RolesReaffectes:
        return None, {**diagnostic, 'refus': 'perception_non_supportee'}
    preuves = source.contre_exemples
    if (not source.refute or not preuves or
            any(p.get('statut') != 'but_refute' or p.get('differences') != [] for p in preuves)):
        return None, {**diagnostic, 'refus': 'refutation_image_exacte_requise'}
    p = copy.deepcopy(source.programme)
    buts = [r for r in p['regles'] if r.get('nom') == 'toutes_cibles_hypothese']
    if len(buts) != 1 or buts[0].get('alors') != [['niveau_suivant']]:
        return None, {**diagnostic, 'refus': 'regle_terminale_non_supportee'}
    ancien = buts[0]
    p['regles'].remove(ancien)
    vue = copy.deepcopy(source.perception)
    vue.programme_transfere = copy.deepcopy(p)
    c = Chaine(vue, p, source.grilles, source.lots, source.actions,
        coups_deja_joues=source.coups, reserve=source.limite,
        films=[e['images'] if e else None for e in source.films.entrees])
    controle, etat = c.rejouer()
    if etat is None or not all(controle.get(k) for k in
            ('catalogue_shacl', 'traduction_python', 'rejeu', 'compilation_fidele')):
        return None, {**diagnostic, 'refus': 'dynamique_non_admise', 'controle': controle}
    c.activer_atms()
    c.but_inconnu = True
    c.preuve_revision_but = {'source': source.signature(), 'but_refute': ancien,
        'contre_exemples': copy.deepcopy(preuves), 'dynamique_sha': empreinte(p)}
    hypotheses = couverture(vue)
    return c, {**diagnostic, 'admis': True, 'controle': controle,
        'but_refute': ancien, 'dynamique_sha': empreinte(p),
        'couverture_hypotheses': hypotheses, 'candidats_buts_admis': [],
        'plan': None, 'raison': 'but_inconnu_roles_supplementaires_non_etablis',
        'limite': 'Correspondance de formes seulement ; aucune mobilite ni cible nouvelle certifiee.'}
