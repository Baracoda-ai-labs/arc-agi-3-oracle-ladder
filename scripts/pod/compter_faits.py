# SPDX-License-Identifier: MIT-0
"""SUR LE POD (ABBA RO / ROF, revue Codex 29/10) : exposition réelle des faits épinglés dans un passage.

Lit les journaux de requêtes du harnais (`*requests.jsonl`, gzip compris), garde les seules lignes `event=request`
(contenu PRÉPARÉ pour l'envoi, écrit juste avant l'appel réseau : ce n'est pas la preuve d'une réponse réussie), et
compte, par jeu, les requêtes dont le DERNIER message utilisateur contient le bloc « OBSERVED FINAL FRAMES » : une
répétition du bloc dans l'historique d'une requête suivante n'est pas une nouvelle injection.
Usage : python3 compter_faits.py <dossier du passage>  → JSON {jeu: {requetes, avec_faits}, total…}"""
import gzip
import json
import sys
from pathlib import Path

MARQUE = 'OBSERVED FINAL FRAMES'


def _texte(contenu):
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        return ''.join(p.get('text', '') for p in contenu if isinstance(p, dict))
    return ''


def compter(dossier):
    par_jeu = {}; fichiers = 0
    for f in sorted(Path(dossier).rglob('*requests.jsonl*')):
        ouvrir = gzip.open if f.suffix == '.gz' else open
        jeu = f.name.split('_requests')[0] if '_requests' in f.name else f.parent.name
        c = par_jeu.setdefault(jeu, {'requetes': 0, 'avec_faits': 0, 'premieres_requetes_avec_faits': 0,
                                     'rang_indetermine_avec_faits': 0, 'illisibles': 0})
        fichiers += 1
        with ouvrir(f, 'rt', errors='replace') as flux:
            for ligne in flux:
                try:
                    r = json.loads(ligne)
                except json.JSONDecodeError:
                    c['illisibles'] += 1
                    continue
                if r.get('event') != 'request':
                    continue
                c['requetes'] += 1
                users = [m for m in (r.get('messages') or []) if isinstance(m, dict) and m.get('role') == 'user']
                if users and MARQUE in _texte(users[-1].get('content')):
                    c['avec_faits'] += 1
                    rang = r.get('request_index_within_turn')
                    if rang == 1:  # 1re requête du tour (le harnais numérote à partir de 1 ; une reprise après yield
                        c['premieres_requetes_avec_faits'] += 1  # peut aussi avoir le rang 1 sans nouvelle action)
                    elif rang is None:
                        c['rang_indetermine_avec_faits'] += 1
    cles = ('requetes', 'avec_faits', 'premieres_requetes_avec_faits', 'rang_indetermine_avec_faits', 'illisibles')
    total = {k: sum(v[k] for v in par_jeu.values()) for k in cles}
    # Zéro fichier ou des lignes illisibles ne prouvent PAS l'absence de faits : verdict « indéterminé » dans ce cas.
    return {'par_jeu': par_jeu, 'total': total, 'fichiers_lus': fichiers, 'jeux': len(par_jeu),
            'verdict_possible': fichiers > 0 and total['illisibles'] == 0}


if __name__ == '__main__':
    print(json.dumps(compter(sys.argv[1]), ensure_ascii=False))
