"""Orchestration opt-in de capacités existantes sur la banque d'observations."""
import time
import numpy as np
from chaine_coherente import empreinte
from memoire_observations import episode_observe
from diagnostic_contexte_transfert import compatible
from segments_contextuels_observes import proposer_segments
from revision_calques_contextes import proposer_avec_revision
from preparer_agent_composition import installer_composition
from correspondance_contextes_objets import _base


def enregistrer_epuisement(agent,nom,chaine,resultat):
    if not getattr(agent,'composition_contextuelle_auto',False):return
    if resultat.get('infos',{}).get('refus')!='espace épuisé':return
    preuves=dict(getattr(agent,'epuisements_contextuels',{}))
    preuves[nom]={'signature':chaine.signature(),'image':empreinte(np.asarray(agent.images[-1]).tolist()),
                  'infos':resultat['infos'],'but_refute':False}
    agent.epuisements_contextuels=preuves


def _sources(agent):
    sources={};raisons=[]
    for nom,c in agent.chaines.items():
        preuve=getattr(agent,'epuisements_contextuels',{}).get(nom,{})
        if (not c.refute and preuve.get('signature')==c.signature()
                and preuve.get('image')==empreinte(np.asarray(agent.images[-1]).tolist())):
            sources[nom]=c;raisons.append('espace_epuise_signe')
    stock=getattr(agent,'modeles_contextes_suspendus',{})
    memoire=getattr(agent,'memoire_jeu',None)
    if not agent.chaines and stock and memoire is not None and compatible(memoire,agent.images[-1]):
        for nom,e in stock.items():
            c=e['chaine'];_,state=c.rejouer()
            if (not c.refute and state is not None
                    and not np.array_equal(c.perception.rendu(state[1]),c.perception.vue(agent.images[-1]))):
                sources[nom]=c;raisons.append('contexte_retour_non_reactivable')
    compatibles={}
    for n,c in sources.items():
        try:_base(c.perception)
        except ValueError:continue
        compatibles[n]=c
    return compatibles,sorted(set(raisons))


def orchestrer(agent,secondes):
    debut=time.process_time();budget=max(0.,float(secondes))
    rapport={'type':'orchestration_contextes','installe':False,'SDK':False,'budget_cpu_s':budget,
             'budget_cooperatif':True,'but_refute':False}
    if not getattr(agent,'composition_contextuelle_auto',False):return {**rapport,'refus':'option_inactive'}
    episodes=getattr(agent,'observations_episodes',())
    if not episodes:return {**rapport,'refus':'banque_absente'}
    sources,raisons=_sources(agent)
    if not sources:return {**rapport,'refus':'aucun_declencheur_signe'}
    # Signature du contenu effectif, pas uniquement des déclarations de provenance.
    if budget<=0:return {**rapport,'refus':'budget_avant_selection'}
    try:
        courant=episode_observe(agent.images,agent.actions,agent.issues,getattr(agent,'films',None))
        corpus=[(e.get('provenance',{}),episode_observe(*(e[k] for k in ('grilles','actions','issues')),films=e.get('films'))['provenance']['sha256_contenu']) for e in episodes]
    except (ValueError,KeyError,TypeError) as exc:
        retour={**rapport,'refus':'corpus_non_aligne','detail':str(exc)}
        agent.journal.append(retour);return retour
    cle=empreinte({'sources':{n:c.signature() for n,c in sources.items()},'corpus':corpus,
                   'courant':courant['provenance']['sha256_contenu']})
    cache=dict(getattr(agent,'essais_composition_contextuelle',{}))
    if cle in cache and (not str(cache[cle].get('refus','')).startswith('budget') or budget<=cache[cle].get('budget_cpu_s',budget)):
        retour={**rapport,'refus':'essai_identique_deja_effectue','signature':cle,'precedent':cache[cle]}
        agent.journal.append(retour);return retour
    rapport.update(signature=cle,declencheurs=raisons,essais=[])
    portefeuille={}
    def restant():return max(0.,budget-(time.process_time()-debut))
    for nom,principal in sources.items():
        if restant()<=0:rapport['refus']='budget';break
        alternatifs,selection=proposer_segments(principal,episodes,secondes=restant())
        if selection.get('budget_epuise') or str(selection.get('refus','')).startswith('budget'):
            rapport['refus']='budget_selection'
        for i,alt in enumerate(alternatifs):
            if restant()<=0:rapport['refus']='budget';break
            candidats,composition=proposer_avec_revision(principal,alt,agent.images,agent.actions,
                agent.issues,agent.films,secondes=restant())
            if composition.get('budget_epuise') or str(composition.get('refus','')).startswith('budget'):
                rapport['refus']='budget_composition'
            rapport['essais'].append({'source':nom,'segment':alt.preuve_segment_contextuel,
                'composition':composition})
            for j,c in enumerate(candidats):portefeuille[f'contextes_observes/{len(portefeuille)}']=c
        if not alternatifs:rapport['essais'].append({'source':nom,'selection':selection})
    if portefeuille and restant()>0:
        rapport['installation']=installer_composition(agent,portefeuille)
        rapport['installe']=True;rapport['candidats']=list(portefeuille)
    elif portefeuille:rapport['refus']='budget_avant_installation'
    elif 'refus' not in rapport:rapport['refus']='aucune_composition_admise'
    rapport['cpu']=time.process_time()-debut
    cache[cle]={'installe':rapport['installe'],'refus':rapport.get('refus'),'cpu':rapport['cpu'],'budget_cpu_s':budget}
    agent.essais_composition_contextuelle=cache
    agent.journal.append(rapport)
    return rapport
