"""Boucle réelle avec questions descendantes et élimination prospective des calques."""
import argparse
import hashlib
import json
import time
from pathlib import Path

from boucle_contact_arc import sauver

# Ce module prépare les chemins du paquet avant les imports d'agent.
from boucle_objets_variables import ICI, LaboP1
from chaine_coherente import Chaine
from objets_variables import ObjetsVariables
from perception_guidee import proposer_calques, questions

from chrysalide.arc3.moteur import CODES, NOMS
from chrysalide.langue import vers_python


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sortie', type=Path, required=True)
    ap.add_argument('--jeu', choices=('ar25', 'ka59'), default='ar25')
    args = ap.parse_args()
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    sauver(out/'sources.json', {n: hashlib.sha256((ICI/n).read_bytes()).hexdigest() for n in
           ('boucle_perception_guidee.py', 'perception_guidee.py', 'objets_variables.py')})
    lab = LaboP1(args.jeu, 1, '/Users/ts/models/chrysalide3/experiments/G/publics20c', out/'N1/partie')
    t = time.process_time()
    journal = []
    bilan = {'jeu': args.jeu, 'statut': 'en_cours', 'initialisations_sdk': 1, 'appels_ia': 0, 'injection_niveau': False}
    appels = 0
    try:
        for a in [1, 2, 3, 4]*2:
            appels += 1
            lab.play(a, purpose='sonde_generique')
            if lab.finished:
                bilan['statut'] = 'fin_sondes'
                return
        candidats = []
        for contact in (False, True):
            v = ObjetsVariables(lab.images, [r['action'] for r in lab.rows], contact=contact)
            sauver(out/f'questions_contact_{contact}.json', questions(v, [NOMS[k] for k in range(1, 5)]))
            for but in v.buts:
                p = v.programme(but)
                c = Chaine(v, p, [g.tolist() for g in lab.images],
                    [{'actions': [{'action': NOMS[r['action']]}]} for r in lab.rows],
                    [(NOMS[k],) for k in range(1, 5)], coups_deja_joues=len(lab.rows), reserve=80)
                plan = c.proposer(secondes=3)
                journal.append({'type': 'selection_perception', 'contact': contact, 'plan': plan})
                if plan['statut'] == 'plan_simule_valide':
                    candidats = [('initial', c)]
                    (out/'programme.py').write_text(vers_python(p))
                    break
            if candidats:
                break
        if not candidats:
            bilan['statut'] = 'aucun_modele'
            return
        repare = False
        while len(lab.rows) < 80 and time.process_time()-t < 30:
            plans = [(nom, c, c.proposer(secondes=3)) for nom, c in candidats]
            if any(plan['statut'] != 'plan_simule_valide' or not plan['plan']['actions'] for _, _, plan in plans):
                bilan['statut'] = 'hypothese_sans_plan'
                break
            choix = {tuple(plan['plan']['actions'][0]) for _, _, plan in plans}
            if len(choix) != 1:
                bilan['statut'] = 'actions_ambigues'
                break
            action = next(iter(choix))
            journal.append({'type': 'action_commune', 'coup': len(lab.rows)+1,
                            'hypotheses': [n for n, _ in candidats], 'action': action})
            appels += 1
            image, film = lab.play(CODES[action[0]], purpose='plan_perception_guidee')
            if lab.finished:
                bilan['statut'] = 'victoire_reelle' if lab.won else 'defaite_reelle'
                journal.append({'type': 'fin_sdk', 'coup': len(lab.rows), 'levels_completed': lab.rows[-1]['levels_completed']})
                break
            survivants = []
            for nom, c in candidats:
                c.activer_atms()
                r = c.observer(action, image, source='jeu', film=film)
                journal.append({'type': 'verification', 'coup': len(lab.rows), 'hypothese': nom, **r})
                if r['statut'] == 'transition_confirmee':
                    survivants.append((nom, c))
                else:
                    sauver(out/f'revocation_{nom}_{len(lab.rows)}.json', c.atms.rapport())
            if survivants:
                candidats = survivants
                continue
            if repare:
                bilan['statut'] = 'reparation_refutee'
                break
            candidats, dossier = proposer_calques(v, p, [g.tolist() for g in lab.images],
                                                 [(NOMS[r['action']],) for r in lab.rows])
            sauver(out/'diagnostic_contact.json', dossier)
            print(json.dumps({'coup_reparation': len(lab.rows), 'candidats': [n for n, _ in candidats]}), flush=True)
            repare = True
            if not candidats:
                bilan['statut'] = 'aucune_reparation'
                break
        if bilan['statut'] == 'en_cours':
            bilan['statut'] = 'budget'
        bilan['hypotheses_finales'] = [n for n, _ in candidats]
    except ValueError as e:
        bilan.update(statut='refus', raison=str(e))
    finally:
        bilan.update(coups_reels=len(lab.rows), appels_step_tentes=appels,
                     appels_avec_initialisation=appels+1, cpu_s=time.process_time()-t,
                     niveaux_gagnes=int(lab.won))
        sauver(out/'bilan.json', bilan)
        sauver(out/'journal.json', journal)
        print(json.dumps(bilan), flush=True)


if __name__ == '__main__':
    main()
