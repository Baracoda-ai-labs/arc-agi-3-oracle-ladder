"""Couverture géométrique candidate, distincte des preuves de dynamique et de but."""
from chrysalide.arc3.logique.theorie import cells, centres_motifs, roles_motif
from extension_but_relationnel import proposer


def diagnostiquer(th, tr, grilles, preuves_dynamique=()):
    """Ne révise rien. Les centres supplémentaires ne sont pas des cibles certifiées.

    preuves_dynamique : résultats d'observation du seul modèle examiné.
    L'absence d'extension ne prouve jamais la complétude de son alphabet.
    """
    buts, preuves = proposer(th, tr, grilles)
    monde = tr.etat(grilles[-1]) if len(grilles) else ()
    col = {p: o[0] for o in monde for p in cells(o)}
    bases = [b for b in th.buts_motifs if b[0] == 'motif_rel' and len(b) == 3]
    if th.but and th.but[0] == 'motif_rel' and len(th.but) == 3:
        bases.append(th.but)
    lignes = []
    for base in dict.fromkeys(bases):
        couverts = set(centres_motifs(col, set(base[1:])))
        candidats = []
        for but, preuve in zip(buts, preuves):
            if tuple(preuve['base']) != base:
                continue
            centres = set(centres_motifs(col, set(roles_motif(*but[1:]))))
            candidats.append({'but': but, 'centres_candidats': len(centres),
                'centres_non_couverts_par_base': len(centres-couverts),
                'positions_non_couvertes': sorted(centres-couverts),
                'role_propose': preuve['role_propose'], 'roles_non_confirmes': True,
                **({'role_neutre': 'hypothese_non_confirmee'} if preuve['role_propose']=='neutre' else {}),
                'but_confirme': False})
        non_couverts = {tuple(p) for c in candidats for p in c['positions_non_couvertes']}
        lignes.append({'base': base, 'centres_couverts': len(couverts),
            'positions_couvertes': sorted(couverts),
            'centres_non_couverts_candidats': len(non_couverts),
            'diagnostic_alphabet': 'incomplet_possible' if non_couverts else 'indetermine',
            'extensions': candidats})
    exactes = sum(p.get('image_exacte') is True and p.get('pixels_ecart', 0) == 0
                  for p in preuves_dynamique)
    ecarts = sum(p.get('image_exacte') is False or p.get('pixels_ecart', 0) > 0
                 for p in preuves_dynamique)
    dynamique = ('refutee_sur_observations' if ecarts else
                 'compatible_sur_observations' if exactes else 'non_evaluee')
    return {'observations_images': len(grilles), 'couverture': lignes,
        'dynamique': {'statut': dynamique, 'images_exactes': exactes,
                     'images_en_ecart': ecarts, 'preuve_universelle': False},
        'promotion_durable': False, 'but_confirme': False,
        'limite': 'Couverture relative aux extensions proposees ; ni exhaustivite ni neutralite prouvee.'}
