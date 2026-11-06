"""Étendre le paramètre existant des classes glissables depuis un film observé."""
import copy
import numpy as np
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import _composantes,NOMS
from glissade_distance_observee import apprendre,compiler
from transfert_roles import RolesReaffectes


def proposer(source,precedents):
    d={'admis':False,'provisoire':True,'nouvelle_loi':False,'but_modifie':False}
    if type(source.perception) is not RolesReaffectes or not source.lots:
        return None,{**d,'refus':'representation_non_applicable'}
    films=[e['images'] if e else None for e in source.films.entrees]
    if films[-1] is None or len(films[-1])<3:return None,{**d,'refus':'film_insuffisant'}
    try:classe,glisse,preuves=apprendre(source.perception,precedents)
    except (ValueError,KeyError,TypeError,IndexError) as exc:return None,{**d,'refus':str(exc)}
    # N'accepter que le réexport exact de la glissade déjà présente.
    ancien=compiler(source.perception,source.programme,classe,glisse)
    noms={r['nom'] for r in ancien['regles'][len(source.programme['regles']):]}
    regles={r['nom']:r for r in source.programme['regles'] if r['nom'] in noms}
    attendues={r['nom']:r for r in ancien['regles'] if r['nom'] in noms}
    if regles!=attendues:return None,{**d,'refus':'glissade_heritee_non_identique'}
    avant=Chaine(source.perception,source.programme,source.grilles[:-1],source.lots[:-1],source.actions,films=films[:-1])
    ctrl,cur=avant.rejouer()
    if cur is None:return None,{**d,'refus':'prefixe_deja_refute'}
    if len(source.lots[-1]['actions'])!=1:return None,{**d,'refus':'action_non_atomique'}
    act=source.action_tuple(source.lots[-1]['actions'][0]);codes=[a for a,n in NOMS.items() if (n,)==act]
    if len(codes)!=1:return None,{**d,'refus':'direction_non_etablie'}
    pas=source.perception.source.mouvements[codes[0]]
    images=[np.asarray(source.grilles[-2]),*[np.asarray(f) for f in films[-1]]]
    composants=[set(_composantes(g,source.perception.fond)) for g in images]
    fixes=set.intersection(*composants);candidats=[]
    for col,forme,x,y in composants[0]-fixes:
        if col in glisse[2]:continue
        chemin=[]
        for etat in composants:
            matches=[(xx,yy) for cc,ff,xx,yy in etat-fixes if cc==col and ff==forme]
            if len(matches)!=1:break
            if not chemin or chemin[-1]!=matches[0]:chemin.append(matches[0])
        else:
            if len(chemin)<3:continue
            if {(q[0]-p[0],q[1]-p[1]) for p,q in zip(chemin,chemin[1:])}!={pas}:continue
            if abs(chemin[-1][0]-x)+abs(chemin[-1][1]-y)!=glisse[0]:continue
            candidats.append((int(col),chemin))
    if len(candidats)!=1:return None,{**d,'refus':'classe_passive_ambigue','candidats':len(candidats)}
    col,chemin=candidats[0]
    # Sol révélé, uniquement aux anciennes cases du support désormais mobile.
    objet=next((o for o in composants[0] if o[0]==col and (o[2],o[3])==chemin[0]),None)
    forme=objet[1];x,y=chemin[0]
    h=max(py for px,py in forme)+1;w=max(px for px,py in forme)+1
    sol=np.full((h,w),-1,dtype=np.int16)
    for px,py in forme:
        valeurs=set()
        for im,etat in zip(images[-1:],composants[-1:]):
            couverts={(xx+fx,yy+fy) for cc,ff,xx,yy in etat if cc==col for fx,fy in ff}
            if (x+px,y+py) not in couverts:valeurs.add(int(im[y+py,x+px]))
        if len(valeurs)!=1 or not valeurs<=set(glisse[1]):
            return None,{**d,'refus':'sol_sous_support_non_etabli'}
        sol[py,px]=next(iter(valeurs))
    nouveau=(glisse[0],glisse[1],glisse[2]|{col},*glisse[3:])
    base=copy.deepcopy(source.programme);base['regles']=[r for r in base['regles'] if r['nom'] not in noms]
    exporte=compiler(source.perception,base,classe,nouveau)
    remplacement={r['nom']:r for r in exporte['regles'] if r['nom'] in noms}
    p=copy.deepcopy(source.programme)
    p['regles']=[remplacement.get(r['nom'],r) for r in p['regles']]
    vue=copy.deepcopy(source.perception);vue.programme_transfere=copy.deepcopy(p)
    vue.statiques.append({'x':x,'y':y,'pixels':sol,'couche':-1})
    vue.sols_reveles=copy.deepcopy(getattr(vue,'sols_reveles',[]))+[{'x':x,'y':y,'pixels':sol.tolist(),'origine':'film_observe'}]
    c=Chaine(vue,p,source.grilles,source.lots,source.actions,coups_deja_joues=source.coups,reserve=source.limite,films=films)
    controle,etat=c.rejouer()
    if etat is None:return None,{**d,'refus':'rejeu_prefixe','controle':controle,'classe':col}
    from memoire_reparations_roles import conserver
    conserver(source,c)
    c.activer_atms();c.contraste_revision=copy.deepcopy(source.programme)
    c.revision_locale={'operateur':'classe_glissable','portee':'film_observe','generalisation':False}
    c.preuve_classe_glissable={'classe':col,'chemin':chemin,'distance_heritee':glisse[0],'sol_revele_pixels':len(forme)}
    return c,{**d,'admis':True,'controle':controle,**c.preuve_classe_glissable,'selection_modifiee':False,'validation_future':False}
