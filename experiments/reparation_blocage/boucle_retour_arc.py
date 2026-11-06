"""Validation prospective d'une règle apprise sur un film archivé, SDK boîte noire."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
PAQUET = ICI / "paquet"
sys.path[:0] = [str(PAQUET), str(PAQUET / "livraison_p1/code"),
               str(PAQUET / "references/astra4/livraison_astra4/ajouts")]

from agent_p1.labo import LaboP1
from apprendre_retour import apprendre
from boucle_contact_arc import sauver
from chaine_coherente import Chaine
from contact_observe import induire

from chrysalide.arc3.moteur import CODES, NOMS
from chrysalide.langue import vers_python
from chrysalide.qwen.images import images_coup


def charger(niveau):
    base = ICI / 'runs/contact_arc_essai1' / niveau
    with np.load(base / 'partie.npz') as z:
        archive = {k: z[k].copy() for k in z.files}
    rows = json.loads((base / 'partie.json').read_text())['rows']
    return archive, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sortie', type=Path, required=True)
    args = parser.parse_args()
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    a, rows1 = charger('N1')
    b, rows2 = charger('N2')
    h = induire(a['images'], [r['action'] for r in rows1], True)
    perception, programme, apprentissage = apprendre(
        h, b['images'], [r['action'] for r in rows2], b['film_' + str(len(rows2))])
    sauver(out / 'apprentissage.json', apprentissage)
    (out / 'regle.py').write_text(vers_python(programme))
    sauver(out / 'sources.json', {n: hashlib.sha256((ICI/n).read_bytes()).hexdigest()
                                 for n in ('apprendre_retour.py', 'boucle_retour_arc.py', 'contact_observe.py',
                                           'chaine_coherente.py')})
    bilan = {'statut': 'en_cours', 'coups_apprentissage_anterieurs': len(rows1)+len(rows2),
             'initialisations_sdk': 1, 'nouveaux_appels_ia': 0, 'injection_niveau': False}
    journal = []
    lab = None
    coups_n1 = 0
    t = time.process_time()
    tentatives = 0
    try:
        lab = LaboP1('m0r0', 1, '/Users/ts/models/chrysalide3/experiments/G/publics20c', out/'N1/partie')
        assert np.array_equal(lab.image, a['images'][0])
        for i, row in enumerate(rows1):
            tentatives += 1
            if row['action'] == 0:
                lab.reset_apres_defaite(purpose='acces_niveau')
            else:
                lab.play(row['action'], purpose='acces_niveau')
            coups_n1 = len(lab.rows)
            assert np.array_equal(lab.image, a['images'][i+1]), f'Acces divergent {i+1}'
        assert lab.won and lab.rows[-1]['levels_completed'] == 1
        lab = lab.next_level(out/'N2/partie')
        assert np.array_equal(lab.image, b['images'][0])
        c = Chaine(perception, programme, [lab.image.tolist()], [],
                   [(NOMS[k],) for k in range(1, 5)], reserve=150)
        c.activer_atms()
        t = time.process_time()
        plan = c.proposer(secondes=3)
        sauver(out/'plan.json', plan)
        print(json.dumps({'statut_plan': plan['statut'], 'longueur': len(plan.get('plan', {}).get('actions', []))}), flush=True)
        if plan['statut'] != 'plan_simule_valide':
            bilan['statut'] = 'aucun_plan'
            return
        actions = plan['plan']['actions']
        for rang, action in enumerate(actions):
            if len(lab.rows) >= 150 or time.process_time()-t >= 30:
                bilan['statut'] = 'budget'
                break
            if rang and c.adopter_plan(actions[rang:])['statut'] != 'plan_simule_valide':
                bilan['statut'] = 'suffixe_refuse'
                break
            _, etat = c.rejouer()
            pc, sc = etat
            pc.step(sc, tuple(action))
            prediction = c.perception.rendu(sc)
            avant = lab.image.copy()
            tentatives += 1
            image, film = lab.play(CODES[action[0]], purpose='plan_regle_retour_apprise')
            if lab.finished:
                bilan['statut'] = 'victoire_reelle' if lab.won else 'defaite_reelle'
                journal.append({'coup': len(lab.rows), 'statut': bilan['statut'],
                                'levels_completed': lab.rows[-1]['levels_completed'], 'issue_predite': sc.issue})
                break
            c.perception.suivre(lab.images, [r['action'] for r in lab.rows])
            r = c.observer(tuple(action), image, source='jeu', film=film)
            journal.append({'coup': len(lab.rows), **r})
            if r['statut'] != 'transition_confirmee':
                bilan['statut'] = 'divergence'
                sauver(out/'film_divergence.json', c.films.analyser(-1))
                for i, page in enumerate(c.films.planches(-1)):
                    (out/f'film_divergence_{i}.png').write_bytes(page)
                (out/'projection.png').write_bytes(images_coup(perception.vue(avant), perception.vue(image), prediction)[1])
                break
        if bilan['statut'] == 'en_cours':
            bilan['statut'] = 'plan_fini_sans_victoire'
    except Exception as e:
        bilan.update(statut='erreur', erreur=repr(e))
        raise
    finally:
        n2 = len(lab.rows) if lab is not None and lab.level == 2 else 0
        bilan.update(coups_n1=coups_n1, coups_n2=n2, coups_reels=coups_n1+n2,
                     appels_step_tentes=tentatives, appels_avec_initialisation=tentatives+1,
                     cpu_n2_s=time.process_time()-t,
                     victoire_n2=bool(lab is not None and lab.level == 2 and lab.won))
        sauver(out/'bilan.json', bilan)
        sauver(out/'journal.json', journal)
        if 'c' in locals():
            sauver(out/'atms.json', c.atms.rapport())
        print(json.dumps(bilan), flush=True)


if __name__ == '__main__':
    main()
