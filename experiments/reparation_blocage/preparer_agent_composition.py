"""Installe une composition admise sans effacer les mémoires des contextes sources."""
import argparse,copy,json,hashlib
from pathlib import Path
import cloudpickle,numpy as np
from avancer_agent_relais import charger_agent,sauver_agent


def _preuve_composition(c):
    """Contrats explicitement supportés ; aucun attribut libre ne suffit."""
    from composition_contextes_objets import SceneContextuelle
    from revision_calques_contextes import ProjectionCiblesComposees
    from perception_guidee import PerceptionGuidee
    vue=c.perception
    if type(vue) is PerceptionGuidee:
        if type(vue.base) is not ProjectionCiblesComposees or not vue.points:
            raise ValueError('Wrapper composition non reconnu')
        revision=getattr(c,'preuve_calque_contextuel',{})
        if (revision.get('nom') not in ('detail_local','detail_periodique')
                or not isinstance(revision.get('contre_exemple'),int)
                or revision['contre_exemple']<1
                or revision.get('provisoire') is not True
                or revision.get('causalite_prouvee') is not False):
            raise ValueError('Revision calque non documentee')
        suffixe=revision.get('suffixe_tenu_a_part',[])
        if (len(suffixe)!=2 or suffixe[0]!=revision['contre_exemple']+1
                or suffixe[1]<suffixe[0] or suffixe[1]>c.coups):
            raise ValueError('Preuve suffixe calque invalide')
        vue=vue.base.vue_composee
    if type(vue) is not SceneContextuelle:
        raise ValueError('Wrapper composition non reconnu')
    preuve=vue.preuve
    if (preuve.get('commutation_dynamique_apprise') is not True
            or preuve.get('composition_provisoire') is not True
            or not preuve.get('preuves')
            or set(preuve.get('commandes',{}))!={'0','1'}
            or set(preuve.get('ecritures_relatives',{}))!={0,1}):
        raise ValueError('Composition non documentee')
    # Les commandes documentées doivent être celles du programme effectivement rejoué.
    for mode in (0,1):
        rs=[r for r in c.programme['regles'] if r.get('nom')==f'commutation_observee_{mode}']
        commande=preuve['commandes'][str(mode)]
        if len(rs)!=1 or len(commande)!=1 or rs[0].get('quand')!=[
                'et',['=',['etat','contexte_actif'],mode],['=',['action'],commande[0]]]:
            raise ValueError('Preuve commutation non synchronisee')
    return preuve


def installer_composition(a,c):
    """Admet une chaîne, liste ou mapping : validation intégrale avant mutation."""
    unique=not isinstance(c,(dict,list,tuple))
    if unique:entrees={'contextes_observes':c}
    elif isinstance(c,dict):entrees=dict(c)
    else:entrees={f'contextes_observes/{i}':v for i,v in enumerate(c)}
    if not entrees or any(not isinstance(n,str) or not n for n in entrees):
        raise ValueError('Portefeuille vide ou noms invalides')
    controles={};installes={}
    for nom,original in entrees.items():
        candidat=copy.deepcopy(original)
        _preuve_composition(candidat)
        if candidat.refute:raise ValueError('Composition refutee')
        candidat._verifie=None
        check,state=candidat.rejouer()
        if (state is None or not all(check.get(k) for k in
                ('catalogue_shacl','traduction_python','rejeu','compilation_fidele'))
                or not np.array_equal(candidat.grilles[-1],a.images[-1])):
            raise ValueError('Composition non alignee')
        if not np.array_equal(candidat.perception.rendu(state[1]),candidat.perception.vue(a.images[-1])):
            raise ValueError('Etat compose different')
        if candidat.plan and not candidat.verifier_plan(candidat.plan['actions'])[0]:
            raise ValueError('Plan compose invalide')
        candidat.coups=len(a.actions);candidat.limite=a.limite
        installes[nom]=candidat;controles[nom]=check
    memoires=copy.deepcopy({'memoire_jeu':getattr(a,'memoire_jeu',None),
        'modeles_suspendus':getattr(a,'modeles_contextes_suspendus',{}),'chaines':a.chaines,
        'modele_gagnant':getattr(a,'modele_gagnant',None),
        'modeles_avant_victoire':getattr(a,'modeles_avant_victoire',{})})
    archives=[*getattr(a,'memoires_avant_composition',[]),memoires]
    # Aucune affectation de l'agent avant validation et copie de tout le portefeuille.
    a.memoires_avant_composition=archives
    a.memoire_jeu=None;a.modeles_contextes_suspendus={};a.diagnostic_transfert=None
    a.chaines=installes;a.reconstruction=False;a.attente=None
    a.journal.append({'type':'composition_contextes_installee','coup':len(a.actions),
        'controles':controles,'candidats':list(installes),'memoires_sources_conservees':True,
        'regles_reapprises':0,'hypotheses_concurrentes_conservees':True})
    return next(iter(controles.values())) if unique else {'candidats':len(installes),'controles':controles}


def preparer(agent_path,candidat_path,sortie):
    a=charger_agent(agent_path);data=candidat_path.read_bytes()
    meta=json.loads(candidat_path.with_suffix('.json').read_text())
    if hashlib.sha256(data).hexdigest()!=meta.get('sha256',meta.get('candidat_sha256')):
        raise ValueError('Candidat altere')
    c=cloudpickle.loads(data)
    check=installer_composition(a,c)
    sortie.mkdir(parents=True,exist_ok=False);sauver_agent(a,sortie/'agent.pkl')
    (sortie/'preuve.json').write_text(json.dumps({'actions_globales':len(a.actions),
        'controle':check,'sdk_actions':0,'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [agent_path,candidat_path]}},indent=2))
    return a

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['agent','candidat','sortie']:p.add_argument('--'+n,type=Path,required=True)
    v=p.parse_args();preparer(v.agent,v.candidat,v.sortie)
