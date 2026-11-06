"""Essai prospectif : sondes sans victoire, classification, induction, plan, SDK."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
PAQUET = ICI/'paquet'
sys.path[:0] = [str(PAQUET), str(PAQUET/'livraison_p1/code'),
               str(PAQUET/'references/astra4/livraison_astra4/ajouts')]

from agent_p1.labo import LaboP1
from boucle_contact_arc import sauver
from chaine_coherente import Chaine
from objets_variables import ObjetsVariables
from ontologie_extensible import _familles

from chrysalide.arc3.moteur import CODES, NOMS
from chrysalide.langue import vers_python


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sortie', type=Path, required=True)
    out = ap.parse_args().sortie
    out.mkdir(parents=True, exist_ok=False)
    sauver(out/'sources.json', {n: hashlib.sha256((ICI/n).read_bytes()).hexdigest()
                               for n in ('objets_variables.py', 'boucle_objets_variables.py')})
    lab = LaboP1('ar25', 1, '/Users/ts/models/chrysalide3/experiments/G/publics20c', out/'N1/partie')
    bilan = {'statut': 'en_cours', 'appels_ia': 0, 'initialisations_sdk': 1, 'injection_niveau': False}
    journal = []
    t = time.process_time()
    try:
        for a in [1, 2, 3, 4]*2:
            lab.play(a, purpose='sonde_generique')
            if lab.finished:
                bilan['statut'] = 'fin_pendant_sondes'
                return
        c = None
        plan = {'statut': 'aucun_plan'}
        for contact in (False, True):
            v = ObjetsVariables(lab.images, [r['action'] for r in lab.rows], contact=contact)
            for cible in v.buts:
                if time.process_time()-t > 30:
                    break
                p = v.programme(cible)
                c = Chaine(v, p, [g.tolist() for g in lab.images],
                    [{'actions': [{'action': NOMS[r['action']]}]} for r in lab.rows],
                    [(NOMS[k],) for k in range(1, 5)], coups_deja_joues=len(lab.rows), reserve=80)
                plan = c.proposer(secondes=3)
                journal.append({'type': 'proposition', 'contact_candidat': contact,
                                'cible': cible, 'resultat': plan})
                if plan['statut'] == 'plan_simule_valide':
                    (out/'programme.py').write_text(vers_python(p))
                    break
            if plan['statut'] == 'plan_simule_valide':
                break
        if c is None or plan['statut'] != 'plan_simule_valide':
            bilan['statut'] = 'aucun_plan'
            return
        bilan.update(objets_mobiles=len(v.mobiles), buts_candidats=len(v.buts),
                     contact_candidat=v.contact)
        f = _familles()
        signaux = f.signaux_depuis_objets([{'roles': ['controle']} for _ in v.mobiles] +
                                         [{'roles': ['cible']} for _ in v.buts],
                                         [NOMS[k] for k in range(1, 5)])
        sauver(out/'classification.json', {'statut': 'hypotheses_conditionnelles',
            'signaux': vars(signaux), 'familles': f.reconnaitre(signaux),
            'limite': 'Cibles supposées par forme ; scores non calibrés, aucun droit action'})
        c.activer_atms()
        actions = plan['plan']['actions']
        print(json.dumps({'mobiles': len(v.mobiles), 'longueur_plan': len(actions)}), flush=True)
        for rang, action in enumerate(actions):
            if len(lab.rows) >= 80 or time.process_time()-t > 30:
                bilan['statut'] = 'budget'
                break
            if rang and c.adopter_plan(actions[rang:])['statut'] != 'plan_simule_valide':
                bilan['statut'] = 'suffixe_refuse'
                break
            image, film = lab.play(CODES[action[0]], purpose='plan_objets_variables')
            if lab.finished:
                bilan['statut'] = 'victoire_reelle' if lab.won else 'defaite_reelle'
                break
            r = c.observer(action, image, source='jeu', film=film)
            journal.append({'coup': len(lab.rows), **r})
            if r['statut'] != 'transition_confirmee':
                bilan['statut'] = 'divergence'
                sauver(out/'film.json', c.films.analyser(-1))
                for i, page in enumerate(c.films.planches(-1)):
                    (out/f'film_{i}.png').write_bytes(page)
                break
        if bilan['statut'] == 'en_cours':
            bilan['statut'] = 'plan_sans_victoire'
    except ValueError as e:
        bilan.update(statut='modele_refuse', raison=str(e))
    finally:
        bilan.update(coups_reels=len(lab.rows), appels_avec_initialisation=len(lab.rows)+1,
                     niveaux_gagnes=int(lab.won), cpu_s=time.process_time()-t)
        sauver(out/'bilan.json', bilan)
        sauver(out/'journal.json', journal)
        print(json.dumps(bilan), flush=True)


if __name__ == '__main__':
    main()
