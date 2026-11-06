"""Prior de couverture hérité, étendu aux supports observés sans nouvelle physique."""
import copy
from chaine_coherente import Chaine,empreinte
from revision_but_roles import couverture
from ontologie_extensible import _familles


def candidats(agent,source):
    preuve=getattr(source,'preuve_revision_but',None)
    prior=preuve.get('but_refute') if preuve else None
    provenance='preuve_revision_but'
    if prior is None:
        for nom,c in getattr(agent,'modeles_but_refute',{}).items():
            regles=[r for r in c.programme['regles'] if r.get('nom')=='toutes_cibles_hypothese']
            if len(regles)==1:
                prior=regles[0];provenance='modeles_but_refute/'+nom;break
    if prior is None or source.refute:return [],{'refus':'prior_compatible_absent'}
    if prior.get('alors')!=[['niveau_suivant']]:return [],{'refus':'prior_terminal_non_supporte'}
    from transfert_roles import RolesReaffectes
    if type(source.perception) is not RolesReaffectes:return [],{'refus':'perception_non_supportee'}
    hypotheses=couverture(source.perception)
    passive=getattr(source,'preuve_classe_glissable',{}).get('classe')
    f=_familles()
    objets=[{'roles':['controle']} for _ in source.perception.pieces]
    if passive is not None:objets.append({'roles':['poussable'],'classe':passive})
    objets += [{'roles':['cible']} for _ in source.perception.cibles]
    signaux=f.signaux_depuis_objets(objets,['UP','DOWN','LEFT','RIGHT'],glissade=passive is not None)
    classification=f.reconnaitre(signaux)
    diagnostic={'prior_source':provenance,'prior_sha256':empreinte(prior),
        'precedents_disponibles':len(getattr(agent,'precedents',[])),
        'classification_hypothetique':classification,'but_herite_localement_refute':True,
        'but_confirme':False,'essais':[]}
    propositions=[]
    for h in hypotheses:
        autres=[q['classe_cible_candidate'] for q in hypotheses if q['forme']==h['forme'] and q['classe_cible_candidate']!=h['classe_cible_candidate']]
        for mobile in autres:
            contraintes=[]
            for x,y,w,ht in h['centres']:
                contraintes.append(['existe','$o',['objets',{'couleur':mobile}],['et',
                    ['=',['x','$o'],x],['=',['y','$o'],y],
                    ['=',['largeur','$o'],w],['=',['hauteur','$o'],ht]]])
            regle=copy.deepcopy(prior)
            regle['nom']='couverture_heritee_elargie_hypothese'
            regle['quand']=['et',copy.deepcopy(prior['quand']),*contraintes]
            p=copy.deepcopy(source.programme);p['regles'].append(regle)
            v=copy.deepcopy(source.perception);v.programme_transfere=copy.deepcopy(p)
            c=Chaine(v,p,source.grilles,source.lots,source.actions,coups_deja_joues=source.coups,reserve=source.limite,
                films=[e['images'] if e else None for e in source.films.entrees])
            controle,etat=c.rejouer()
            desc={'forme_but':'couverture_heritee_elargie','classe_mobile_candidate':mobile,
                'classe_cible_candidate':h['classe_cible_candidate'],'centres':h['centres'],
                'role_mobile_observe':mobile==passive,'but_confirme':False,
                'prior_source':provenance,'prior_sha256':empreinte(prior)}
            diagnostic['essais'].append({**desc,'controle':controle,'admis_sur_traces':etat is not None})
            if etat is None:continue
            c.activer_atms();c.preuve_but_elargi=desc
            c.preuve_revision_but=copy.deepcopy(preuve)
            c.but_hypothese_non_confirmee=True
            propositions.append((desc,c))
    # La classe oriente le rang, jamais une nouvelle loi ou une certification du but.
    pousse=any(n=='pousse_cibles' and score>0 for n,score in classification)
    propositions.sort(key=lambda item:(not (pousse and item[0]['role_mobile_observe']),not item[0]['role_mobile_observe']))
    return propositions,diagnostic


