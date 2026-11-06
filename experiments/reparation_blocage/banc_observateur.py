"""Observateur non bloquant : préfixe seul à l'ouvrier, suffixe évalué dans le parent."""
import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI), str(ICI / 'paquet'), str(ICI / 'paquet/livraison_p1/code')]
from agent_p1.releve_moteur import _lot
from banc_chaine import CAS
from chaine_coherente import Chaine
from moteur_observateur import MoteurObservateur
from observateur_cpu import Observateur, cle_instantane

from chrysalide.arc3.moteur import nom_action
from chrysalide.arc3.moteur_processus import MoteurDistant


def charger(cas):
    run, jeu, niveau, k = cas
    base = (ICI.parents[2] / 'audit/chrysalide_audit_23-10/traces/enregistrements' / jeu
            if run == 'audit' else ICI / 'runs' / run / jeu)
    env = json.loads((base / 'journal_jeu.jsonl').read_text().splitlines()[0])['env']
    for cle in list(os.environ):
        if cle.startswith('CHRYS_'):
            del os.environ[cle]
    os.environ.update(env)
    os.environ.update(CHRYS_REPARATION_BLOCAGE='2', CHRYS_EXPORT_SANS_EFFET='1',
                      CHRYS_CENTRES_RAPIDES='1', CHRYS_PLAN_CONTEXTE_COMPLET='1',
                      CHRYS_MOTEUR_PROCESSUS_DELAI_S='15', CHRYS_MOTEUR_OUVRIERS='2')
    document = json.loads((base / f'N{niveau}/partie.json').read_text())
    archive = np.load(base / f'N{niveau}/partie.npz')
    rows, images = document['rows'], archive['images']
    debut = max(max((i + 1 for i in range(k) if rows[i]['action'] == 0), default=0), k - 40)
    historique = {'grilles': images[debut:k + 1].tolist(),
        'lots': [_lot(r['action']) for r in rows[debut:k]], 'precedents': [],
        'films': [archive[f'film_{t + 1}'].tolist() if f'film_{t + 1}' in archive else None
                  for t in range(debut, k)]}
    archive.close()
    return historique, document, images, {'partie': run + '/' + jeu, 'niveau': niveau, 'coup': k}


def evaluer(resultat, perception, historique, document, images, contexte):
    k = contexte['coup']
    rows = document['rows']
    observations, correspondances = [], []
    for i, prediction in enumerate(resultat.get('predictions', [])):
        t = k + i
        if t >= len(rows):
            break
        action = nom_action(_lot(rows[t]['action'])['actions'][0])
        if tuple(prediction['action']) != action:
            observations.append({'pas': i + 1, 'statut': 'action_differente_non_verifiable'})
            break
        attendue = np.asarray(prediction['image'])
        observe = np.asarray(perception.vue(images[t + 1]))
        pixels = int((attendue != observe).sum()) if attendue.shape == observe.shape else None
        victoire = bool(document['victory']) and t + 1 == len(rows)
        terminal = rows[t]['state'].split('.')[-1] != 'NOT_FINISHED'
        predit = prediction['issue']
        statut = ('victoire_sur_trace' if victoire else
                  'but_refute' if pixels == 0 and predit in ('niveau', 'victoire') and not victoire else
                  'transition_compatible' if pixels == 0 and predit is None and not terminal else 'divergence')
        observations.append({'pas': i + 1, 'pixels_ecart': pixels, 'statut': statut,
                             'issue_predite': predit, 'victoire_observee': victoire})
        if statut != 'transition_compatible':
            break
        correspondances.append(i + 1)
    revalidations = []
    if resultat.get('programme'):
        for age in (0, 1, 2):
            if k + age > len(rows):
                revalidations.append({'age_coups': age, 'statut': 'trace_insuffisante'})
                continue
            # Toutes les actions réelles du suffixe sont rejouées, même différentes du vieux plan.
            h = {**historique,
                'grilles': historique['grilles'] + images[k + 1:k + age + 1].tolist(),
                'lots': historique['lots'] + [_lot(r['action']) for r in rows[k:k + age]]}
            ctx = {**contexte, 'coup': k + age}
            c = Chaine(perception, resultat['programme'], h['grilles'], h['lots'], [],
                       coups_deja_joues=k + age)
            controle, courant = c.rejouer()
            revalidations.append({'age_coups': age, 'perime': age != 0,
                'statut': 'modele_compatible' if courant else 'modele_refute',
                'controle': controle, 'ancien_plan_autorise': False,
                'cle_courante': cle_instantane(h, ctx)})
    return {'observations_reservees': observations, 'revalidations': revalidations}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sortie', type=Path, default=ICI / 'bilan_observateur.json')
    sortie = parser.parse_args().sortie
    if sortie.exists():
        raise FileExistsError(sortie)
    bilan = {'nouveaux_appels_sdk': 0, 'appels_ia': 0, 'gain_franzen_mesure': False, 'cas': []}
    for cas in CAS:
        hist, document, images, ctx = charger(cas)
        avant_cpu_fils = resource.getrusage(resource.RUSAGE_CHILDREN)
        distant = MoteurDistant(MoteurObservateur(budget=2))
        service = Observateur(distant)
        cpu_parent = time.process_time()
        try:
            soumission = service.soumettre(hist, ctx)
            occupe = service.soumettre(hist, ctx)
            polls = 0
            while True:
                rapport = service.lire(soumission['cle'])
                polls += 1
                if rapport['statut'] != 'en_cours':
                    break
                time.sleep(.005)
            resultat = rapport.pop('proposition', None) or {'statut': 'aucune_proposition'}
            perception = resultat.pop('perception_complete', distant._local)
            evaluation = evaluer(resultat, perception, hist, document, images, ctx)
            # Les images prédites brutes ne sont pas nécessaires dans le journal agrégé.
            resume = {k: v for k, v in resultat.items() if k not in ('predictions', 'programme')}
            ligne = {'cas': cas, 'soumission': soumission, 'occupation': occupe,
                'rapport': rapport, 'resultat': resume, 'evaluation': evaluation, 'lectures_sans_attente': polls,
                'cpu_parent_s': time.process_time() - cpu_parent,
                'transport': dict(distant.mesures_processus)}
            bilan['cas'].append(ligne)
            print(json.dumps({'cas': cas, 'statut': resultat['statut'],
                              'soumission_s': soumission['mur_soumission_s'],
                              'mur_s': rapport['mur_depuis_soumission_s'],
                              'observations': evaluation['observations_reservees']}, ensure_ascii=False), flush=True)
        finally:
            service.fermer()
        apres_cpu_fils = resource.getrusage(resource.RUSAGE_CHILDREN)
        ligne['cpu_fils_total_s'] = (apres_cpu_fils.ru_utime + apres_cpu_fils.ru_stime
                                     - avant_cpu_fils.ru_utime - avant_cpu_fils.ru_stime)
        ligne['cpu_parent_s'] = time.process_time() - cpu_parent
        sortie.write_text(json.dumps(bilan, ensure_ascii=False, indent=2, default=repr) + '\n')


if __name__ == '__main__':
    main()
