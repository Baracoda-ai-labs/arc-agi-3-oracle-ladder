"""Réutiliser la poussée en chaîne du DSL après mouvement secondaire filmé."""
import copy
import numpy as np
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import NOMS
from transfert_roles import RolesReaffectes
from memoire_reparations_roles import conserver


def parametrer(source,classe):
    p=copy.deepcopy(source.programme);obstacles=set();changements=0
    def walk(x):
        nonlocal changements
        if not isinstance(x,list):return x
        if (len(x)==5 and x[:2]==['libre','$p'] and isinstance(x[4],dict)
            and 'couleur' in x[4] and (x[2] or x[3])):
            if x[4]['couleur']==classe:return True
            obstacles.add(x[4]['couleur'])
        if len(x)==4 and x[:2]==['deplacer','$p']:
            changements+=1
            return ['pousser','$p',x[2],x[3],{'tag':'obstacle_poussee'},{'tag':'piece'},'_gl_stop']
        return [walk(v) for v in x]
    for r in p['regles']:
        if r['nom'].startswith('glissade c'):r['alors']=walk(r['alors'])
    return p,obstacles,changements


def proposer(source):
    diag={'admis':False,'provisoire':True,'but_change':False,'brique':'langage.pousser'}
    if type(source.perception) is not RolesReaffectes or not source.lots:return None,{**diag,'refus':'representation_non_applicable'}
    films=[e['images'] if e else None for e in source.films.entrees]
    if films[-1] is None or len(films[-1])<3:return None,{**diag,'refus':'film_insuffisant'}
    if len(source.lots[-1]['actions'])!=1:return None,{**diag,'refus':'action_non_atomique'}
    m=source.perception;action=source.action_tuple(source.lots[-1]['actions'][0]);codes=[k for k,v in NOMS.items() if (v,)==action]
    if len(codes)!=1 or codes[0] not in m.source.mouvements:return None,{**diag,'refus':'direction_non_etablie'}
    pas=m.source.mouvements[codes[0]]
    avant=Chaine(m,source.programme,source.grilles[:-1],source.lots[:-1],source.actions,films=films[:-1]);_,cur=avant.rejouer()
    if cur is None:return None,{**diag,'refus':'prefixe_deja_refute'}
    _,scene=cur;hypotheses=[]
    for o in scene.sprites:
        if 'piece' not in o.get('tags',[]):continue
        at=o['attrs'];marque=o['pixels'][at['marqueur_y'],at['marqueur_x']]
        if marque==m.selection:continue
        autres={(q['x'],q['y']) for q in scene.sprites if q is not o and 'piece' in q.get('tags',[])}
        chemin=[]
        for g in [source.grilles[-2],*films[-1]]:
            ps=set(m.source.positions(np.asarray(g)))-autres
            if len(ps)!=1:break
            pos=next(iter(ps))
            if not chemin or chemin[-1]!=pos:chemin.append(pos)
        else:
            if (len(chemin)>=3 and chemin[0]==(o['x'],o['y'])
                and {(b[0]-a[0],b[1]-a[1]) for a,b in zip(chemin,chemin[1:])}=={pas}):hypotheses.append(chemin)
    if len(hypotheses)!=1:return None,{**diag,'refus':'mouvement_secondaire_absent_ou_ambigu'}
    couleurs=set(np.unique(m.source.coque))-{-1}
    if len(couleurs)!=1:return None,{**diag,'refus':'classe_coque_ambigue'}
    classe=int(next(iter(couleurs)));sources=[];ancien=getattr(source,'modele_source_transfert',None)
    while ancien is not None:sources.append(ancien);ancien=getattr(ancien,'modele_source_transfert',None)
    sources=list(reversed(sources))+[source];controles=[]
    for s in sources:
        p,obstacles,n=parametrer(s,classe)
        if not n:return None,{**diag,'refus':'export_glissade_hors_contrat'}
        vue=copy.deepcopy(s.perception);vue.classes_bloquantes_poussee=sorted(obstacles);vue.programme_transfere=copy.deepcopy(p)
        c=Chaine(vue,p,s.grilles,s.lots,s.actions,coups_deja_joues=s.coups,reserve=s.limite,
                 films=[e['images'] if e else None for e in s.films.entrees])
        ctrl,etat=c.rejouer();controles.append(ctrl)
        if etat is None:return None,{**diag,'refus':'contre_exemple','controles':controles}
    conserver(source,c);c.activer_atms();c.revision_locale={'operateur':'poussee_chaine_existante','generalisation':False}
    return c,{**diag,'admis':True,'classe_secondaire':classe,'chemin_secondaire':hypotheses[0],'controles':controles}
