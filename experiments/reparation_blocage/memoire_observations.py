"""Épisodes d'observations séparés, avec films et identité de contenu stable."""
import copy
import hashlib
import json
import numbers
import numpy as np


def episode_observe(grilles, actions, issues, films=None):
    if len(grilles)!=len(actions)+1 or len(issues)!=len(actions):
        raise ValueError('Episode non aligne')
    if any(isinstance(a,numbers.Integral) and a==0 for a in actions):
        raise ValueError('RESET ne constitue pas une observation de dynamique')
    if films is not None and len(films)!=len(actions):
        raise ValueError('Films non alignes')
    # Conversion pour empreinte seulement : les observations originales restent intactes.
    def normaliser(x):
        if isinstance(x,np.ndarray):return x.tolist()
        if isinstance(x,np.generic):return x.item()
        if isinstance(x,(tuple,list)):return [normaliser(v) for v in x]
        if isinstance(x,dict):return {k:normaliser(v) for k,v in x.items()}
        return x
    contenu={'grilles':grilles,'actions':actions,'issues':issues,'films':films}
    digest=hashlib.sha256(json.dumps(normaliser(contenu),sort_keys=True,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return {**copy.deepcopy(contenu),'provenance':{'type':'observations_sdk',
        'sha256_contenu':digest,'transitions':len(actions),
        'films_disponibles':films is not None}}


def ajouter_episode(agent, episode):
    """Import explicite d'observations, sans fusion ni remplacement de l'état courant."""
    valide=episode_observe(*(episode[k] for k in ('grilles','actions','issues')),
                          films=episode.get('films'))
    attendu=episode.get('provenance',{}).get('sha256_contenu')
    if attendu!=valide['provenance']['sha256_contenu']:
        raise ValueError('Empreinte episode invalide')
    anciens=getattr(agent,'observations_episodes',[])
    if any(e.get('provenance',{}).get('sha256_contenu')==attendu for e in anciens):
        return False
    valide['provenance']=copy.deepcopy(episode['provenance'])
    agent.observations_episodes=[*anciens,valide]
    return True


def lire_archive(prefixe, empreintes, niveaux_initiaux):
    """Lit une archive explicitement choisie et vérifiée ; aucune découverte de jeux."""
    from pathlib import Path
    from io import BytesIO
    from issues_observees import issue_sdk
    p=Path(prefixe); contenus={}
    for suffixe in ('.json','.npz'):
        b=p.with_suffix(suffixe).read_bytes()
        if hashlib.sha256(b).hexdigest()!=empreintes.get(suffixe):
            raise ValueError('Empreinte archive invalide')
        contenus[suffixe]=b
    rows=json.loads(contenus['.json'])['rows']
    issues=[issue_sdk(r['state'],r['levels_completed'],niveaux_initiaux) for r in rows]
    if any(i!='continue' for i in issues[:-1]):
        raise ValueError('Archive traverse une frontiere episode')
    with np.load(BytesIO(contenus['.npz']),allow_pickle=False) as z:
        films=[z[f'film_{i+1}'].copy() for i in range(len(rows))]
        ep=episode_observe(z['images'].copy(),[r['action'] for r in rows],issues,films)
    ep['provenance'].update(archives_sha256=dict(empreintes),
                            niveaux_initiaux=niveaux_initiaux)
    return ep
