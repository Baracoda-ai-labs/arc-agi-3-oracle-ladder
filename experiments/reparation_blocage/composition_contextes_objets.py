"""Composition bornée de deux programmes admis et commutations observées."""
import copy
import numpy as np
from chaine_coherente import Chaine
from chaine_agent_integree import canon,lots
from correspondance_contextes_objets import apprendre,reaffecter_observation,_roles
from chrysalide.arc3.moteur import MoteurFormel


def _tag(role):return f'{role[0]}_{role[1]}'


def _renommer(x,noms):
    if isinstance(x,str):return noms.get(x,x)
    if isinstance(x,list):return [_renommer(v,noms) for v in x]
    if isinstance(x,dict):return {k:_renommer(v,noms) for k,v in x.items()}
    return x


class SceneContextuelle(MoteurFormel):
    def __init__(self,vue,scene,image,preuve):
        self.vue_source=copy.deepcopy(vue);self.initiale=copy.deepcopy(scene)
        self.image=np.asarray(image).copy();self.preuve=copy.deepcopy(preuve)
    def vue(self,g):return self.vue_source.vue(g)
    def scene(self,g):
        if not np.array_equal(self.vue(g),self.vue(self.image)):raise ValueError('instance_initiale_differente')
        return copy.deepcopy(self.initiale)
    def signature_observation(self):
        return {'methode':'scene_partagee_contextuelle','source':self.vue_source.signature_observation(),
                'preuve':self.preuve}


def composer(principal,alternatif,commutations,image_initiale,mode_initial=0):
    """commutations=(avant,action,apres,mode_avant), données réelles exclusivement."""
    try:
        if mode_initial not in (0,1):raise ValueError('mode_initial_inconnu')
        paires=[(a,b) if mode==0 else (b,a) for a,_,b,mode in commutations]
        mapping,preuve=apprendre(principal,alternatif,paires)
        if mapping is None:raise ValueError('identites_non_admises:'+str(preuve))
        inverse=dict((b,a) for a,b in mapping)
        noms_alt={_tag(b):_tag(a) for a,b in mapping}
        sources=[principal,alternatif];ecritures={};commandes={};calques={};couches={}
        for avant,action,apres,mode in commutations:
            if mode not in (0,1):raise ValueError('mode_observe_inconnu')
            src,ds=reaffecter_observation(sources[mode],avant)
            dst,dd=reaffecter_observation(sources[1-mode],apres)
            if src is None or dst is None:raise ValueError('commutation_non_reaffectable')
            depart={r:(m,xy) for r,m,xy in _roles(src)}
            arrivee={r:(m,xy) for r,m,xy in _roles(dst)}
            changements=[]
            for rp,ra in mapping:
                r0,r1=(rp,ra) if mode==0 else (ra,rp)
                m,xy=depart[r0];n,xy1=arrivee[r1]
                if xy!=xy1 or m.shape!=n.shape:raise ValueError('commutation_deplace_objet')
                modifications=[(int(y),int(x),int(n[y,x])) for y,x in np.argwhere(m!=n)]
                if modifications:changements.append((_tag(rp),modifications))
            code=canon(action)
            if len(code)!=1:raise ValueError('selecteur_non_atomique')
            if mode in commandes and (commandes[mode]!=code or ecritures[mode]!=changements):
                raise ValueError('commutations_contradictoires')
            commandes[mode]=code;ecritures[mode]=changements
            for n,c in [(mode,src),(1-mode,dst)]:
                scene=c.perception.scene(c.grilles[0])
                couches[n] = {(noms_alt.get(t,t) if n==1 else t):s['couche']
                    for s in scene.sprites for t in s['tags'] if t.startswith(('mobile_','statique_'))}
                extra=[s for s in scene.sprites if not any(t.startswith(('mobile_','statique_')) for t in s['tags'])]
                if n in calques:
                    if len(extra)!=len(calques[n]):raise ValueError('calques_contradictoires')
                    for a,b in zip(extra,calques[n]):
                        if a['x']!=b['x'] or a['y']!=b['y'] or not np.array_equal(a['pixels'],b['pixels']):raise ValueError('ancrage_calques_variable')
                calques[n]=copy.deepcopy(extra)
        if set(commandes)!={0,1}:raise ValueError('retour_non_observe')
        instance,di=reaffecter_observation(sources[mode_initial],image_initiale)
        if instance is None:raise ValueError('instance_non_admise:'+str(di))
        scene=instance.perception.scene(image_initiale)
        scene.sprites=[s for s in scene.sprites if any(t.startswith(('mobile_','statique_')) for t in s['tags'])]
        if mode_initial==1:
            for s in scene.sprites:s['tags']=[noms_alt.get(t,t) for t in s['tags']]
        for mode,ss in calques.items():
            for i,s in enumerate(ss):
                s=copy.deepcopy(s);s['tags']=[f'calque_mode_{mode}_{i}'];s['visible']=mode==mode_initial
                scene.sprites.append(s)
        programme={'mode':'lois','etat':{'contexte_actif':mode_initial},'regles':[]}
        for mode,source in enumerate(sources):
            noms={k:f'contexte_{mode}_{k}' for k in source.programme.get('etat',{})}
            if mode==1:noms.update(noms_alt)
            for k,v in source.programme.get('etat',{}).items():programme['etat'][noms[k]]=copy.deepcopy(v)
            for r in source.programme['regles']:
                r=_renommer(copy.deepcopy(r),noms);r['nom']=f'contexte_{mode}_'+r['nom']
                r['quand']=['et',['=',['etat','contexte_actif'],mode],r.get('quand',True)]
                programme['regles'].append(r)
        phase=min(r.get('phase',0) for r in programme['regles'])-1
        for mode in (0,1):
            effets=[]
            for tag,modifs in ecritures[mode]:
                effets.append(['pour','$o',['objets',{'tag':tag}],
                               [['ecrire','$o',y,x,c] for y,x,c in modifs]])
            for tag,couche in couches[1-mode].items():
                effets.append(['pour','$o',['objets',{'tag':tag}],[['calque','$o',couche]]])
            for n,ss in calques.items():
                for i in range(len(ss)):effets.append(['pour','$o',['objets',{'tag':f'calque_mode_{n}_{i}'}],[['montrer','$o',n==1-mode]]])
            effets.append(['poser','contexte_actif',1-mode])
            programme['regles'].append({'nom':f'commutation_observee_{mode}','phase':phase,
                'quand':['et',['=',['etat','contexte_actif'],mode],['=',['action'],commandes[mode][0]]], 'alors':effets})
        preuve.update(commutation_dynamique_apprise=True,ecritures_relatives=ecritures,couches_par_mode=couches,
                       commandes={str(k):v for k,v in commandes.items()},composition_provisoire=True)
        vue=SceneContextuelle(instance.perception,scene,image_initiale,preuve)
        actions=sorted(set(principal.actions+alternatif.actions+list(commandes.values())))
        c=Chaine(vue,programme,[np.asarray(image_initiale).tolist()],[],actions)
        controle,state=c.rejouer()
        if state is None or not np.array_equal(vue.rendu(state[1]),vue.vue(image_initiale)):
            raise ValueError('rendu_initial_non_exact')
        return c,{'admis':True,'preuve':preuve,'controle':controle,'but_principal_conserve':True,
                  'but_alternatif_ajoute':False,'mouvements_appris':False,'fusion_provisoire':True}
    except (ValueError,KeyError,TypeError,IndexError) as exc:
        return None,{'admis':False,'refus':str(exc)}
