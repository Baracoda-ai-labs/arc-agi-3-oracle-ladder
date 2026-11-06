"""Une commande sans mouvement appris reste inconnue dans un nouveau contexte."""
import numpy as np
from objets_identites import occurrences
from suivi_partiel_observe import suivre
from chrysalide.arc3.masque import Masque
from selection_visuelle_immobile import _vue


def proposer(agent,offre):
    h=getattr(agent,'memoire_mouvement_conjoint',None)
    if not h:return None
    motif=np.asarray(h['support_motif_stable']);n=len(occurrences(agent.images[-1],motif))
    if not 2<=n<=6:return None
    try:series,diagnostic=suivre(agent.images,motif,n)
    except ValueError:return None
    connus=set()
    for i,code in enumerate(agent.actions):
        if isinstance(code,int) and series[i] is not None and series[i+1] is not None and series[i]!=series[i+1]:connus.add(code)
    m=Masque()
    for a,b in zip(agent.images,agent.images[1:]):m.observer(np.asarray(a).tolist(),np.asarray(b).tolist())
    cells=m.cellules();courant=_vue(agent.images[-1],cells)
    for code in sorted(k for k in offre if k in (1,2,3,4) and k not in connus):
        if any(a==code and np.array_equal(_vue(g,cells),courant) for a,g in zip(agent.actions,agent.images)):continue
        return {'actions':[code],'predictions':[[]],'modeles':[], 'origine':'sonde_commande_contexte_nouveau',
            'statut':'experience_conditionnelle','but':'inconnu','risque':'inconnu',
            'question':'Commande sans déplacement caractérisé : garde contextuelle ou absence de contrôle ?',
            'supports_observes':list(map(list,series[-1])),'suivi':diagnostic,
            'abstentions':['direction','amplitude','but','autres_objets'],
            'preuve':'Ancien effet nul ne prouve pas inertie universelle',
            'contexte':'image_complete_hors_masque_heuristique'}
    return None
