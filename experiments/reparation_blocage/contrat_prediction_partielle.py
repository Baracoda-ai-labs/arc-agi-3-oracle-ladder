"""Portée explicite d'une hypothèse ; les attributs hors portée restent inconnus."""
import copy


def contrat_relation(attente):
    return {'action': copy.deepcopy(attente['action']),
            'objets': {'forme': copy.deepcopy(attente['forme'])},
            'attributs': ['positions_visibles', 'population_visible'],
            'sources': copy.deepcopy(attente['sources']),
            'destination': copy.deepcopy(attente['destination']),
            'abstentions': ['autres_objets', 'couleurs', 'images_intermediaires',
                            'navigation', 'consommation', 'but'],
            'statut': 'hypothese_provisoire', 'but_certifie': False}


def verifier(contrat, avant, action, apres, issue='continue'):
    """Réutilise la perception de formes ; aucune complétion silencieuse du monde."""
    from relation_clic_observee import positions
    resultat = {'statut': 'abstention', 'exact': None, 'modele_complet': False,
                'but_certifie': False, 'abstentions': list(contrat['abstentions'])}
    if action != contrat['action']:
        return {**resultat, 'raison': 'action_hors_perimetre'}
    if issue != 'continue':
        return {**resultat, 'raison': 'frontiere_issue_scene_non_comparable'}
    forme = frozenset(map(tuple, contrat['objets']['forme']))
    depart = positions(avant, forme)
    sources = set(map(tuple, contrat['sources']))
    if not sources <= depart:
        return {**resultat, 'raison': 'sources_non_identifiees'}
    attendu = (depart - sources) | {tuple(contrat['destination'])}
    observe = positions(apres, forme)
    exact = attendu == observe
    return {**resultat, 'statut': 'confirme_partiellement' if exact else 'refute_dans_perimetre',
            'exact': exact, 'attendu': sorted(map(list, attendu)),
            'observe': sorted(map(list, observe)),
            'attributs_verifies': list(contrat['attributs'])}
