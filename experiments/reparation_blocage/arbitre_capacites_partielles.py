"""Aiguillage expérimental entre portée clic et navigation, sans modèle du but."""
import numpy as np
from objets_variables import ObjetsVariables, localiser
from chrysalide.arc3.masque import Masque


def proposer_navigation(agent, offre):
    from sonde_effet_historique import proposer as proposer_historique
    d=proposer_historique(agent,offre)
    if d is not None:return d
    # Réutiliser le plus long segment clavier, sans concaténer des transitions.
    segments=[];debut=None
    for i,a in enumerate(agent.actions+[None]):
        if isinstance(a,int) and a in (1,2,3,4):
            if debut is None:debut=i
        elif debut is not None:
            segments.append((debut,i));debut=None
    if not segments:return None
    debut,fin=max(segments,key=lambda ab:ab[1]-ab[0])
    try:
        from perception_navigation_provisoire import construire
        vue,diagnostic=construire(agent.images[debut:fin+1],agent.actions[debut:fin])
        agent.diagnostic_perception_navigation=diagnostic
    except (ValueError,TypeError):return None
    from garde_support_navigation import proposer as proposer_support
    for motif in vue.mobiles:
        d=proposer_support(agent.images,agent.actions,motif,offre)
        if d is not None:return d
    from sonde_commande_contextuelle import proposer as sonde_contexte
    d=sonde_contexte(agent,offre)
    if d is not None:return d
    masque=Masque()
    for a,b in zip(agent.images,agent.images[1:]):masque.observer(np.asarray(a).tolist(),np.asarray(b).tolist())
    cellules=masque.cellules()
    def contexte(g):
        v=np.asarray(g).copy()
        for y,x in cellules:v[y,x]=-1
        return v
    courant=contexte(agent.images[-1])
    hauteur,largeur=courant.shape
    choix=[]
    for no,motif in enumerate(vue.mobiles):
        try:position=localiser(agent.images[-1],motif)
        except ValueError:continue
        for code,delta in vue.mouvements[no].items():
            if code not in offre or tuple(delta)==(0,0):continue
            deja=False
            for avant,a in zip(agent.images,agent.actions):
                if a!=code:continue
                try:deja=localiser(avant,motif)==position and np.array_equal(contexte(avant),courant)
                except ValueError:continue
                if deja:break
            if deja:continue
            cible=(position[0]+delta[0],position[1]+delta[1])
            if min(cible)<0 or cible[0]+motif.shape[1]>largeur or cible[1]+motif.shape[0]>hauteur:continue
            repetitions=0
            for avant,action in zip(agent.images,agent.actions):
                if action!=code:continue
                try:repetitions+=int(localiser(avant,motif)==position)
                except ValueError:continue
            choix.append((repetitions,code,no,position,cible))
    if not choix:return None
    repetitions,code,no,position,cible=min(choix)
    return {'actions':[code],'predictions':[[]],'modeles':[],
            'origine':'arbitrage_capacites_coexistantes','statut':'experience_conditionnelle',
            'risque':'inconnu','but':'inconnu','memoire_provisoire':True,
            'question':'La translation déjà observée reste-t-elle possible dans ce contexte objet ?',
            'contrat_prediction_partielle':{'action':code,'objets':{'motif':vue.mobiles[no].tolist()},
              'attributs':['position_visible'],'position_avant':list(position),'position_candidate':list(cible),
              'statut':'extrapolation_garde_inconnue','but_certifie':False,
              'abstentions':['garde_de_contact','autres_objets','relation_clic','but','images_intermediaires']},
            'preuve':{'segment_clavier':[debut+1,fin], 'segment_statut':'candidat_non_exhaustif',
                      'contexte':'image_complete_hors_masque_heuristique',
                      'cellules_masquees':sorted(map(list,cellules)),
                      'priorite':'moins_sonde_a_position_egale_heuristique_pas_interdiction_physique',
                      'repetitions_position_action':repetitions,
                      'contexte_integral_pour_exclusion':True}}
