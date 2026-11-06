"""Distance passive issue des films, exportée par la glissade existante du moteur C."""
import copy
from types import SimpleNamespace
import numpy as np
from chaine_coherente import Chaine
from chrysalide.arc3.logique.induction import _glisse
from chrysalide.arc3.logique.export_langage import _glisse as exporter_glisse
from chrysalide.arc3.moteur import _composantes,_codes_c
from transfert_roles import RolesReaffectes,parametrer


def apprendre(vue,precedents):
    m=vue.source if isinstance(vue,RolesReaffectes) else vue
    couleurs=set(np.unique(m.coque))-{-1}
    if len(couleurs)!=1:raise ValueError('Famille de coque ambiguë')
    classe=int(next(iter(couleurs)));h,w=m.coque.shape
    forme=frozenset((x,y) for y in range(h) for x in range(w))
    preuves=[];poussees=[]
    for niveau,historique in enumerate(precedents):
        grilles=historique['grilles'];acts=_codes_c(historique['lots'])
        for t,film in enumerate(historique.get('films',[])):
            if film is None or len(film)<3 or acts is None or isinstance(acts[t],tuple):continue
            frames=[np.asarray(grilles[t]),*[np.asarray(g) for g in film]]
            positions=[set(m.positions(g)) for g in frames]
            fixes=set.intersection(*positions)
            if not any(frames[0][y+m.my,x+m.mx]==m.selection for x,y in fixes):continue
            chemin=[]
            for ps in positions:
                mobile=ps-fixes
                if len(mobile)!=1:break
                p=next(iter(mobile))
                if not chemin or p!=chemin[-1]:chemin.append(p)
            else:
                if len(chemin)<3:continue
                pas=m.mouvements.get(acts[t]);deltas={(q[0]-p[0],q[1]-p[1]) for p,q in zip(chemin,chemin[1:])}
                if pas is None or deltas!={pas}:continue
                x,y=chemin[0];xf,yf=chemin[-1]
                avant=(classe,forme,x,y);apres=(classe,forme,xf,yf)
                # Décor issu du niveau précédent, jamais de l'image cible N2.
                decor=m.decor
                e0=[avant,*_composantes(decor,m.fond)]
                e0 += [(classe,forme,px,py) for px,py in fixes]
                poussees.append((niveau,t,avant,apres,e0))
                preuves.append({'precedent':niveau,'coup':t+1,'chemin':chemin,'pas':pas,
                    'distance':abs(xf-x)+abs(yf-y)})
    regle=_glisse(poussees)
    if not regle:raise ValueError('Aucune glissade passive filmée attribuable')
    if regle[3] or regle[4]:raise ValueError('Extension de portée non traitée par ce raccord')
    return classe,regle,preuves


def compiler(vue,programme,classe,glisse):
    m=vue.source if isinstance(vue,RolesReaffectes) else vue
    th=SimpleNamespace(selection_clic=(classe,),glisse=glisse,
                       moves={(classe,a):d for a,d in m.mouvements.items()},fond_solide=False)
    h,w=vue.image.shape if isinstance(vue,RolesReaffectes) else m.decor.shape
    regles=exporter_glisse(th,w,h)
    # Les marqueurs sont des pixels de la pièce, pas des passagers séparés.
    def nettoyer(x):
        if not isinstance(x,list):return x
        if len(x)>=3 and x[:2]==['pour','$r']:return ['pour','$r',['liste'],[]]
        if len(x)==2 and x[0]=='+':return nettoyer(x[1])
        return [nettoyer(v) for v in x]
    for r in regles:r['alors']=nettoyer(r['alors'])
    if isinstance(vue,RolesReaffectes):
        marque=['pixel','$s',['attr','$s','marqueur_x'],['attr','$s','marqueur_y']]
    else:marque=['pixel','$s',m.mx,m.my]
    regles.append({'nom':'sélecteur observé pour glissade','phase':-0.4,'quand':True,
        'alors':[['pour','$s',['objets',{'tag':'piece'}],[['si_alors',['=',marque,m.selection],
            [['poser','_sel_x',['x','$s']],['poser','_sel_y',['y','$s']]],[]]]]]})
    p=copy.deepcopy(programme)
    def adapter(x):
        if not isinstance(x,list):return x
        if len(x)==4 and x[:3]==['poser_attr','$o','contact_avant']:
            return x[:3]+[['ou',x[3],['=',['etat','_pousse'],1]]]
        # La poussée passive est désormais exécutée par l'export glisse existant.
        if len(x)>=3 and x[0]=='si_alors' and isinstance(x[2],list) and any(
                isinstance(e,list) and e[:2]==['pour','$p'] for e in x[2]):
            return ['si_alors',False,[],[]]
        return [adapter(v) for v in x]
    for r in p['regles']:
        if r['nom'].startswith('mouvement_'):r['alors']=adapter(r['alors'])
    p['regles']+=regles
    return p


