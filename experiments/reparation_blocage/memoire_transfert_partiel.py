"""Transfert de faits d'épisodes, sans transformer une victoire en théorie du but."""
from memoire_observations import episode_observe,ajouter_episode
import copy


def annoter(episode):
    ep=dict(episode);ep['provenance']=copy.deepcopy(episode['provenance'])
    issues=ep['issues'];films=ep.get('films')
    ep['provenance'].update(
        type_preuve_issue='issue_sdk_observee_pas_but_identifie',but_certifie=False,
        transitions_non_victorieuses=[i+1 for i,v in enumerate(issues) if v=='continue'],
        transition_victorieuse=len(issues) if issues and issues[-1] in ('niveau','victoire') else None,
        image_post_transition_utilisable_comme_but=False,
        film_terminal_conserve=films is not None and bool(films) and films[-1] is not None,
        frontiere_niveau='position_du_changement_dans_film_non_attribuee')
    return ep


def conserver(ancien,nouveau):
    if not ancien.issues or ancien.issues[-1] not in ('niveau','victoire'):
        raise ValueError('Victoire SDK nécessaire pour transfert de niveau')
    if any(i!='continue' for i in ancien.issues[:-1]):
        raise ValueError('Episode traverse une frontiere interne')
    for ep in getattr(ancien,'observations_episodes',[]):ajouter_episode(nouveau,annoter(ep))
    episode=episode_observe(ancien.images,ancien.actions,ancien.issues,getattr(ancien,'films',None))
    episode=annoter(episode)
    ajouter_episode(nouveau,episode)
    conserver_hypotheses(ancien,nouveau,episode['provenance']['sha256_contenu'])
    nouveau.journal.append({'type':'transfert_episodes_observes',
        'episode_source_sha256':episode['provenance']['sha256_contenu'],
        'episodes_uniques':len(nouveau.observations_episodes),
        'but_certifie':False,'image_niveau_suivant_pas_but_source':True})
    return episode['provenance']['sha256_contenu']


def conserver_hypotheses(ancien,nouveau,episode_sha):
    """Bibliothèque accessible ; ne réaffecte aucun objet du nouveau niveau."""
    import hashlib,json
    banque=copy.deepcopy(getattr(nouveau,'hypotheses_capacites_heritees',[]))
    candidats=copy.deepcopy(getattr(ancien,'hypotheses_capacites_heritees',[]))
    regle=getattr(ancien,'memoire_mouvement_conjoint',None)
    if regle:
        candidats.append({'capacite':'mouvement_conjoint','episode_source_sha256':episode_sha,
             'hypothese':copy.deepcopy(regle),'statut':'a_revalider_dans_nouveau_contexte',
             'active':False,'but_certifie':False})
    def cle(e):return hashlib.sha256(json.dumps(e,sort_keys=True,default=lambda x:x.tolist()).encode()).hexdigest()
    vus={cle(e) for e in banque}
    for e in candidats:
        k=cle(e)
        if k not in vus:banque.append(e);vus.add(k)
    nouveau.hypotheses_capacites_heritees=banque
    return len(banque)
