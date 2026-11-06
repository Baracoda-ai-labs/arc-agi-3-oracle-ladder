"""Raccord des modèles perceptifs provisoires au choix d'expérience existant."""
import numpy as np
from buts_modele_conserve import actions_modele


def proposer(agent,offre):
    from chaine_agent_integree import canon,sdk
    if len(agent.chaines)<2 or not any(hasattr(c, 'diagnostic_hitbox') for c in agent.chaines.values()):
        return None
    actions=sorted({a for c in agent.chaines.values() for a in actions_modele(c,offre)})
    def repetee(action):
        for image,ancienne in zip(agent.images,agent.actions):
            if canon(ancienne)!=action:continue
            if all(np.array_equal(c.perception.vue(image),c.perception.vue(agent.images[-1])) for c in agent.chaines.values()):
                return True
        return False
    actions=[a for a in actions if not repetee(a)]
    # Une nouvelle position avant une réutilisation dans un autre état observable.
    deja={canon(a) for a in agent.actions}
    actions.sort(key=lambda a:(a in deja,a))
    nom=next(iter(agent.chaines))
    candidats=[(1,nom,a) for a in actions]
    choix,diag=agent._choisir_sonde_utile(agent.dossier(offre),candidats)
    agent.journal.append({'type':'experience_portefeuille','diagnostic':diag})
    if choix is None:return None
    result={'statut':'experience_discriminante','origine':'controleur_portefeuille_perception',
        'actions':[sdk(choix[2])],'predictions':[[]],'diagnostic':diag,
        'risque':'inconnu','but':'non_requis','cout_actions':1}
    agent._suivre_experience(result);agent.attente=result
    return result
