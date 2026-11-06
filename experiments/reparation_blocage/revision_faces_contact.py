"""Rendu de contact pour mobile suivi, indépendant du clic et du but."""
import copy
import numpy as np
from chaine_coherente import Chaine
from faces_contact import regles_faces
from chrysalide.arc3.moteur import NOMS


def proposer(source):
    m=source.perception
    from transfert_roles import RolesReaffectes
    if isinstance(m,RolesReaffectes):
        return proposer_roles(source)
    diag={'admis':False,'masque_change':False,'mouvements_changes':False}
    def fini(c=None,**infos):return c,{**diag,**infos}
    if not hasattr(m,'mobiles') or not hasattr(m,'statiques') or not source.lots:
        return fini(refus='representation_non_applicable')
    films=[e['images'] if e else None for e in source.films.entrees]
    avant=Chaine(m,source.programme,source.grilles[:-1],source.lots[:-1],source.actions,films=films[:-1])
    _,courant=avant.rejouer()
    if courant is None:return fini(refus='prefixe_deja_refute')
    if len(source.lots[-1]['actions'])!=1:return fini(refus='action_non_atomique')
    action=source.action_tuple(source.lots[-1]['actions'][0])
    codes=[k for k,v in NOMS.items() if (v,)==action]
    if not codes:return fini(refus='direction_inconnue')
    pc,scene=courant;pc.step(scene,action)
    pred=m.rendu(scene);obs=m.vue(source.grilles[-1])
    erreurs={tuple(map(int,p)) for p in np.argwhere(pred!=obs)}
    if not erreurs:return fini(refus='aucune_divergence')
    hypotheses=[];regles=[]
    for i,motif in enumerate(m.mobiles):
        dx,dy=m.mouvements[i].get(codes[0],(0,0))
        haut,large=motif.shape
        if bool(dx)==bool(dy) or (dx and abs(dx)!=large) or (dy and abs(dy)!=haut):continue
        face=[(y,0 if dx<0 else large-1) for y in range(haut)] if dx else [(0 if dy<0 else haut-1,x) for x in range(large)]
        for mobile in (o for o in scene.sprites if f'mobile_{i}' in o.get('tags',[])):
            x,y=mobile['x'],mobile['y']
            if erreurs!={(y+iy,x+ix) for iy,ix in face}:continue
            couleurs={int(obs[y+iy,x+ix]) for iy,ix in face}
            if len(couleurs)!=1:continue
            voisins=[]
            for j,v in enumerate(m.statiques):
                px=np.asarray(v['pixels'])
                if px.shape!=motif.shape:continue
                bord=np.zeros(px.shape,bool);bord[[0,-1],:]=True;bord[:,[0,-1]]=True
                if np.array_equal(px[bord],motif[bord]):voisins.append(j)
            if not any((m.statiques[j]['x'],m.statiques[j]['y'])==(x+dx,y+dy) for j in voisins):continue
            couleur=couleurs.pop()
            hypotheses.append(dict(mobile=i,dx=dx,dy=dy,face=face,couleur=couleur,voisins=voisins))
            select=['objets',{'tag':f'statique_{voisins[0]}'}]
            for j in voisins[1:]:select=['+',select,['objets',{'tag':f'statique_{j}'}]]
            regles+=regles_faces(motif,[(dx,dy,face,couleur)],['objets',{'tag':f'mobile_{i}'}],True,select)
    if not hypotheses:return fini(refus='pas_de_face_adjacente_etayee')
    programme=copy.deepcopy(source.programme);programme['regles']+=regles
    c=Chaine(m,programme,source.grilles,source.lots,source.actions,
             coups_deja_joues=source.coups,reserve=source.limite,films=films)
    controle,etat=c.rejouer()
    if etat is None or not all(controle.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
        return fini(refus='rejeu_prefixe',controle=controle)
    c.activer_atms();c.contraste_revision=copy.deepcopy(source.programme)
    c.revision_locale={'operateur':'face_contact','portee':'prefixe_observe','generalisation':False}
    return fini(c,admis=True,controle=controle,hypotheses=hypotheses)


def proposer_roles(source):
    from transfert_roles import regle_face
    m=source.perception
    diag={'admis':False,'masque_change':False,'mouvements_changes':False}
    def fini(c=None,**infos):return c,{**diag,**infos}
    if not source.lots:return fini(refus='aucune_transition')
    films=[e['images'] if e else None for e in source.films.entrees]
    avant=Chaine(m,source.programme,source.grilles[:-1],source.lots[:-1],source.actions,films=films[:-1])
    _,courant=avant.rejouer()
    if courant is None:return fini(refus='prefixe_deja_refute')
    if len(source.lots[-1]['actions'])!=1:return fini(refus='action_non_atomique')
    action=source.action_tuple(source.lots[-1]['actions'][0])
    codes=[k for k,v in NOMS.items() if (v,)==action]
    if not codes:return fini(refus='direction_inconnue')
    pc,scene=courant;pc.step(scene,action)
    pred=m.rendu(scene);obs=m.vue(source.grilles[-1])
    erreurs={tuple(map(int,p)) for p in np.argwhere(pred!=obs)}
    pieces=[p for p in scene.sprites if 'piece' in p.get('tags',[])]
    hypotheses=[]
    ph,pw=m.source.coque.shape
    for p in pieces:
        at=p['attrs'];x,y=p['x'],p['y'];h,w=p['pixels'].shape
        if p['pixels'][at['marqueur_y'],at['marqueur_x']]!=m.selection:continue
        for dx,dy in ((-pw,0),(pw,0),(0,-ph),(0,ph)):
            face=[(iy,0 if dx<0 else w-1) for iy in range(h)] if dx else [(0 if dy<0 else h-1,ix) for ix in range(w)]
            if not erreurs or not erreurs<={(y+iy,x+ix) for iy,ix in face}:continue
            couleurs={int(obs[y+iy,x+ix]) for iy,ix in face}
            if len(couleurs)!=1:continue
            sx,sy=int(np.sign(dx)),int(np.sign(dy))
            for q in scene.sprites:
                if q is p:continue
                tag='piece' if 'piece' in q.get('tags',[]) else ('bloqueur' if 'bloqueur' in q.get('tags',[]) else None)
                if tag is None:continue
                qx,qy=q['x'],q['y'];qh,qw=q['pixels'].shape
                occupes=[(x+ix+sx-qx,y+iy+sy-qy) for iy,ix in face]
                if not all(0<=xx<qw and 0<=yy<qh and q['pixels'][yy,xx]>=0 for xx,yy in occupes):continue
                classes=set(np.unique(q['pixels']))-{-1}
                if tag!='piece' and len(classes)!=1:continue
                classe=int(next(iter(classes))) if tag!='piece' else None
                hypotheses.append((dx,dy,face,next(iter(couleurs)),tag,classe))
    uniques={(dx,dy,col,tag,classe) for dx,dy,face,col,tag,classe in hypotheses}
    if len(uniques)!=1:return fini(refus='pas_de_face_adjacente_etayee' if not uniques else 'contact_ambigu')
    dx,dy,face,couleur,tag,classe=hypotheses[0]
    vue=copy.deepcopy(m);programme=copy.deepcopy(source.programme)
    nouvelle=regle_face(dx,dy,couleur,m.selection) if tag=='piece' else regle_face_support(dx,dy,couleur,m.selection,tag)
    if tag!='piece':
        nouvelle['alors'][0][3][0][1][2][2][1]['couleur']=classe
        nouvelle['nom']+=f'_classe_{classe}'
    programme['regles'].append(nouvelle)
    from revision_garde_face import partager_gardes
    programme=partager_gardes(programme)
    h,w=vue.source.coque.shape
    prototype=[(iy,0 if dx<0 else w-1) for iy in range(h)] if dx else [(0 if dy<0 else h-1,ix) for ix in range(w)]
    if not any(f[:2]==(dx,dy) for f in vue.source.faces):
        vue.source.faces.append((dx,dy,prototype,couleur))
    for p in vue.pieces:
        h,w=p['pixels'].shape
        p['attrs'][f'face_{dx}_{dy}']=[(iy,0 if dx<0 else w-1) for iy in range(h)] if dx else [(0 if dy<0 else h-1,ix) for ix in range(w)]
    vue.programme_transfere=copy.deepcopy(programme)
    c=Chaine(vue,programme,source.grilles,source.lots,source.actions,
             coups_deja_joues=source.coups,reserve=source.limite,films=films)
    controle,etat=c.rejouer()
    if etat is None or not all(controle.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
        return fini(refus='rejeu_prefixe',controle=controle)
    from memoire_reparations_roles import conserver
    controles_sources=[]
    ancien=getattr(source,'modele_source_transfert',None)
    while ancien is not None:
        p=copy.deepcopy(ancien.programme);p['regles'].append(copy.deepcopy(nouvelle))
        v=copy.deepcopy(ancien.perception);v.programme_transfere=copy.deepcopy(p)
        test=Chaine(v,p,ancien.grilles,ancien.lots,ancien.actions,
                    films=[e['images'] if e else None for e in ancien.films.entrees])
        ctrl,etat_source=test.rejouer();controles_sources.append(ctrl)
        if etat_source is None:return fini(refus='contre_exemple_niveau_source',controle=ctrl)
        ancien=getattr(ancien,'modele_source_transfert',None)
    conserver(source,c)
    c.activer_atms();c.contraste_revision=copy.deepcopy(source.programme)
    c.revision_locale={'operateur':'face_contact','portee':'prefixe_observe','generalisation':False}
    return fini(c,admis=True,controle=controle,orientation=[dx,dy],couleur=couleur,voisin_tag=tag,
                pixels_observes=len(face),classe_support=classe,controles_sources=controles_sources,validation_suffixe=False)


def regle_face_support(dx,dy,couleur,selection,tag):
    """Même effet de rendu ; toute la face doit toucher des pixels du support."""
    from transfert_roles import regle_face
    r=regle_face(dx,dy,couleur,selection)
    r['nom']=f'face_support_{tag}_{dx}_{dy}'
    sx,sy=int(np.sign(dx)),int(np.sign(dy))
    xx=['-',['+',['+',['x','$o'],['elem','$bord',1]],sx],['x','$p']]
    yy=['-',['+',['+',['y','$o'],['elem','$bord',0]],sy],['y','$p']]
    occupe=['et',['>=',xx,0],['>=',yy,0],['<',xx,['largeur','$p']],['<',yy,['hauteur','$p']],['>=',['pixel','$p',xx,yy],0]]
    voisin=['existe','$p',['objets',{'tag':tag}],['et',['!=','$o','$p'],
        ['tous','$bord',['attr','$o',f'face_{dx}_{dy}'],occupe]]]
    r['alors'][0][3][0][1][2]=voisin
    return r
