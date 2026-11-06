"""Transfert des mécanismes de sélection/freinage, géométrie observée par instance."""
import copy
import numpy as np
from chaine_coherente import Chaine
from selection_observee import SelectionObservee
from freinage_passif import FreinagePassif
from chrysalide.arc3.moteur import MoteurFormel, _composantes, _sprite
from chrysalide.arc3.ontologie_exec import Scene


def voisinage(dx,dy):
    o,p='$o','$p'
    if dx>0: axe=['=', ['x',p], ['+', ['x',o], ['largeur',o]]]
    elif dx<0: axe=['=', ['x',o], ['+', ['x',p], ['largeur',p]]]
    elif dy>0: axe=['=', ['y',p], ['+', ['y',o], ['hauteur',o]]]
    else: axe=['=', ['y',o], ['+', ['y',p], ['hauteur',p]]]
    pos,dim=('y','hauteur') if dx else ('x','largeur')
    return ['et',['!=',o,p],axe,
        ['<',[pos,o],['+',[pos,p],[dim,p]]],['<',[pos,p],['+',[pos,o],[dim,o]]]]


def regle_face(dx,dy,couleur,selection):
    return {'nom':f'face_contact_{dx}_{dy}','phase':1,'quand':True,
        'alors':[['pour','$o',['objets',{'tag':'piece'}],[['si_alors',
            ['et',['=',['pixel','$o',['attr','$o','marqueur_x'],['attr','$o','marqueur_y']],selection],
             ['existe','$p',['objets',{'tag':'piece'}],voisinage(dx,dy)]],
            [['pour','$face',['attr','$o',f'face_{dx}_{dy}'],[
                ['ecrire','$o',['elem','$face',0],['elem','$face',1],couleur]]]],[]]]]]}


def parametrer(source,programme):
    h,w=source.coque.shape;mx,my=source.mx,source.my
    def walk(x,dx=0,dy=0,selection=False):
        if not isinstance(x,list):return copy.deepcopy(x)
        if len(x)==4 and x[0]=='pixel' and x[2:]==[mx,my]:
            return ['pixel',x[1],['attr',x[1],'marqueur_x'],['attr',x[1],'marqueur_y']]
        if len(x)==5 and x[0]=='ecrire' and x[2:4]==[my,mx]:
            return ['pour','$mark',['attr',x[1],'marqueur_cases'],[
                ['ecrire',x[1],['elem','$mark',0],['elem','$mark',1],walk(x[4],dx,dy,selection)]]]
        for var in ('$o','$p'):
            for axe,dim,pas,taille in [('x','largeur',dx,w),('y','hauteur',dy,h)]:
                if x==['+',[axe,var],pas+taille]:
                    return ['+',['+',[axe,var],pas],[dim,var]]
        ancien=['et',['!=','$o','$p'],['=',['x','$p'],['+',['x','$o'],dx]],['=',['y','$p'],['+',['y','$o'],dy]]]
        if (dx or dy) and x==ancien:return voisinage(dx,dy)
        return [walk(v,dx,dy,selection) for v in x]
    p=copy.deepcopy(programme)
    for r in p['regles']:
        nom=r['nom']
        if nom.startswith('mouvement_'):
            action=int(nom.rsplit('_',1)[1]);dx,dy=source.mouvements[action]
            r['alors']=walk(r['alors'],dx,dy)
        elif nom=='selection_observee':
            r['quand']=walk(r['quand'],selection=True);r['alors']=walk(r['alors'],selection=True)
        elif nom=='coque_hors_contact':
            r['alors']=[['pour','$o',['objets',{'tag':'piece'}],[['pour','$case',['attr','$o','coque_cases'],[
                ['ecrire','$o',['elem','$case',0],['elem','$case',1],['elem','$case',2]]]]]]]
        elif nom.startswith('face_contact_'):
            dx,dy=map(int,nom.removeprefix('face_contact_').split('_'))
            couleur=next(v[3] for v in source.faces if v[:2]==(dx,dy))
            r.update(regle_face(dx,dy,couleur,source.selection))
        elif nom=='toutes_cibles_hypothese':
            condition=r['quand'][3][3]
            condition.extend([['=',['largeur','$o'],['largeur','$t']],['=',['hauteur','$o'],['hauteur','$t']]])
    return p


