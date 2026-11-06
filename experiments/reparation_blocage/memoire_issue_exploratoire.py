"""Conserver une issue observée sans transformer tous les modèles en théories gagnantes."""
import copy
import hashlib
import numpy as np


def capturer(chaines, decision, action, image, film, issue, coup, *, source):
    """Appeler AVANT observer : les snapshots gardent le préfixe avant image terminale.

    Retourne preuve sérialisable, candidats avant victoire, nom sélectionné ou None.
    La sélection exige une prédiction terminale vérifiée ; l'ambiguïté est conservée.
    """
    if issue not in ('niveau', 'victoire'):
        return None, {}, None
    if source not in ('jeu', 'trace'):
        raise ValueError('Provenance de l’issue attendue : jeu ou trace')
    if not decision.get('actions'):
        raise ValueError('Décision prospective absente')
    preuve = {'type':'memoire_issue_observee', 'issue':issue, 'source':source,
        'coup':coup, 'action':list(action),
        'image_sha256':hashlib.sha256(np.asarray(image,dtype=np.int16).tobytes()).hexdigest(),
        'film_sha256':hashlib.sha256(np.asarray(film,dtype=np.int16).tobytes()).hexdigest(),
        'candidats':[], 'selection':None, 'promotion_interjeux':False}
    snapshots={}; predits=[]
    prospectifs=set(decision.get('modeles',()))
    owner=decision.get('modele_plan')
    if owner is not None:prospectifs.add(owner)
    for nom,c in chaines.items():
        if c.refute:continue
        controle,courant=c.rejouer()
        if courant is None or not all(controle.get(k) for k in
                ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
            continue
        predit,verification=c.verifier_plan([action]) if nom in prospectifs else (False,{'refus':'pas_de_prediction_prospective'})
        snapshots[nom]=copy.deepcopy(c)
        if predit:predits.append(nom)
        preuve['candidats'].append({'nom':nom,'signature':c.signature(),
            'but_confirme_par_prediction':bool(predit),'verification':verification,
            'portee':'prefixe_et_issue_predite' if predit else 'prefixe_seulement_but_non_valide'})
    selection=owner if owner in predits else (predits[0] if len(predits)==1 else None)
    preuve['selection']=selection
    preuve['ambiguite']=len(predits)>1 and selection is None
    preuve['but_reste_a_induire']=not predits
    return preuve,snapshots,selection


def memoriser(agent, action, image, film, issue, *, source):
    """Raccord minimal au journal et à modele_gagnant, sans réinitialiser le jeu."""
    preuve,snapshots,selection=capturer(agent.chaines,agent.attente,action,image,film,
        issue,len(agent.actions)+1,source=source)
    if preuve is None:return None
    agent.modeles_avant_victoire=snapshots
    # Un modèle gagnant d'un ancien niveau ne doit pas masquer l'incertitude du nouveau.
    agent.modele_gagnant=snapshots[selection] if selection is not None else None
    agent.journal.append(preuve)
    return preuve
