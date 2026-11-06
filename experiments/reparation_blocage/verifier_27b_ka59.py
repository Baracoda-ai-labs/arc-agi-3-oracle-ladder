"""Vérifie les sorties brutes du 27B sans les corriger ni exécuter du Python libre."""
import argparse
import json
import resource
import sys
from pathlib import Path

import numpy as np

ICI_BOOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI_BOOT/"paquet"), str(ICI_BOOT)]

from chaine_coherente import Chaine
from essai_27b_ka59_outils import ICI, OUT
from objets_variables import ObjetsVariables
from propositions_python import Proposition

from chrysalide.arc3.moteur import NOMS
from chrysalide.langue import depuis_python


def verifier(numero, grilles=None, actions=None):
    resource.setrlimit(resource.RLIMIT_CPU, (10, 12))
    r = ICI/'runs/guidage_ka59_fige1/N1'
    if grilles is None:
        with np.load(r/'partie.npz') as z:
            grilles = z['images'].copy().tolist()
        actions = [(NOMS[x['action']],) for x in json.loads((r/'partie.json').read_text())['rows']]
    try:
        raw = json.loads((OUT/f'reponse_{numero}.json').read_text())
    except json.JSONDecodeError as e:
        return {'statut': 'format_refuse', 'erreur': str(e), 'experience': None}
    bilan = {'diagnostic_non_verifie': raw.get('diagnostic'), 'experience': None}
    code = raw.get('outil_python', '')
    if code:
        try:
            outil = Proposition(code)
            resultat = outil.appeler('analyse', [np.asarray(g).ravel().tolist() for g in grilles], [a[0] for a in actions])
            texte = json.dumps(resultat, ensure_ascii=False)
            (OUT/f'resultat_outil_{numero}.json').write_text(texte)
            bilan['outil'] = {'statut': 'execute_non_certifie', 'resultat': texte[:5000], 'tronque': len(texte)>5000}
        except Exception as e:  # noqa: BLE001 — refus mécanique consigné
            bilan['outil'] = {'statut': 'refuse', 'erreur': repr(e)}
    code = raw.get('experience_python', '')
    if code:
        try:
            experience = Proposition(code).experience
            if experience is None or len(experience['actions'])>3:
                raise ValueError('Expérience bornée à 1–3 actions requise')
            bilan['experience'] = experience
        except Exception as e:  # noqa: BLE001 — refus mécanique consigné
            bilan['experience_refusee'] = repr(e)
    code = raw.get('programme_python', '')
    if code:
        try:
            p = depuis_python(code)
            if len(code)>16000:
                raise ValueError('Programme trop long')
            base = ObjetsVariables(grilles[:9], [next(k for k,v in NOMS.items() if v==a[0]) for a in actions[:8]])
            lots = [{'actions': [{'action': a[0], **({'row':a[1],'col':a[2]} if len(a)==3 else {})}]} for a in actions]
            c = Chaine(base,p,grilles,lots,sorted(set(actions)))
            bilan['modele'] = c.rejouer()[0]
        except Exception as e:  # noqa: BLE001 — pas de correction du modèle
            bilan['modele'] = {'statut': 'refuse', 'erreur': repr(e)}
    return bilan


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('numero',type=int);a=ap.parse_args()
    b=verifier(a.numero);(OUT/f'controle_{a.numero}.json').write_text(json.dumps(b,ensure_ascii=False,indent=2))
    print(json.dumps(b,ensure_ascii=False))
