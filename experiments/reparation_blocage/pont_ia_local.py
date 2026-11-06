"""Connexion locale au bras Patch existant ; observations archivées uniquement."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / 'paquet'), str(ICI / 'paquet/livraison_p1/code')]

from agent_p1.releve_moteur import _lot

from chrysalide.arc3.moteur import MoteurC, _exporter, nom_action, porte
from chrysalide.langue import appliquer_patch, lire_reponse, vers_python


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modele', default='qwen3:4b-instruct-2507-q4_K_M')
    ap.add_argument('--sortie', default='ia_patch_arc')
    ap.add_argument('--delai', type=float, default=90)
    args = ap.parse_args()
    sortie = ICI / args.sortie
    sortie.mkdir(exist_ok=False)
    base = ICI / 'runs/arc_blocage_terminale_g1/m0r0'
    meta = json.loads((base / 'journal_jeu.jsonl').read_text().splitlines()[0])
    for k in list(os.environ):
        if k.startswith('CHRYS_'):
            del os.environ[k]
    os.environ.update(meta['env'])
    images = np.load(base / 'N2/partie.npz')['images']
    rows = json.loads((base / 'N2/partie.json').read_text())['rows']
    grilles = [g.tolist() for g in images[80:126]]
    lots = [_lot(r['action']) for r in rows[80:125]]
    m = MoteurC(budget=30)
    proposition = m.proposer({'grilles': grilles[:41], 'lots': lots[:40], 'precedents': []})
    assert proposition is not None
    programme = proposition[1]
    depart = porte(m, programme, grilles[:41], lots[:40])
    assert depart is not None, 'Ancien blocage export non leve : aucun appel IA'
    prog, sc = depart
    observations = []
    for t in range(40, 45):
        avant = m.vue(grilles[t])
        reel = m.vue(grilles[t + 1])
        prog.step(sc, nom_action(lots[t]['actions'][0]))
        pred = m.rendu(sc)
        faux = np.argwhere(pred != reel)
        observations.append({'action': lots[t]['actions'][0], 'ecart_pixels': len(faux),
                             'differences': [{'y': int(y), 'x': int(x), 'avant': int(avant[y, x]),
                                              'predit': int(pred[y, x]), 'observe': int(reel[y, x])}
                                             for y, x in faux[:64]],
                             'issue_predite': sc.issue})
    # Contrôle positif déjà établi : contre-exemple contextuel, pas une règle de jeu écrite à la main.
    th = copy.deepcopy(m.th_plan)
    monde = m.tr.etats[0]
    for a in m.tr.actions + [r['action'] for r in rows[120:124]]:
        monde, _ = th.pas(monde, a, m.tr.taille)
    th.sans_effet = th.sans_effet | {th.cle_sans_effet(monde, rows[124]['action'], m.tr.taille)}
    positif, non = _exporter(th, m.tr.taille)
    controle = {'parent_fenetre': True, 'parent_avec_contre_exemple': porte(m, programme, grilles, lots) is not None,
                'positif_avec_contre_exemple': not non and porte(m, positif, grilles, lots) is not None}
    (sortie / 'controle.json').write_text(json.dumps(controle, indent=2))
    assert not controle['parent_avec_contre_exemple'] and controle['positif_avec_contre_exemple']
    prompt = ('Tu proposes une correction minimale de regles pour un simulateur de jeu. '
              'Le programme ci-dessous rejoue exactement les 40 coups anterieurs. '
              'Les cinq observations suivantes incluent un contre-exemple. '
              'Corrige sans casser les coups anterieurs. Pas de copie d image ni de regle memorisant les pixels. '
              'Utilise uniquement les constructeurs et mots du programme. '
              'Reponds en Python declaratif, sans fonction ni import reel : '
              'REPONSE = Reponse(patch=Patch(retire=["nom"], ajoute=[Regle(...)]), explique=["raison"]) '
              'ou REPONSE = Abstention(raison="..."). Les noms retires doivent exister.\n\n'
              + vers_python(programme) + '\nObservations :\n' + json.dumps(observations, ensure_ascii=False))
    (sortie / 'invite.txt').write_text(prompt)
    spec = importlib.util.spec_from_file_location('qwen_local', '/Users/ts/qwenn-horizon/harnais/qwen_local.py')
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    t0 = time.monotonic()
    reponse, metriques = client.generer(prompt, modele=args.modele,
                                       num_predict=1024, num_ctx=8192, timeout=args.delai)
    (sortie / 'reponse.txt').write_text(reponse)
    bilan = {'controle': controle, 'metriques': metriques, 'mur_s': time.monotonic() - t0,
             'mode': 'trace, zero action SDK', 'victoire_reelle': False, 'accepte': False,
             'modele': args.modele, 'invite_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
    try:
        blocs = re.findall(r'```(?:python)?\s*\n(.*?)```', reponse, re.DOTALL)
        lu = lire_reponse(blocs[0] if blocs else reponse)
        bilan['lecture'] = lu
        if 'patch' in lu:
            noms = {r.get('nom') for r in programme['regles']}
            if set(lu['patch'].get('retire', [])) - noms:
                raise ValueError('Retrait de regle inconnue')
            corrige = appliquer_patch(programme, lu['patch'])
            bilan['accepte'] = porte(m, corrige, grilles, lots) is not None
            if bilan['accepte']:
                # Evaluation uniquement : ces cinq transitions n'ont pas ete envoyees au modele.
                bilan['suite_reservee_exacte'] = porte(m, corrige,
                    [g.tolist() for g in images[80:131]], [_lot(r['action']) for r in rows[80:130]]) is not None
            (sortie / 'programme_propose.json').write_text(json.dumps(corrige, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, SyntaxError) as e:
        bilan['refus'] = str(e)
    (sortie / 'bilan.json').write_text(json.dumps(bilan, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in bilan.items() if k != 'lecture'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
