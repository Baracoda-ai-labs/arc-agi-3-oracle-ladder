"""Spécialiser une garde de face par un rôle observé, sous rejeu complet."""
import copy
import numpy as np
from chaine_coherente import Chaine
from transfert_roles import RolesReaffectes


def proposer(source):
    diag={'admis':False,'provisoire':True,'but_change':False,'mouvements_changes':False}
    def refus(r,**kw):return None,{**diag,'refus':r,**kw}
    if type(source.perception) is not RolesReaffectes or not source.lots:
        return refus('representation_non_applicable')
    films=[e['images'] if e else None for e in source.films.entrees]
    avant=Chaine(source.perception,source.programme,source.grilles[:-1],source.lots[:-1],source.actions,films=films[:-1])
    _,cur=avant.rejouer()
    if cur is None:return refus('prefixe_deja_refute')
    if len(source.lots[-1]['actions'])!=1:return refus('action_non_atomique')
    pc,scene=cur;pc.step(scene,source.action_tuple(source.lots[-1]['actions'][0]))
    erreurs={tuple(map(int,p)) for p in np.argwhere(source.perception.rendu(scene)!=source.perception.vue(source.grilles[-1]))}
    if not erreurs:return refus('aucun_ecart')
    candidats=[]
    for i,r in enumerate(source.programme['regles']):
        if not r['nom'].startswith('face_support_'):continue
        # Contrat des règles produites par regle_face_support ; rien d'autre n'est réécrit.
        try:
            condition=r['alors'][0][3][0][1][2]
            if condition[0]!='existe' or condition[1]!='$p':continue
            tag=condition[2][1]['tag'];garde=condition[3]
            face=garde[2][2][2]
            if not any(erreurs <= {(o['y']+y,o['x']+x) for y,x in o.get('attrs',{}).get(face,[])}
                       for o in scene.sprites if 'piece' in o.get('tags',[])):continue
        except (KeyError,IndexError,TypeError):continue
        tags=sorted({t for o in scene.sprites if tag in o.get('tags',[]) for t in o['tags'] if t!=tag})
        for exclu in tags:
            clause=['non',['a_tag','$p',exclu]]
            if clause in garde:continue
            p=copy.deepcopy(source.programme);p['regles'][i]['alors'][0][3][0][1][2][3].append(clause)
            p=partager_gardes(p)
            v=copy.deepcopy(source.perception);v.programme_transfere=copy.deepcopy(p)
            c=Chaine(v,p,source.grilles,source.lots,source.actions,coups_deja_joues=source.coups,reserve=source.limite,films=films)
            controle,etat=c.rejouer()
            if etat is not None:candidats.append((c,controle,r['nom'],exclu))
    if len(candidats)!=1:return refus('garde_absente_ou_ambigue',candidats=len(candidats))
    c,controle,regle,tag=candidats[0]
    from memoire_reparations_roles import conserver
    conserver(source,c)
    c.activer_atms();c.contraste_revision=copy.deepcopy(source.programme)
    c.revision_locale={'operateur':'garde_face','portee':'prefixe_observe','generalisation':False}
    return c,{**diag,'admis':True,'regle':regle,'tag_exclu':tag,'controle':controle}


def partager_gardes(programme):
    """Hypothèse de symétrie : mêmes exclusions pour le même rôle de support.

    Le programme retourné doit toujours être admis par rejeu avant utilisation.
    """
    p=copy.deepcopy(programme);groupes={}
    for r in p['regles']:
        if not r['nom'].startswith('face_support_'):continue
        try:
            voisin=r['alors'][0][3][0][1][2]
            if voisin[:2]!=['existe','$p']:continue
            tag=voisin[2][1]['tag'];garde=voisin[3]
            groupes.setdefault(tag,[]).append(garde)
        except (KeyError,IndexError,TypeError):continue
    for gardes in groupes.values():
        clauses=[]
        for garde in gardes:
            for x in garde[1:]:
                if (isinstance(x,list) and len(x)==2 and x[0]=='non'
                    and isinstance(x[1],list) and len(x[1])==3 and x[1][:2]==['a_tag','$p']
                    and x not in clauses):clauses.append(x)
        for garde in gardes:
            garde.extend(copy.deepcopy(x) for x in clauses if x not in garde)
    return p