def proposer(source,precedents):
    diag={'admis':False,'hypothese':'distance_glissade_existante','provisoire':True}
    if not isinstance(source.perception,RolesReaffectes):return None,{**diag,'refus':'representation_non_applicable'}
    if getattr(source.perception,'distance_glissade_observee',None):return None,{**diag,'refus':'distance_deja_testee'}
    try:classe,glisse,preuves=apprendre(source.perception,precedents)
    except (ValueError,IndexError,KeyError,TypeError) as e:return None,{**diag,'refus':str(e)}
    validations=[]
    # Les films proposent ; toutes les transitions antérieures et leur finale contrôlent.
    for indice in sorted({p['precedent'] for p in preuves}):
        h=precedents[indice];prototype=source.perception.source
        try:
            ancienne_vue=RolesReaffectes(prototype,h['grilles'][0])
            ancien_programme=parametrer(prototype,prototype.programme())
            nouveau_programme=compiler(ancienne_vue,ancien_programme,classe,glisse)
            ancienne_vue.programme_transfere=copy.deepcopy(nouveau_programme)
            ancien=Chaine(ancienne_vue,nouveau_programme,h['grilles'],h['lots'],[],films=h.get('films'))
            controle,etat=ancien.rejouer()
            if etat is None:return None,{**diag,'refus':'precedent_refute','controle':controle}
            finale=h.get('finale')
            victoire=None
            if finale:
                pc,sc=etat
                for action in finale['actions']:pc.step(sc,Chaine.action_tuple(action))
                victoire=sc.issue in ('niveau','victoire')
                if not victoire:return None,{**diag,'refus':'finale_precedent_perdue'}
            validations.append({'precedent':indice,'controle':controle,'finale_confirmee':victoire})
        except (ValueError,KeyError,TypeError,IndexError) as exc:
            return None,{**diag,'refus':'precedent_non_verifiable','raison':str(exc)}
    vue=copy.deepcopy(source.perception)
    p=compiler(vue,source.programme,classe,glisse)
    vue.programme_transfere=copy.deepcopy(p)
    vue.distance_glissade_observee={'distance':glisse[0],'preuves':preuves}
    c=Chaine(vue,p,source.grilles,source.lots,source.actions,
             coups_deja_joues=source.coups,reserve=source.limite,
             films=[e['images'] if e else None for e in source.films.entrees])
    controle,etat=c.rejouer()
    diag.update(distance=glisse[0],traverse=sorted(glisse[1]),preuves=preuves,controle=controle,validations_precedents=validations)
    if etat is None or not all(controle.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
        return None,{**diag,'refus':'rejeu_prefixe'}
    c.activer_atms();c.contraste_revision=copy.deepcopy(source.programme)
    c.revision_locale={'operateur':'distance_glissade','portee':'precedents_et_prefixe','generalisation':False}
    return c,{**diag,'admis':True,'validation_future':False}
