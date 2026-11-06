"""Un appel préinscrit : outil d'analyse temporelle, tests réservés, aucun environnement de jeu."""
import json
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / 'paquet'), str(ICI)]
from client_multimodal import generer
from propositions_python import Proposition

PROMPT = '''Ecris un outil Python pur dans notre langage existant.
Renvoie uniquement ce code, sans Markdown :
PROGRAMME = Programme(regles=[], fonctions={"compter_transitions": {"params": ["films"], "expr": "EXPRESSION PYTHON"}})
films est une liste d'images aplaties de meme longueur, chaque image est une liste d'entiers.
L'outil rend le nombre TOTAL de cellules qui changent entre CHAQUE paire d'images consecutives.
Un retour a l'image initiale compte donc aussi les changements intermediaires.
Film vide ou une seule image : 0. Ne pas comparer seulement premiere et derniere images.
Exemples : [[0],[1],[0]] -> 2 ; [[2,2],[2,2]] -> 0.
Expression pure autorisee : sum, len, range, min, max, abs, int, compréhensions, indexation,
comparaisons, additions. Pas d'import, d'attribut, de zip, de enumerate, de fonction externe.
Programme est notre constructeur declaratif ; il n'est pas a importer. Ne genere aucune regle de jeu.'''


def attendu(film):
    total = 0
    for i in range(1, len(film)):
        for a, b in zip(film[i - 1], film[i], strict=True):
            total += a != b
    return total


def main():
    sortie = ICI / 'essai_outil_27b'
    sortie.mkdir(exist_ok=False)
    (sortie / 'prompt.txt').write_text(PROMPT)
    films = [[], [[]], [[3]], [[0, 0], [1, 1]], [[0, 0], [1, 0], [0, 0]],
             [[3, 4, 5], [3, 4, 5], [6, 4, 7], [6, 0, 7]],
             [[0], [1], [0], [1]], [[1, 2], [3, 4], [5, 6]]]
    cas = [((f,), attendu(f)) for f in films]
    (sortie / 'cas_reserves.json').write_text(json.dumps(films))
    bilan = {'appels_ia': 1, 'nouveaux_appels_sdk': 0, 'modele': 'qwen3.8:27b-mlx',
             'gain_arc': False, 'statut': 'non_termine'}
    debut = time.monotonic()
    try:
        code, metriques = generer(PROMPT, num_predict=512, num_ctx=8192, timeout=45)
        (sortie / 'reponse_brute.txt').write_text(code)
        bilan['metriques'] = metriques
        p = Proposition(code)
        bilan['verification'] = p.tester_outil('compter_transitions', cas)
        bilan['statut'] = bilan['verification']['statut']
    except (ValueError, SyntaxError, TypeError, RuntimeError, OSError) as e:
        bilan.update(statut='refus_ou_erreur', erreur=repr(e))
    bilan['mur_total_s'] = time.monotonic() - debut
    (sortie / 'bilan.json').write_text(json.dumps(bilan, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in bilan.items() if k != 'metriques'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
