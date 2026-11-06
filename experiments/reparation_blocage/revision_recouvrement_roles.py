"""Réviser un ordre de rendu observé, puis réutiliser le sol révélé si nécessaire."""
import copy
import numpy as np
from chaine_coherente import Chaine
from transfert_roles import RolesReaffectes
from memoire_reparations_roles import conserver


def proposer(source):
    diag={'admis':False,'programme_modifie':False,'provisoire':True}
    if type(source.perception) is not RolesReaffectes or not source.lots:
        return None,{**diag,'refus':'representation_non_applicable'}
    films=[e['images'] if e else None for e in source.films.entrees]
    def chaine(v,p=source.programme):
        c=Chaine(v,copy.deepcopy(p),source.grilles,source.lots,source.actions,
                 coups_deja_joues=source.coups,reserve=source.limite,films=films)
        conserver(source,c);return c
    prefixe=Chaine(source.perception,source.programme,source.grilles[:-1],source.lots[:-1],source.actions,films=films[:-1])
    _,cur=prefixe.rejouer()
    if cur is None:return None,{**diag,'refus':'prefixe_deja_refute'}
    if len(source.lots[-1]['actions'])!=1:return None,{**diag,'refus':'action_non_atomique'}
    pc,scene=cur;anciens=copy.deepcopy(scene.sprites)
    pc.step(scene,source.action_tuple(source.lots[-1]['actions'][0]))
    pred=source.perception.rendu(scene);obs=source.perception.vue(source.grilles[-1])
    hypotheses=set()
    for avant,apres in zip(anciens,scene.sprites):
        if (avant['x'],avant['y'])==(apres['x'],apres['y']):continue
        if not np.array_equal(avant['pixels'],apres['pixels']):continue
        couleurs=set(np.unique(apres['pixels']))-{-1}
        if len(couleurs)!=1:continue
        classe=int(next(iter(couleurs)));couvertures=[]
        for y,x in np.argwhere(pred!=obs):
            xx,yy=int(x-apres['x']),int(y-apres['y'])
            if not (0<=yy<apres['pixels'].shape[0] and 0<=xx<apres['pixels'].shape[1]
                    and apres['pixels'][yy,xx]==obs[y,x]):continue
            for q in scene.sprites:
                qx,qy=int(x-q['x']),int(y-q['y'])
                if ('cible' in q.get('tags',[]) and 0<=qy<q['pixels'].shape[0] and 0<=qx<q['pixels'].shape[1]
                    and q['pixels'][qy,qx]==pred[y,x]):couvertures.append(q.get('couche',0))
        if couvertures:hypotheses.add((classe,max(couvertures)+1))
    if len(hypotheses)!=1:return None,{**diag,'refus':'recouvrement_absent_ou_ambigu'}
    classe,couche=next(iter(hypotheses))
    def relever(v):
        v=copy.deepcopy(v)
        for q in v.statiques:
            if set(np.unique(q['pixels']))-{-1}=={classe}:q['couche']=max(q.get('couche',0),couche)
        return v
    c=chaine(relever(source.perception));controle,etat=c.rejouer();sol=None
    if etat is None:
        from revision_sol_revele import proposer as sol_revele
        c,sol=sol_revele(c)
        if c is None:return None,{**diag,'refus':'rejeu_avec_sol','sol':sol}
        controle,etat=c.rejouer()
    validations=[];ancien=getattr(source,'modele_source_transfert',None)
    while ancien is not None:
        v=relever(ancien.perception)
        test=Chaine(v,ancien.programme,ancien.grilles,ancien.lots,ancien.actions,
                    films=[e['images'] if e else None for e in ancien.films.entrees])
        ctrl,e=test.rejouer();validations.append(ctrl)
        if e is None:return None,{**diag,'refus':'contre_exemple_source','controle':ctrl}
        ancien=getattr(ancien,'modele_source_transfert',None)
    c.activer_atms();c.revision_locale={'operateur':'recouvrement_roles','classe_observee':classe,'couche':couche,'generalisation':False}
    return c,{**diag,'admis':True,'classe_observee':classe,'couche':couche,'controle':controle,'sources':validations,'sol':sol}