class RolesReaffectes(SelectionObservee):
    def __init__(self,source,image):
        self.source=copy.deepcopy(source)
        self.hud=copy.deepcopy(source.hud);self.fond=source.fond
        self.mx,self.my=source.mx,source.my
        self.selection=source.selection
        self.cibles_meme_forme=True
        self.coque=source.coque.copy()
        self.image=np.asarray(image).copy()
        g=self.vue(image);couleurs=set(np.unique(source.coque))-{-1}
        if len(couleurs)!=1:raise ValueError('Coque multicolore : attribution non étayée')
        couleur=int(next(iter(couleurs)))
        composants=_composantes(np.where(g==couleur,1,0),0)
        pieces=[];couverture=np.zeros(g.shape,bool)
        for _,forme,x,y in composants:
            w=max(px for px,py in forme)+1;h=max(py for px,py in forme)+1
            px=g[y:y+h,x:x+w].copy();marque=px!=couleur
            ys,xs=np.nonzero(marque)
            if not len(xs):raise ValueError('Coque sans marqueur attribuable')
            mx,my=int(xs.min()),int(ys.min());mw,mh=int(xs.max()-mx+1),int(ys.max()-my+1)
            rectangle=np.zeros(px.shape,bool);rectangle[my:my+mh,mx:mx+mw]=True
            if not np.array_equal(marque,rectangle) or len(set(px[marque]))!=1 or mx==0 or my==0 or mx+mw>=w or my+mh>=h:
                raise ValueError('Coque ou marqueur incomplet')
            valeur=int(px[my,mx])
            if valeur not in (source.selection,source.inactif,source.inactif_apres_selection):raise ValueError('Rôle marqueur inconnu')
            attrs={'marqueur_x':mx,'marqueur_y':my,'marqueur_largeur':mw,'marqueur_hauteur':mh,
                'marqueur_cases':[(int(iy),int(ix)) for iy,ix in np.argwhere(marque)],
                'coque_cases':[(int(iy),int(ix),int(px[iy,ix])) for iy,ix in np.argwhere(~marque)],
                'marqueur_repos':source.inactif_apres_selection if valeur==source.selection else valeur}
            for dx,dy,*_ in source.faces:
                attrs[f'face_{dx}_{dy}']=[(iy,0 if dx<0 else w-1) for iy in range(h)] if dx else [(0 if dy<0 else h-1,ix) for ix in range(w)]
            pieces.append({'x':x,'y':y,'pixels':px,'tags':['piece'],'couche':1,'attrs':attrs})
            couverture[y:y+h,x:x+w]=True
        if not pieces or not np.all(couverture[g==couleur]):raise ValueError('Couverture des pièces incomplète')
        self.pieces=pieces;self.decor=g.copy();self.inconnus=[]
        for p in pieces:
            x,y=p['x'],p['y'];h,w=p['pixels'].shape
            voisins=[]
            for yy in range(max(0,y-1),min(g.shape[0],y+h+1)):
                for xx in range(max(0,x-1),min(g.shape[1],x+w+1)):
                    if not couverture[yy,xx]:voisins.append(int(g[yy,xx]))
            possibles=set(voisins)&source.libres
            if len(possibles)!=1:raise ValueError('Sol caché ambigu depuis sols libres observés')
            sol=possibles.pop();self.decor[y:y+h,x:x+w]=sol
            self.inconnus.append({'boite':[x,y,w,h],'sol_hypothetique':sol})
        self.statiques=[_sprite(o) for o in _composantes(self.decor,self.fond)]
        self.statiques.append({'pixels':np.where(self.decor==self.fond,self.fond,-1),'x':0,'y':0,'couche':0})
        self.cibles=[];formes={p['pixels'].shape for p in pieces}
        for s in self.statiques:
            px=s['pixels'];h,w=px.shape;x,y=s['x'],s['y']
            if (h,w) not in formes or not np.all(px>=0) or x<1 or y<1 or x+w>=g.shape[1] or y+h>=g.shape[0]:continue
            b=self.decor[y-1:y+h+1,x-1:x+w+1]
            per=np.concatenate([b[0],b[-1],b[1:-1,0],b[1:-1,-1]])
            if len(set(per.tolist()))==1:self.cibles.append((x,y,w,h,int(per[0])))

    def programme(self):
        return copy.deepcopy(self.programme_transfere)

    def vue(self,g):
        a=np.asarray(g).copy()
        for y,x in self.hud:a[y,x]=self.fond
        return a

    def signature_observation(self):
        return {'methode':'roles_reaffectes_geometrie','decor':self.decor.tolist(),'cibles':self.cibles,
                'masque_herite_provisoire':sorted(self.hud),'sols_hypothetiques':self.inconnus,
                'classes_bloquantes_poussee':getattr(self,'classes_bloquantes_poussee',[]),
                'calques_observes':[{'x':q['x'],'y':q['y'],'couche':q.get('couche',0),
                    'pixels':np.asarray(q['pixels']).tolist()} for q in self.statiques]}

    def scene(self,g):
        if not np.array_equal(self.vue(g),self.vue(self.image)):raise ValueError('Instance différente : utiliser état rejoué')
        sprites=[];s=self.source
        for o in self.statiques:
            colors=set(np.unique(o['pixels']))-{-1}
            tags=['decor'] if colors <= s.libres|s.optimistes else (['bloqueur','mur'] if self.fond in colors else ['bloqueur'])
            if colors&s.sorties:tags.append('frein')
            if colors & set(getattr(self,'classes_bloquantes_poussee',())):tags.append('obstacle_poussee')
            sprites.append({**copy.deepcopy(o),'tags':tags})
        sprites+=copy.deepcopy(self.pieces)
        for x,y,w,h,_ in self.cibles:sprites.append({'x':x,'y':y,'pixels':self.decor[y:y+h,x:x+w].copy(),'couche':0,'tags':['cible']})
        return Scene(self.image.shape,self.fond,self.fond,sprites)


