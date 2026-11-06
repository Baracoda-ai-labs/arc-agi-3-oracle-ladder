"""Départager superposition et mouvement conjoint sans certifier une contenance."""
import numpy as np
from objets_variables import localiser
from garde_support_navigation import apprendre


def proposer(agent,offre,objectif,memo):
    from relation_clic_observee import positions
    preuve=objectif.get('ancre_partielle')
    if not preuve:return None
    try:pos=localiser(agent.images[-1],np.array(preuve['motif_stable']))
    except ValueError:return None
    motif=np.array(objectif['motif_mobile']);forme=frozenset(map(tuple,memo['forme']))
    inclus=[p for p in positions(agent.images[-1],forme) if all(pos[0]<=p[0]+x<pos[0]+motif.shape[1] and pos[1]<=p[1]+y<pos[1]+motif.shape[0] for x,y in forme)]
    if len(inclus)!=1:return None
    gardes,mouvements,_=apprendre(agent.images,agent.actions,motif)
    for code,delta in sorted(mouvements.items()):
        if code not in offre:continue
        dest=tuple(pos[i]+delta[i] for i in (0,1))
        if min(dest)<0 or dest[0]+motif.shape[1]>agent.images[-1].shape[1] or dest[1]+motif.shape[0]>agent.images[-1].shape[0]:continue
        if not gardes or not all(int(agent.images[-1][dest[1]+g['offset'][1],dest[0]+g['offset'][0]]) in g['permis'] for g in gardes):continue
        return {'actions':[code],'predictions':[[]],'modeles':[],
                'origine':'experience_mouvement_conjoint','statut':'experience_conditionnelle',
                'but':'inconnu','risque':'inconnu','support_avant':list(pos),'support_candidate':list(dest),
                'motif_stable':preuve['motif_stable'],'forme_avant':list(inclus[0]),
                'hypotheses':{'independante':list(inclus[0]),'conjointe':[inclus[0][i]+delta[i] for i in (0,1)]},
                'portee':'predictions_concurrentes_pas_contenance_validee'}
    return None


def memoriser(agent,objectif,memo):
    """Conserver uniquement le déplacement relatif réellement observé."""
    from relation_clic_observee import positions
    i=objectif.get('index_sonde_conjointe')
    preuve=objectif.get('ancre_partielle')
    if i is None or len(agent.actions)<=i or not preuve:return None
    stable=np.asarray(preuve['motif_stable']);forme=frozenset(map(tuple,memo['forme']))
    try:a=localiser(agent.images[i],stable);b=localiser(agent.images[i+1],stable)
    except ValueError:return None
    delta=(b[0]-a[0],b[1]-a[1])
    if delta==(0,0):return None
    avant=positions(agent.images[i],forme);apres=positions(agent.images[i+1],forme)
    couples=[p for p in avant if (p[0]+delta[0],p[1]+delta[1]) in apres and all(a[0]<=p[0]+x<a[0]+stable.shape[1] and a[1]<=p[1]+y<a[1]+stable.shape[0] for x,y in forme)]
    if len(couples)!=1:return None
    p=couples[0]
    regle={'forme':memo['forme'],'support_motif_stable':stable.tolist(),
           'support_motif_complet':objectif['motif_mobile'],
           'decalage':[p[0]-a[0],p[1]-a[1]],'vecteur_observe':list(delta),
           'action_preuve':agent.actions[i],'coup_preuve':i+1,
           'statut':'mouvement_conjoint_provisoire','but_certifie':False,
           'contenance_certifiee':False,'transfert_valide':False}
    agent.memoire_mouvement_conjoint=regle
    return regle
