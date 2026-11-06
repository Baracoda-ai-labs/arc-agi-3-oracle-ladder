"""Contrôle neutre du transport visuel ; aucun jeu, aucune règle cible."""
import json
from pathlib import Path

import requests
from PIL import Image, ImageDraw
from reprise_flux_27b import appeler_flux


def main():
    out=Path(__file__).resolve().parent/'installation_gemma3_4b'
    out.mkdir(exist_ok=False)
    modele='gemma3:4b'
    r=requests.post('http://127.0.0.1:11434/api/show',json={'model':modele},timeout=20)
    r.raise_for_status();infos=r.json()
    (out/'modele.json').write_text(json.dumps(infos,ensure_ascii=False,indent=2))
    tags=requests.get('http://127.0.0.1:11434/api/tags',timeout=10).json()
    (out/'identite.json').write_text(json.dumps([x for x in tags['models'] if x['name']==modele],indent=2))
    if 'vision' not in infos.get('capabilities',[]): raise ValueError('Vision non annoncée')
    images=[]
    for nom,gauche,droite in [('A',(255,0,0),(0,0,255)),('B',(0,255,0),(255,255,0))]:
        im=Image.new('RGB',(640,640),gauche);ImageDraw.Draw(im).rectangle((320,0,639,639),fill=droite)
        p=out/f'{nom}.png';im.save(p);images.append(p)
    attendu={'A_gauche':'rouge','A_droite':'bleu','B_gauche':'vert','B_droite':'jaune'}
    (out/'attendu.json').write_text(json.dumps(attendu))
    schema={'type':'object','required':list(attendu),'properties':{k:{'type':'string'} for k in attendu},'additionalProperties':False}
    prompt='Deux images jointes, A puis B. Identifie la couleur de la moitié gauche et de la moitié droite de chacune. Réponds en JSON avec A_gauche, A_droite, B_gauche, B_droite ; noms de couleurs simples en français.'
    raw,met=appeler_flux(prompt,images,out,1,schema,jetons=128,delai=120,modele=modele)
    try:
        obtenu=json.loads(raw)
        normalise={k:v.strip().casefold() if isinstance(v,str) else v for k,v in obtenu.items()}
        bilan={'correct':normalise==attendu,'correct_strict':obtenu==attendu,
               'obtenu':obtenu,'metriques':met,'preuve_arc':False}
    except ValueError as e:
        bilan={'correct':False,'erreur':str(e),'metriques':met,'preuve_arc':False}
    (out/'bilan.json').write_text(json.dumps(bilan,ensure_ascii=False,indent=2))
    # L'essai de jeu doit inclure son propre chargement.
    r=requests.post('http://127.0.0.1:11434/api/generate',json={'model':modele,'keep_alive':0},timeout=20)
    r.raise_for_status()
    print(json.dumps(bilan,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
