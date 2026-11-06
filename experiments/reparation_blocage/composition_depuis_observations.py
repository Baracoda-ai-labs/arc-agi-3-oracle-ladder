"""Orchestre les briques contextuelles sur observations fournies, sans politique SDK."""
import time
import numpy as np
from correspondance_contextes_objets import reaffecter_observation,apprendre
from composition_contextes_objets import composer
from chaine_coherente import Chaine
from chaine_agent_integree import lots


def proposer_composition(principal,alternatif,images,actions,issues=None,films=None,secondes=5.):
    debut=time.process_time()
    diag={'admis':False,'SDK':False,'commutations':[], 'refus_locaux':[],
          'apprentissage_futur_validation':False,'but_alternatif_ajoute':False}
    def refuse(raison,**infos):return None,{**diag,'refus':raison,'cpu':time.process_time()-debut,**infos}
    if len(images)!=len(actions)+1 or not actions:return refuse('historique_non_aligne')
    if films is not None and len(films)!=len(actions):return refuse('films_non_alignes')
    if issues is not None and (len(issues)!=len(actions) or any(i!='continue' for i in issues)):
        return refuse('frontiere_issue_non_continue')
    sources=[principal,alternatif];cache={};trouvees={};fin=None
    def mode(index):
        if index not in cache:
            possibles=[];refus=[]
            for no,src in enumerate(sources):
                c,d=reaffecter_observation(src,images[index])
                if c is not None:possibles.append(no)
                else:refus.append({'mode':no,'refus':d['refus']})
            cache[index]=(possibles,refus)
        return cache[index]
    for k in range(len(actions)):
        if time.process_time()-debut>=secondes:return refuse('budget_selection')
        avant,ra=mode(k);apres,rb=mode(k+1)
        if len(avant)>1 or len(apres)>1:return refuse('mode_ambigu',image=k if len(avant)>1 else k+1)
        if not avant or not apres:
            diag['refus_locaux'].append({'transition':k+1,'avant':ra if not avant else [],'apres':rb if not apres else []})
            continue
        m,n=avant[0],apres[0]
        if m==n or m in trouvees:continue
        paire=(images[k],images[k+1]) if m==0 else (images[k+1],images[k])
        mapping,preuve=apprendre(principal,alternatif,[paire])
        if mapping is None:
            diag['refus_locaux'].append({'transition':k+1,'commutation':preuve});continue
        trouvees[m]=(images[k],actions[k],images[k+1],m)
        diag['commutations'].append({'transition':k+1,'mode_avant':m,'mode_apres':n,'preuve':preuve})
        if len(trouvees)==2:
            fin=k+1;mode_initial=n;break
    if fin is None:return refuse('deux_sens_observes_non_disponibles')
    if fin==len(actions):return refuse('aucun_suffixe_independant')
    c,preuve=composer(principal,alternatif,list(trouvees.values()),images[fin],mode_initial)
    if c is None:return refuse('composition_refusee',composition=preuve)
    candidat=Chaine(c.perception,c.programme,[np.asarray(g).tolist() for g in images[fin:]],
        lots(actions[fin:]),c.actions,coups_deja_joues=len(actions),reserve=principal.limite,
        films=None if films is None else films[fin:])
    controle,state=candidat.rejouer()
    if state is None or not all(controle.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
        return refuse('suffixe_refute',controle=controle,fin_apprentissage=fin,
                      transition_divergence=fin+controle.get('premiere_divergence',0),
                      refus_blocant=True)
    if not np.array_equal(candidat.perception.rendu(state[1]),candidat.perception.vue(images[-1])):
        return refuse('etat_courant_non_aligne')
    candidat.activer_atms()
    diag.update(admis=True,composition=preuve,fin_apprentissage=fin,
                suffixe_validation=[fin+1,len(actions)],controle=controle,
                mode_courant=state[0].etat['contexte_actif'],cpu=time.process_time()-debut)
    candidat.preuve_composition_automatique=diag
    return candidat,diag
