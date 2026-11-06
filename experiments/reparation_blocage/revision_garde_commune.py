"""Hypothèse de mouvement conjoint, depuis un arrêt observé ; aucune loi universelle."""
import copy
import numpy as np
from chaine_coherente import Chaine
from objets_variables import ObjetsVariables
from chrysalide.arc3.langage import Programme


def parametrer(base, programme):
    """Factorise les gardes existantes, avant les mouvements séquentiels."""
    if not any(programme == base.programme(b) for b in base.buts):
        raise ValueError('programme_hors_contrat')
    p = copy.deepcopy(programme)
    groupes = {}
    for r in p['regles']:
        if r['nom'].startswith('mouvement_'):
            boucle = r['alors'][0]
            groupes.setdefault(r['quand'][2], []).append((r, boucle))
    gardes = []
    for i, (action, groupe) in enumerate(groupes.items()):
        if len(groupe) < 2:
            continue
        nom = 'garde_commune_' + str(i)
        if nom in p['etat']:
            raise ValueError('etat_deja_utilise')
        p['etat'][nom] = False
        condition = ['et', *[['tous', b[1], copy.deepcopy(b[2]), copy.deepcopy(b[3][0][1])]
                              for _, b in groupe]]
        gardes.append({'nom': nom, 'phase': -1, 'quand': copy.deepcopy(groupe[0][0]['quand']),
                       'alors': [['poser', nom, condition]]})
        for _, b in groupe:
            b[3][0][1] = ['et', ['etat', nom], b[3][0][1]]
    p['regles'] = gardes + p['regles']
    return p


def proposer(source):
    diag = {'admis': False, 'hypothese': 'garde_commune', 'provisoire': True,
            'generalisation': False, 'mouvements_changes': False, 'but_change': False,
            'perception_changee': False}
    def refus(raison, **infos):
        return None, {**diag, 'refus': raison, **infos}
    base = source.perception
    while hasattr(base, 'base'):
        base = base.base
    if type(base) is not ObjetsVariables or len(source.lots) < 1:
        return refus('representation_non_applicable')
    if not np.array_equal(source.perception.vue(source.grilles[-2]), source.perception.vue(source.grilles[-1])):
        return refus('observation_non_immobile')
    avant, apres = map(np.asarray, source.grilles[-2:])
    if any(tuple(map(int, p)) not in base.hud for p in np.argwhere(avant != apres)):
        return refus('changement_natif_hors_masque')
    if any(len(l['actions']) != 1 for l in source.lots):
        return refus('lots_non_atomiques')
    try:
        programme = parametrer(base, source.programme)
        pc = Programme(source.programme)
        sc = source.perception.scene(source.grilles[0])
        for lot, image in zip(source.lots[:-1], source.grilles[1:-1], strict=True):
            pc.step(sc, source.action_tuple(lot['actions'][0]))
            if not np.array_equal(source.perception.rendu(sc), source.perception.vue(image)):
                return refus('ancien_contre_exemple')
        def positions():
            return {(tuple(s['tags'])): (s['x'], s['y']) for s in sc.sprites
                    if any(t.startswith('mobile_') for t in s['tags'])}
        pre = positions()
        pc.step(sc, source.action_tuple(source.lots[-1]['actions'][0]))
        post = positions()
        if pre.keys() != post.keys():
            return refus('objets_changes')
        mobiles = [post[k] != pre[k] for k in pre]
        if not any(mobiles) or all(mobiles):
            return refus('pas_de_separation_predite')
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return refus('contrat_non_applicable', detail=str(exc))
    c = Chaine(copy.deepcopy(source.perception), programme, source.grilles, source.lots,
               source.actions, coups_deja_joues=source.coups, reserve=source.limite,
               films=[e['images'] if e else None for e in source.films.entrees])
    controle, etat = c.rejouer()
    if etat is None or not all(controle.get(k) for k in
                              ('catalogue_shacl', 'traduction_python', 'rejeu', 'compilation_fidele')):
        return refus('rejeu_prefixe', controle=controle)
    c.activer_atms()
    c.contraste_revision = copy.deepcopy(source.programme)
    c.revision_locale = {'operateur': 'garde_commune', 'portee': 'prefixe_observe',
                         'provisoire': True, 'generalisation': False}
    return c, {**diag, 'admis': True, 'controle': controle}
