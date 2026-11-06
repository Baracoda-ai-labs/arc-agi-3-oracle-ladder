"""Suspend les hypothèses objets hors contexte ; retour observable, jamais loi SPACE."""
import copy
import numpy as np
from diagnostic_contexte_transfert import compatible, marqueurs


def observer(agent, avant, apres, action, issue):
    modele = getattr(agent, 'memoire_jeu', None)
    if issue != 'continue' or modele is None or modele.famille != 'objets':
        return None
    stock = getattr(agent, 'modeles_contextes_suspendus', {})
    coup = len(agent.actions)
    retour = compatible(modele, apres)
    if stock:
        record = {'type': 'contexte_suspendu_observe', 'coup': coup,
                  'action': copy.deepcopy(action), 'prediction_physique': False,
                  'contexte_compatible': retour, 'reactives': [], 'refuses': []}
        if retour:
            for nom, entree in list(stock.items()):
                c = copy.deepcopy(entree['chaine'])
                c._verifie = None
                check, state = c.rejouer()
                exact = state is not None and all(check.get(k) for k in
                    ('catalogue_shacl','traduction_python','rejeu','compilation_fidele'))
                exact = exact and np.array_equal(c.perception.rendu(state[1]), c.perception.vue(apres))
                if not exact:
                    record['refuses'].append(nom)
                    continue
                preuve = {'debut': entree['debut'], 'fin': coup,
                          'actions_non_modelisees': copy.deepcopy(agent.actions[entree['debut']-1:coup]),
                          'reprise': 'egalite_rendu_etat_conserve', 'etat_latent_provisoire': True,
                          'prediction_physique_intervalle': False}
                c.intervalles_contexte = [*getattr(c,'intervalles_contexte',[]), preuve]
                c.plan = None
                c.coups = coup
                agent.chaines[nom] = c
                record['reactives'].append(nom)
                del stock[nom]
            if record['reactives']:
                agent.diagnostic_transfert = None
                agent.reconstruction = False
                record['type'] = 'contexte_modeles_reactives'
        agent.modeles_contextes_suspendus = stock
        agent.journal.append(record)
        agent.attente = None
        return record
    if retour or not compatible(modele, avant) or not agent.chaines:
        return None
    # Seuls les pixels des marqueurs changent ; aucun déplacement natif caché.
    points_avant, points_apres = [
        {p for hosts in marqueurs(im).values() for positions in hosts.values() for p in positions}
        for im in (avant, apres)]
    points = points_avant & points_apres
    changes = {tuple(map(int,p)) for p in np.argwhere(np.asarray(avant)!=np.asarray(apres))}
    for nom,c in agent.chaines.items():
        base=c.perception
        while hasattr(base,'base'):base=base.base
        if c.refute or not changes <= points | set(getattr(base,'hud',())):
            continue
        check,state=c.rejouer()
        if state is None or not np.array_equal(c.perception.rendu(state[1]),c.perception.vue(avant)):
            continue
        saved=copy.deepcopy(c);saved.plan=None
        stock[nom]={'chaine':saved,'debut':coup}
    if not stock or len(stock)!=len(agent.chaines):
        return None
    agent.modeles_contextes_suspendus=stock
    agent.chaines={}
    agent.reconstruction=False
    agent.diagnostic_transfert={'contrat_candidat':'selection_marqueur',
        'statut':'contexte_suspendu','regles_conservees':True,
        'prediction_physique_intervalle':False}
    record={'type':'contexte_modeles_suspendus','coup':coup,'modeles':list(stock),
            'prediction_physique':False,'avant':marqueurs(avant),'apres':marqueurs(apres)}
    agent.journal.append(record);agent.attente=None
    return record