def reaffecter(source,image,actions,coups_deja_joues=0,reserve=150):
    m=source.perception
    if type(m) not in (SelectionObservee,FreinagePassif,RolesReaffectes) or source.refute:raise ValueError('Source sélection/freinage non étayée')
    if m.programme()!=source.programme or source.rejouer()[1] is None:raise ValueError('Source non synchronisée ou non admissible')
    prototype=m.source if isinstance(m,RolesReaffectes) else m
    vue=RolesReaffectes(prototype,image)
    if hasattr(m,'classes_bloquantes_poussee'):
        vue.classes_bloquantes_poussee=copy.deepcopy(m.classes_bloquantes_poussee)
    programme=copy.deepcopy(source.programme) if isinstance(m,RolesReaffectes) else parametrer(m,source.programme)
    from buts_roles_herites import reaffecter_couverture
    buts_suspendus=[]
    if not vue.cibles:
        buts_suspendus=[copy.deepcopy(r) for r in programme['regles']
                       if r.get('alors')==[['niveau_suivant']]]
        if any(r.get('nom') not in ('toutes_cibles_hypothese','couverture_heritee_elargie_hypothese')
               for r in buts_suspendus):
            raise ValueError('Suspension de but hors contrat')
        programme['regles']=[r for r in programme['regles'] if r not in buts_suspendus]
        preuve_but=None
    else:
        programme,preuve_but=reaffecter_couverture(source,vue,programme)
    vue.programme_transfere=copy.deepcopy(programme)
    c=Chaine(vue,programme,[np.asarray(image).tolist()],[],actions,coups_deja_joues=coups_deja_joues,reserve=reserve)
    scene=vue.scene(image)
    if not np.array_equal(vue.rendu(scene),vue.vue(image)):raise ValueError('Projection initiale non exacte')
    check,etat=c.rejouer()
    if etat is None or not all(check.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):raise ValueError('Transfert non admissible')
    c.modele_source_transfert=copy.deepcopy(source)
    if not vue.cibles:
        c.but_inconnu=True
        c.preuve_but_suspendu={'raison':'cibles_non_reaffectees','regles_source':buts_suspendus,
            'source':source.signature(),'but_refute':False,'nouvelle_physique':False}
    c.preuve_transfert_roles={'metadonnees_source':{n:copy.deepcopy(getattr(source,n))
        for n in ('preuve_revision_but','preuve_classe_glissable','preuve_but_elargi','revision_locale') if hasattr(source,n)},
        'validation_nouvelle_instance':False}
    if preuve_but is not None:
        c.preuve_but_elargi=preuve_but
        c.but_hypothese_non_confirmee=True
    if hasattr(source,'preuve_classe_glissable'):
        c.preuve_classe_glissable=copy.deepcopy(source.preuve_classe_glissable)
    c.activer_atms()
    return c,{'admis':True,'controle':check,'but_suspendu':not bool(vue.cibles),'programme_identique':programme==source.programme,
        'mecanismes_conserves':True,'parametres_adaptes':['dimensions','marqueurs','faces_contact','cibles_de_meme_forme'],
        'pieces_completes':len(vue.pieces),'cibles':len(vue.cibles),'masque_herite_provisoire':True,
        'sols_hypothetiques':vue.inconnus,'validation_dynamique_nouveau_niveau':False,
        'hypotheses_non_departagees':['pas fixe hérité vs proportionnel à taille',
            'but : dimensions compatibles en plus des ancres', 'marqueur rectangulaire uniforme',
            'contact : adjacence des boîtes avec recouvrement orthogonal']}
