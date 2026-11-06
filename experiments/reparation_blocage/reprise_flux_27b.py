"""Dernier appel borné : retour de format, sans correction sémantique humaine."""
import base64
import json
import signal
import time
from itertools import groupby

import requests
from essai_27b_ka59_outils import OUT, SCHEMA


def main():
    if (OUT/'metriques_3.json').exists() or (OUT/'reponse_3.json').exists():
        raise FileExistsError('Troisième appel déjà lancé')
    prompt = (OUT/'prompt_1.txt').read_text()
    prompt += '\nRETOUR MECANIQUE DU CONTROLEUR\n' + (OUT/'controle_2.json').read_text()
    prompt += '\nLa réponse précédente a atteint sa limite de sortie. Fournis un JSON complet et concis dans 1536 jetons. Les chaînes vides sont autorisées comme indiqué au contrat. Aucun code partiel ne sera exécuté.\nREPONSE PRECEDENTE BRUTE\n'
    prompt += (OUT/'reponse_2.json').read_text()
    (OUT/'prompt_3.txt').write_text(prompt)
    files = sorted(OUT.glob('frame_*.png'))+[OUT/'comparaison.png']
    appeler_flux(prompt, files, OUT, 3, SCHEMA, jetons=1536, delai=150)


def images_texte(files):
    import numpy as np
    from PIL import Image

    from chrysalide.qwen.images import PAL
    palette={tuple(map(int,c)):i for i,c in enumerate(PAL)}
    resultat=[]
    for p in files:
        rgb=np.asarray(Image.open(p).convert('RGB'))
        if rgb.shape!=(640,640,3): raise ValueError('Image ×10 exacte requise')
        petit=rgb[::10,::10]
        if not np.array_equal(rgb,petit.repeat(10,0).repeat(10,1)):
            raise ValueError('Image non agrandie par nearest-neighbor')
        g=[[palette[tuple(map(int,c))] for c in ligne] for ligne in petit]
        lignes=[[[couleur,len(list(groupe))] for couleur,groupe in groupby(row)] for row in g]
        assert [[c for c,n in row for _ in range(n)] for row in lignes]==g
        resultat.append({'image':p.name,'lignes':lignes})
    return resultat


def appeler_flux(prompt, files, out, numero, schema, jetons=1200, delai=180,
                 modele='qwen3.8:27b-mlx', texte_images=False):
    if (out/f'metriques_{numero}.json').exists() or (out/f'reponse_{numero}.json').exists():
        raise FileExistsError('Appel déjà lancé')
    if texte_images and files:
        prompt+='\nIMAGES EXACTES EN TEXTE : 64 lignes de haut en bas, chaque ligne = suites [couleur ARC, longueur], de gauche à droite. Aucun pixel omis.\n'+json.dumps(images_texte(files),separators=(',',':'))
    (out/f'prompt_{numero}.txt').write_text(prompt)
    (out/f'images_{numero}.json').write_text(json.dumps([str(p) for p in files]))
    body = {'model':modele, 'messages':[{'role':'user','content':prompt,
        **({'images':[base64.b64encode(p.read_bytes()).decode() for p in files]} if not texte_images else {})}],
        'format':schema, 'stream':True, 'think':False, 'keep_alive':'5m',
        'options':{'temperature':0,'num_predict':jetons,'num_ctx':32768}}
    def expire(_sig, _frame):
        raise TimeoutError(f'Plafond mural {delai} s')
    signal.signal(signal.SIGALRM, expire)
    signal.alarm(delai)
    debut = time.monotonic()
    contenu, dernier, erreur = '', {}, None
    try:
        with requests.post('http://127.0.0.1:11434/api/chat', json=body, stream=True, timeout=(5,delai)) as r:
            r.raise_for_status()
            with (out/f'flux_{numero}.jsonl').open('x') as f:
                for ligne in r.iter_lines():
                    if not ligne:
                        continue
                    dernier = json.loads(ligne)
                    f.write(json.dumps(dernier,ensure_ascii=False)+'\n'); f.flush()
                    contenu += dernier.get('message',{}).get('content','')
                    (out/f'reponse_{numero}.json').write_text(contenu)
    except Exception as e:  # noqa: BLE001 — coût des échecs conservé
        erreur = repr(e)
    finally:
        signal.alarm(0)
        bilan = {'mur_s':time.monotonic()-debut,'fin':dernier.get('done_reason'),
            'entree':dernier.get('prompt_eval_count'),'sortie':dernier.get('eval_count'),
            'erreur':erreur,'caracteres_recuperes':len(contenu),'n_images':len(files),
            'modele':modele,'representation_images':'texte_exact' if texte_images else 'vision'}
        (out/f'metriques_{numero}.json').write_text(json.dumps(bilan,indent=2))
        print(json.dumps(bilan),flush=True)
    return contenu, bilan


if __name__ == '__main__':
    main()
