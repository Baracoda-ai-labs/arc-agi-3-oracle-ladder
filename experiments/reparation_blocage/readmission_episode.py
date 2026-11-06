"""Réadmettre une physique archivée après RESET observé, sans rejouer RESET."""
import copy
import numpy as np
from chaine_coherente import Chaine

_CONTROLES=('catalogue_shacl','traduction_python','rejeu','compilation_fidele')


def proposer(source, image, actions, reserve):
    if source.refute or source.contre_exemples:
        raise ValueError('Source réfutée : aucune réactivation')
    original=copy.deepcopy(source)
    controle,courant=original.rejouer()
    if courant is None or not all(controle.get(k) for k in _CONTROLES):
        raise ValueError('Préfixe source non admissible')
    controle_source=copy.deepcopy(controle)
    if np.array_equal(np.asarray(image), np.asarray(original.grilles[0])):
        # Même observation native : scène initiale du programme, jamais son état final.
        c=Chaine(original.perception, original.programme, [np.asarray(image).tolist()],
                 [], actions, reserve=reserve, films=[], origine='retry_instance_initiale_observee')
        mode='image_initiale_native_identique'
    else:
        from selection_observee import SelectionObservee
        from chrysalide.arc3.moteur import MoteurC
        if isinstance(original.perception, SelectionObservee):
            from transfert_roles import reaffecter
        elif isinstance(original.perception, MoteurC):
            from transfert_modele_c import reaffecter
        else:
            raise ValueError('Nouvelle disposition sans adaptateur étayé')
        c,_=reaffecter(original,image,actions,reserve=reserve)
        mode='adaptateur_instance_existant'
    controle,courant=c.rejouer()
    if courant is None or not all(controle.get(k) for k in _CONTROLES):
        raise ValueError('Instance RESET non admissible')
    if not np.array_equal(c.perception.rendu(courant[1]),c.perception.vue(image)):
        raise ValueError('Rendu RESET non exact dans la perception héritée')
    for nom,valeur in vars(original).items():
        if nom.startswith('preuve_') and not hasattr(c,nom):
            setattr(c,nom,copy.deepcopy(valeur))
    c.plan=None
    c.but_hypothese_non_confirmee=True
    if getattr(original,'but_inconnu',False):c.but_inconnu=True
    c.preuve_readmission_episode={'source':original.signature(),'mode':mode,
        'controle_source':controle_source,
        'controle_instance':controle,'but_confirme':False,'plan_adopte':False,
        'dynamique_nouvel_episode_validee':False,
        'limite':'Rendu initial exact ; conséquences futures et but restent hypothèses'}
    c.activer_atms()
    return c


def installer(agent, offre):
    if agent.actions or getattr(agent,'attente',None) is not None:
        raise ValueError('Réadmission réservée au début observé de tentative')
    from chaine_agent_integree import NOMS
    actions=[(NOMS[k],) for k in offre if k in NOMS]
    essais=[]
    for nom,source in getattr(agent,'modeles_episode_precedent',{}).items():
        try:
            c=proposer(source,agent.images[0],actions,agent.limite)
        except (ValueError,TypeError,KeyError,IndexError) as exc:
            essais.append({'source':nom,'admis':False,'raison':str(exc)})
            continue
        agent.chaines['episode_precedent/'+nom]=c
        essais.append({'source':nom,'admis':True,**c.preuve_readmission_episode})
    if any(e['admis'] for e in essais):agent.reconstruction=False
    agent.journal.append({'type':'readmission_episode_observe','essais':essais,
        'but_confirme':False,'reset_dans_historique_modele':False})
    return essais


def conserver_physique_terminale(chaines, resultats):
    """Une défaite réelle réfute la sûreté, pas un rendu effectivement exact.

    Ne conserve que les modèles dont la SEULE contradiction est le terminal
    sans victoire ; tout le préfixe est rejoué avant usage, jamais tronqué.
    """
    stock={}
    for r in resultats:
        if (r.get('statut')!='fin_sans_victoire' or not r.get('image_exacte')
                or r.get('issue_predite') is not None):continue
        nom=r['nom'];source=chaines[nom]
        if not source.contre_exemples or any(
                p.get('statut')!='fin_sans_victoire' or p.get('differences')!=[]
                or p.get('issue_predite') is not None for p in source.contre_exemples):continue
        c=Chaine(source.perception,source.programme,source.grilles,source.lots,
                 source.actions,coups_deja_joues=source.coups,reserve=source.limite,
                 films=[e['images'] if e else None for e in source.films.entrees])
        for attr,valeur in vars(source).items():
            if attr.startswith('preuve_') or attr=='but_inconnu':
                setattr(c,attr,copy.deepcopy(valeur))
        c.preuve_defaite_physique_exacte={'source':source.signature(),
            'terminal':copy.deepcopy(source.contre_exemples),
            'surete_refutee':True,'but_confirme':False,'rejeu_source_requis':True}
        c.but_hypothese_non_confirmee=True
        stock[nom]=c
    return stock
