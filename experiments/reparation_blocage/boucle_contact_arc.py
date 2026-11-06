"""Essai préinscrit : SDK boîte noire, préfixe vérifié, films, révision et replanification."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
PAQUET = ICI / 'paquet'
sys.path[:0] = [str(PAQUET), str(PAQUET / 'livraison_p1/code'),
               str(PAQUET / 'references/astra4/livraison_astra4/ajouts')]

from agent_p1.labo import LaboP1
from chaine_coherente import Chaine
from contact_observe import PerceptionContact, induire, programme

from chrysalide.arc3.moteur import CODES, NOMS
from chrysalide.langue import vers_python
from chrysalide.qwen.images import images_coup


def sauver(path, valeur):
    def donnees(v):
        if isinstance(v, dict):
            return {str(k): donnees(x) for k, x in v.items()}
        if isinstance(v, (list, tuple, set, frozenset)):
            return [donnees(x) for x in v]
        return v
    path.write_text(json.dumps(donnees(valeur), ensure_ascii=False, indent=2, default=repr) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sortie', type=Path, required=True)
    ap.add_argument('--pause-divergence', action='store_true')
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=False)
    racine_jeux = Path('/Users/ts/models/chrysalide3/experiments/G/publics20c')
    if any((racine_jeux / j).exists() for j in ('vc33', 'tu93', 'wa30', 's5i5', 'cn04')):
        raise ValueError('Temoins presents')
    reference = ICI / 'runs/arc_integre_ref_g2/m0r0/N1'
    rows = json.loads((reference / 'partie.json').read_text())['rows']
    with np.load(reference / 'partie.npz') as archive:
        images_reference = archive['images']
    sauver(a.sortie / 'commande.json', {'argv': sys.argv, 'reference': str(reference),
        'sha_sources': {n: hashlib.sha256((ICI / n).read_bytes()).hexdigest() for n in
                        ('contact_observe.py', 'boucle_contact_arc.py', 'chaine_coherente.py')},
        'budget_n2': 150, 'budget_cpu_s': 30, 'initialisations_sdk': 1})
    lab = LaboP1('m0r0', 1, str(racine_jeux), a.sortie / 'N1/partie')
    journal = []
    debut = time.process_time()
    bilan = {'statut': 'en_cours', 'nouveaux_appels_ia': 0, 'initialisations_sdk': 1,
             'injection_niveau': False, 'projection': 'geometrie ; pas une prediction RGB complete'}
    coups_n1 = 0
    appels_step = 0
    try:
        assert np.array_equal(lab.image, images_reference[0]), 'Etat initial different'
        for i, row in enumerate(rows):
            appels_step += 1
            if row['action'] == 0:
                lab.reset_apres_defaite(purpose='acces_niveau_depuis_trace')
            else:
                lab.play(row['action'], purpose='acces_niveau_depuis_trace')
            coups_n1 = len(lab.rows)
            assert np.array_equal(lab.image, images_reference[i + 1]), f'Prefixe different au coup {i+1}'
        assert lab.won and lab.rows[-1]['levels_completed'] == 1
        h = induire(lab.images, [r['action'] for r in lab.rows], lab.won)
        sauver(a.sortie / 'hypothese_depuis_n1.json', h)
        lab = lab.next_level(a.sortie / 'N2/partie')
        debut = time.process_time()
        revision, prudente = 0, False
        while len(lab.rows) < 150 and not lab.finished and time.process_time() - debut < 30:
            perception = PerceptionContact(h, prudente)
            p = programme(h, lab.images[0])
            lots = [{'actions': [{'action': NOMS[r['action']]}]} for r in lab.rows]
            c = Chaine(perception, p, [g.tolist() for g in lab.images], lots,
                       [(NOMS[k],) for k in range(1, 5)], coups_deja_joues=len(lab.rows), reserve=150,
                       films=[lab.films.get('film_' + str(t+1)) for t in range(len(lab.rows))])
            c.activer_atms()
            (a.sortie / f'modele_revision_{revision}.py').write_text(vers_python(p))
            controle, courant = c.rejouer()
            journal.append({'type': 'rejeu', 'revision': revision, 'controle': controle})
            if courant is None:
                bilan['statut'] = 'reparation_refusee_au_rejeu'
                break
            plan = c.proposer(secondes=min(3, max(.001, 30 - (time.process_time() - debut))))
            journal.append({'type': 'plan', 'revision': revision, 'resultat': plan})
            print(json.dumps({'revision': revision, 'statut_plan': plan['statut'],
                'longueur': len(plan.get('plan', {}).get('actions', []))}), flush=True)
            if plan['statut'] != 'plan_simule_valide':
                bilan['statut'] = 'aucun_plan_valide'
                break
            actions = plan['plan']['actions']
            divergence = False
            for rang, action in enumerate(actions):
                if len(lab.rows) >= 150 or time.process_time() - debut >= 30:
                    bilan['statut'] = 'budget'
                    break
                if rang:
                    r = c.adopter_plan(actions[rang:])
                    if r['statut'] != 'plan_simule_valide':
                        bilan['statut'] = 'suffixe_refuse'
                        break
                _, courant = c.rejouer()
                pc, sc = courant
                pc.step(sc, tuple(action))
                prediction = c.perception.rendu(sc)
                avant = lab.image.copy()
                appels_step += 1
                image, film = lab.play(CODES[action[0]], purpose=f'plan_contact_revision_{revision}')
                if lab.finished:
                    journal.append({'type': 'fin_sdk', 'coup': len(lab.rows), 'gagne': lab.won,
                                    'levels_completed': lab.rows[-1]['levels_completed'], 'issue_predite': sc.issue})
                    bilan['statut'] = 'victoire_reelle' if lab.won else 'defaite_reelle'
                    break
                r = c.observer(tuple(action), image, source='jeu', film=film)
                journal.append({'type': 'observation', 'coup': len(lab.rows), **r})
                if r['statut'] != 'transition_confirmee':
                    divergence = True
                    dossier = a.sortie / f'divergence_{revision}'
                    dossier.mkdir()
                    sauver(dossier / 'film.json', c.films.analyser(-1))
                    for i, page in enumerate(c.films.planches(-1)):
                        (dossier / f'film_{i}.png').write_bytes(page)
                    (dossier / 'projection.png').write_bytes(images_coup(
                        c.perception.vue(avant), c.perception.vue(image), prediction)[1])
                    sauver(dossier / 'atms.json', c.atms.rapport())
                    print(json.dumps({'divergence': str(dossier), 'coup': len(lab.rows), **r}), flush=True)
                    sauver(a.sortie / 'journal.json', journal)
                    if a.pause_divergence:
                        input('Film sauvegarde. ENTREE pour evaluer la reparation preinscrite.\n')
                    break
            if lab.finished:
                break
            if not divergence:
                bilan['statut'] = bilan['statut'] if bilan['statut'] != 'en_cours' else 'plan_fini_sans_victoire'
                break
            if prudente or revision >= 4:
                bilan['statut'] = 'nouveau_mecanisme_requis'
                break
            prudente, revision = True, revision + 1
        if bilan['statut'] == 'en_cours':
            bilan['statut'] = 'budget'
    except Exception as e:
        bilan.update(statut='erreur', erreur=repr(e))
        raise
    finally:
        n2 = len(lab.rows) if lab.level == 2 else 0
        bilan.update(coups_n1=coups_n1, coups_n2=n2, coups_reels=coups_n1+n2,
                     appels_step_tentes=appels_step,
                     appels_avec_initialisation=coups_n1+n2+1, cpu_n2_s=time.process_time()-debut,
                     niveaux_gagnes=int(coups_n1 == len(rows) and (lab.level == 2 or lab.won))
                                      + int(lab.level == 2 and lab.won))
        sauver(a.sortie / 'journal.json', journal)
        sauver(a.sortie / 'bilan.json', bilan)
        print(json.dumps(bilan), flush=True)


if __name__ == '__main__':
    main()
