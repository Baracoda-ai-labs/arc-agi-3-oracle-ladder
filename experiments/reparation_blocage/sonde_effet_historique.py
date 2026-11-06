"""Départage une restauration historique et une translation, sans nommer la commande."""
import numpy as np
from objets_identites import suivre_motif
from operateurs_memoire import verifier_retours
from chrysalide.arc3.logique.induction import precedent_pile
from perception_navigation_provisoire import construire


def proposer(agent,offre):
    if len(agent.actions)<3 or not all(isinstance(a,int) for a in agent.actions):return None
    code=agent.actions[-1]
    if code not in offre:return None
    try:vue,diagnostic=construire(agent.images,agent.actions)
    except (ValueError,TypeError):return None
    agent.diagnostic_perception_navigation=diagnostic
    if len(vue.mobiles)<2 or not all(np.array_equal(m,vue.mobiles[0]) for m in vue.mobiles):return None
    motif=vue.mobiles[0]
    try:etats=suivre_motif(agent.images,motif,len(vue.mobiles))
    except ValueError:return None
    preuves=verifier_retours(etats,agent.actions,code)
    if not preuves or not all(p['conforme'] for p in preuves):return None
    historique=precedent_pile(etats,agent.actions,len(agent.actions),code)
    deltas={tuple((q[0]-p[0],q[1]-p[1]) for p,q in zip(etats[i],etats[i+1])) for i,a in enumerate(agent.actions) if a==code}
    if len(deltas)!=1:return None
    delta=next(iter(deltas));constant=tuple((p[0]+d[0],p[1]+d[1]) for p,d in zip(etats[-1],delta))
    if historique==constant or historique==etats[-1]:return None
    return {'actions':[code],'predictions':[[]],'modeles':[],
        'origine':'experience_effet_historique','statut':'experience_conditionnelle',
        'but':'inconnu','risque':'inconnu','question':'Restauration de positions historiques ou translation constante ?',
        'contrat_hypotheses':{'motif':motif.tolist(),'cardinalite':len(vue.mobiles),
          'historique':[list(p) for p in historique],'translation_constante':[list(p) for p in constant],
          'attributs':['positions_visibles_toutes_les_pistes'],'abstentions':['but','autres_objets','semantique_commande'],
          'annulation_certifiee':False},'preuves_retour':preuves,'perception':diagnostic}
