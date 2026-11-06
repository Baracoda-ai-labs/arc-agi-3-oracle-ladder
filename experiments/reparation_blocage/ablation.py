"""Diagnostic borné : retirer une règle, jamais inventer une loi de jeu."""
import copy
import time


def diagnostiquer(chaine, secondes=5):
    debut = time.process_time()
    bilan = {'statut': 'modele_non_refute', 'candidats': [], 'essais': [],
             'preuve_impossibilite': False, 'nouveaux_appels_sdk': 0}
    if not chaine.refute:
        return bilan, []
    admissibles = []
    regles = chaine.programme.get('regles', [])
    for index, regle in enumerate(regles):
        if time.process_time() - debut >= secondes:
            break
        programme = copy.deepcopy(chaine.programme)
        del programme['regles'][index]
        controle, courant = chaine.rejouer(programme)
        ok = courant is not None and controle['catalogue_shacl']
        ligne = {'index': index, 'regle': regle.get('nom'), 'admissible': ok,
                 'controle': controle}
        bilan['essais'].append(ligne)
        if ok:
            # Révision isolée : aucune mutation de la référence ni promotion en loi vraie.
            candidat = copy.deepcopy(chaine)
            nom = regle.get('nom')
            revision = candidat.patch(f'REPONSE = Reponse(patch=Patch(retire={[nom]!r}, ajoute=[]))')
            if revision['statut'] != 'patch_valide_sur_observations' or candidat.programme != programme:
                ligne['admissible'] = False
                ligne['refus_revision'] = revision
                continue
            candidat.origine = 'hypothese_ablation_non_confirmee'
            admissibles.append(candidat)
            bilan['candidats'].append({'index': index, 'regle_retiree': regle.get('nom')})
    bilan.update(cpu_s=time.process_time() - debut, regles_total=len(regles),
                 exploration_complete=len(bilan['essais']) == len(regles),
                 statut='ambigu' if len(admissibles) > 1 else
                        'hypothese_unique' if admissibles else 'aucune_reparation_trouvee')
    return bilan, admissibles
