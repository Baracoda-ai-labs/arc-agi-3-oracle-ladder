"""Réutiliser une affordance de sélection, sans exiger une règle déjà applicable."""
import numpy as np
from chrysalide.arc3.masque import Masque
from selection_visuelle_immobile import analyser,_vue


def proposer(agent,offre,memo):
    if 6 not in offre or not memo or memo.get('refutee'):return None
    from relation_clic_observee import positions
    attente=getattr(agent,'selection_heritee_en_attente',None)
    if attente and len(agent.actions)>attente['index']:
        agent.selection_heritee_en_attente=None
        if len(agent.actions)==attente['index']+1:
            hs=analyser(agent.images,agent.actions,agent.films,agent.issues)
            h=next((h for h in reversed(hs) if h['coup_activation']==len(agent.actions)),None)
            if h and h['marqueurs_distants']:
                from passage_clic_observe import proposer_marqueur
                d=proposer_marqueur(agent,memo,attente,h['marqueurs_distants'])
                if d is not None:return d
                c=min(h['marqueurs_distants'],key=lambda c:(c['y'],c['x']))
                return {'actions':[['clic',c['x'],c['y']]],'predictions':[[]],'modeles':[],
                    'origine':'marqueur_selection_heritee_sans_regle','statut':'experience_conditionnelle',
                    'but':'inconnu','risque':'inconnu','selection_source':attente,
                    'marqueurs_observes':h['marqueurs_distants'],
                    'question':'Quel effet a ce marqueur confirmé visuellement dans le nouveau contexte ?',
                    'abstentions':['regle_de_transformation','but','consommation','autres_objets']}
        return None
    m=Masque()
    for a,b in zip(agent.images,agent.images[1:]):m.observer(np.asarray(a).tolist(),np.asarray(b).tolist())
    cells=m.cellules();courant=_vue(agent.images[-1],cells)
    forme=frozenset(map(tuple,memo['forme']));cx=sum(x for x,y in forme)/len(forme);cy=sum(y for x,y in forme)/len(forme)
    dx,dy=min(forme,key=lambda p:((p[0]-cx)**2+(p[1]-cy)**2,p))
    for x,y in sorted(positions(agent.images[-1],forme),key=lambda p:(p[1],p[0])):
        action=['clic',x+dx,y+dy]
        if any(a==action and np.array_equal(_vue(g,cells),courant) for a,g in zip(agent.actions,agent.images)):continue
        agent.selection_heritee_en_attente={'index':len(agent.actions),'action':action,'position':[x,y],
            'forme':memo['forme'],'source':'affordance_selection_anterieure','but_certifie':False}
        return {'actions':[action],'predictions':[[]],'modeles':[],
            'origine':'selection_heritee_sans_cible','statut':'experience_conditionnelle',
            'but':'inconnu','risque':'inconnu','question':'Cette forme encore présente révèle-t-elle des actions contextuelles ?',
            'hypotheses':['selection_avec_marqueurs','selection_non_confirmee_dans_ce_contexte'],
            'abstentions':['partenaire','destination','transformation','but'],
            'provenance':'forme interactive conservée, pas solution ni coordonnées héritées'}
    return None