def signature_semantique(c):
    """Condition, dynamique et perception ; les étiquettes de réparation ne comptent pas."""
    def simple(x):
        if hasattr(x,'tolist'):return x.tolist()
        if isinstance(x,dict):return {k:simple(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [simple(v) for v in x]
        if isinstance(x,set):return sorted(simple(v) for v in x)
        return x
    buts=[r for r in c.programme['regles'] if r.get('nom')=='couverture_heritee_elargie_hypothese']
    if len(buts)!=1:return None
    dynamique=copy.deepcopy(c.programme)
    dynamique['regles']=[r for r in dynamique['regles'] if r not in buts]
    vue=c.perception
    return empreinte(simple({'condition':buts[0]['quand'],'dynamique':dynamique,
        'perception':vue.signature_observation(),
        'statiques':getattr(vue,'statiques',None),'pieces':getattr(vue,'pieces',None)}))


def dedupliquer(agent):
    vus={};doublons=[]
    for nom,c in list(agent.chaines.items()):
        sig=signature_semantique(c)
        if sig is None:continue
        if sig in vus:
            doublons.append({'retire':nom,'conserve':vus[sig],'signature':sig})
            del agent.chaines[nom]
        else:vus[sig]=nom
    if doublons:agent.journal.append({'type':'buts_roles_doublons','doublons':doublons})
    return set(vus)


def admettre(agent,secondes=1):
    """Raccord au portefeuille courant ; les réfutations de buts restent en mémoire."""
    import time
    debut=time.monotonic();ajouts={};essais=[]
    existants=dedupliquer(agent)
    refuses={empreinte(r['quand']) for c in getattr(agent,'modeles_but_refute',{}).values()
             for r in c.programme['regles'] if r.get('nom')=='couverture_heritee_elargie_hypothese'}
    for nom,source in list(agent.chaines.items()):
        if time.monotonic()-debut>=secondes:break
        if not getattr(source,'but_inconnu',False) or not hasattr(source,'preuve_classe_glissable'):continue
        signature=empreinte({'programme':source.programme,'perception':source.perception.signature_observation()})
        cache=getattr(agent,'buts_roles_deja_proposes',set())
        if signature in cache:continue
        cs,diag=candidats(agent,source)
        agent.buts_roles_deja_proposes=set(cache)|{signature}
        for desc,c in cs:
            cond=empreinte(c.programme['regles'][-1]['quand'])
            if cond in refuses:continue
            sem=signature_semantique(c)
            if sem in existants:continue
            label='but_roles_herite/'+cond[:16]
            if label in agent.chaines or label in ajouts:label+='/' + sem[:16]
            existants.add(sem)
            c.preuve_but_elargi['source_dynamique']=nom
            ajouts[label]=c
        essais.append({'source':nom,**diag})
    if essais:agent.journal.append({'type':'buts_roles_herites','coup':len(agent.actions),'diagnostics':essais,'admis':list(ajouts),'but_confirme':False})
    agent.chaines.update(ajouts)
    return bool(ajouts)


def reaffecter_couverture(source,vue,programme):
    """Transférer la famille de but ; seuls les paramètres de la nouvelle scène changent."""
    p=copy.deepcopy(programme)
    regles=[r for r in p['regles'] if r.get('nom')=='couverture_heritee_elargie_hypothese']
    if not regles:return p,None
    preuve=getattr(source,'preuve_but_elargi',None)
    if len(regles)!=1 or not preuve:raise ValueError('Provenance du but de couverture absente ou ambiguë')
    r=regles[0]
    if r['quand'][0]!='et' or r.get('alors')!=[['niveau_suivant']]:
        raise ValueError('But de couverture hors contrat')
    formes={tuple(x[2:]) for x in preuve['centres']}
    groupes=[h for h in couverture(vue)
             if h['classe_cible_candidate']==preuve['classe_cible_candidate']
             and {(w,ht) for x,y,w,ht in h['centres']}==formes]
    if len(groupes)!=1:raise ValueError('Réaffectation des cibles de couverture absente ou ambiguë')
    centres=groupes[0]['centres']
    r['quand']=['et',r['quand'][1],*[
        ['existe','$o',['objets',{'couleur':preuve['classe_mobile_candidate']}],['et',
         ['=',['x','$o'],x],['=',['y','$o'],y],['=',['largeur','$o'],w],['=',['hauteur','$o'],h]]]
        for x,y,w,h in centres]]
    return p,{**copy.deepcopy(preuve),'centres':centres,'but_confirme':False,
        'source_centres':copy.deepcopy(preuve['centres']),'reaffectation_instance':True}
