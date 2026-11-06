"""Preuves d'épisodes locaux : risque provisoire, jamais règle ni but appris."""
import copy
import hashlib
import numpy as np


def signature(image):
    a=np.asarray(image,dtype=np.int64)
    return hashlib.sha256(str(a.shape).encode()+a.tobytes()).hexdigest()


def retenir_defaite(agent, offre, niveau):
    preuves=copy.deepcopy(getattr(agent,'memoire_episodes',[]))
    if agent.issues and agent.issues[-1]=='defaite' and len(agent.images)>=2:
        action=agent.actions[-1]
        preuves.append({'image':signature(agent.images[-2]),'action':list(action) if isinstance(action,tuple) else action,
            'offre':sorted(offre),'niveau':niveau,'statut':'risque_provisoire',
            'contexte_latent':'inconnu','portee':'session_jeu_courante','issue_observee':'defaite'})
    return preuves


def risques(preuves,image,offre):
    sig=signature(image)
    return {tuple(p['action']) if isinstance(p['action'],list) else p['action']
            for p in preuves if p['image']==sig and p['offre']==sorted(offre)
            and p['issue_observee']=='defaite'}


def separer_episode(lab,output):
    """Après RESET observé : même env, image initiale, aucune transition RESET induite."""
    nxt=copy.copy(lab)
    nxt.output=output;output.parent.mkdir(parents=True,exist_ok=False)
    nxt.images=[lab.image.copy()];nxt.rows=[];nxt.films={};nxt.resets=0;nxt.defaites=0
    nxt.save()
    return nxt
