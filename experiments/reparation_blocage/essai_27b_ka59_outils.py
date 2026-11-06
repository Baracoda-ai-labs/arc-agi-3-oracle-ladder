"""Dossier factuel et appels bornés ; aucune solution humaine injectée."""
import argparse
import ast
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI/'paquet'), str(ICI)]

from objets_variables import ObjetsVariables

from chrysalide.arc3 import langage
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.moteur import NOMS
from chrysalide.langue import vers_python
from chrysalide.qwen.demander import _appel
from chrysalide.qwen.images import PAL, images_coup

OUT = ICI/'essai_27b_ka59_outils'
SCHEMA = {'type': 'object', 'required': ['diagnostic', 'outil_python', 'experience_python', 'programme_python'],
          'properties': {k: {'type': 'string'} for k in ('diagnostic', 'outil_python', 'experience_python', 'programme_python')},
          'additionalProperties': False}
CONTRAT = '''Tu es auteur de programmes pour un agent qui découvre un jeu inconnu.
Le modèle actuel ne reproduit pas les observations. Identifie des hypothèses, pas une vérité présumée.
Tu peux demander une expérience, écrire un outil d'analyse et proposer un programme corrigé.
Ne reçois aucune solution humaine ; ne devine pas le nom du jeu. Aucune source de jeu accessible.
Réponse JSON : diagnostic (hypothèses et prédictions distinguables), outil_python, experience_python, programme_python.
Laisse une chaîne vide si tu ne proposes pas encore cet élément. Pas de Markdown dans le code.
Outil facultatif : PROGRAMME = Programme(regles=[], fonctions={"analyse": {"params": ["grilles", "actions"], "expr": "EXPRESSION"}})
grilles = liste des images 64x64 aplaties (4096 entiers), actions = liste des noms de commandes.
Expressions pures : sum,len,range,min,max,abs,int,compréhensions,indexation,comparaisons. Pas import/attribut/exec.
Le contrôleur exécutera analyse(grilles,actions) avec le vérificateur natif, et te renverra le résultat ou l'erreur.
Expérience : PROGRAMME = Programme(regles=[], experience={"actions": [["UP"]], "question": "question discriminante"})
L'exemple est seulement syntaxique. Propose 1 à 3 actions depuis la DERNIERE image observée.
Actions permises à proposer : UP DOWN LEFT RIGHT SPACE, ou ["MOUSE", row, col] avec coordonnées 0..63 ; le SDK filtrera.
Programme corrigé : PROGRAMME = Programme(mode="lois", etat={}, regles=[Regle(...)]) ; remplacer le programme complet.
Utilise la syntaxe du programme et la sémantique ci-dessous. Objet statique = segmentation actuelle, pas une vérité de rôle.
Le rejeu entier doit correspondre aux observations et ne doit pas annoncer une victoire absente.
Le modèle pourra agir seulement après vérification ; déclare les incertitudes et les informations manquantes.
Les images sont du pixel art 64x64 agrandi exactement x10 sans lissage. Tous les pixels sont des preuves.
'''


def preparer():
    OUT.mkdir(exist_ok=False)
    r = ICI/'runs/guidage_ka59_fige1/N1'
    with np.load(r/'partie.npz') as z:
        gs = z['images'].copy()
        films = {k: len(z[k]) for k in z.files if k.startswith('film_')}
    rows = json.loads((r/'partie.json').read_text())['rows']
    actions = [x['action'] for x in rows]
    v = ObjetsVariables(gs, actions)
    p = v.programme(v.buts[0])
    pc, sc = Programme(p), v.scene(gs[0])
    pc.step(sc, (NOMS[actions[0]],))
    predit = v.rendu(sc)
    yy, xx = np.nonzero(predit != v.vue(gs[1]))
    scene = [{**{k: s[k] for k in ('x', 'y', 'tags', 'couche')},
              'forme': s['pixels'].shape, 'pixels': s['pixels'].tolist()} for s in v.scene(gs[0]).sprites]
    dossier = {'actions': [NOMS[a] for a in actions], 'films_n_images': films,
               'etat_courant': 8, 'premiere_divergence': 1,
               'ecarts_y_x_predit_observe': [[int(y),int(x),int(predit[y,x]),int(v.vue(gs[1])[y,x])] for y,x in zip(yy,xx)],
               'scene_initiale': scene, 'programme_refuse': vers_python(p),
               'limite_films': 'une image finale par coup, aucune animation supplémentaire'}
    (OUT/'dossier.json').write_text(json.dumps(dossier,ensure_ascii=False,indent=2))
    for i,g in enumerate(gs):
        Image.fromarray(PAL[g]).resize((640,640),Image.Resampling.NEAREST).save(OUT/f'frame_{i}.png')
    (OUT/'comparaison.png').write_bytes(images_coup(v.vue(gs[0]),v.vue(gs[1]),predit)[1])
    doc = ast.get_docstring(ast.parse(Path(langage.__file__).read_text()))
    prompt = CONTRAT+'\nDOSSIER FACTUEL\n'+json.dumps(dossier,ensure_ascii=False)+'\nSEMANTIQUE NATIVE\n'+doc
    (OUT/'prompt_1.txt').write_text(prompt)
    print(json.dumps({'caracteres_prompt':len(prompt),'images':10,'ecarts':len(xx)}))


def appeler(numero):
    if numero not in (1,2,3):
        raise ValueError('Budget appels')
    cible = OUT/f'reponse_{numero}.json'
    if cible.exists():
        raise FileExistsError(cible)
    prompt = (OUT/f'prompt_{numero}.txt').read_text()
    fichiers = sorted(OUT.glob('frame_*.png')) if numero == 1 else sorted(OUT.glob('experience_frame_*.png'))
    if numero == 1:
        fichiers.append(OUT/'comparaison.png')
    images = [p.read_bytes() for p in fichiers]
    debut=time.monotonic()
    try:
        brut,fin,usage=_appel('ollama','qwen3.8:27b-mlx',prompt,SCHEMA,1536,150,0,images,num_ctx=32768)
        cible.write_text(brut)
        bilan={'fin':fin,'usage':usage,'n_images':len(images),'mur_s':time.monotonic()-debut}
    except Exception as e:  # noqa: BLE001 — transport enregistré, aucun repli
        bilan={'erreur':repr(e),'mur_s':time.monotonic()-debut}
    (OUT/f'metriques_{numero}.json').write_text(json.dumps(bilan,indent=2))
    print(json.dumps(bilan),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--appel',type=int);a=ap.parse_args()
    if a.appel:appeler(a.appel)
    else:preparer()
