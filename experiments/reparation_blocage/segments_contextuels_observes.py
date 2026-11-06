"""Sélection de contextes locaux dans une banque explicite, sans accès aux archives."""
import time
from types import SimpleNamespace
from diagnostic_contexte_transfert import marqueurs,compatible,contexte_source
from memoire_observations import episode_observe
from perception_contexte_archive import proposer
from correspondance_contextes_objets import _base


def proposer_segments(principal,episodes,secondes=2.):
    debut=time.process_time();rapport={'statut':'aucun_candidat','essais':[],
        'induction':'perception_contexte_archive.proposer','SDK':False,'but_ajoute':False}
    try:_base(principal.perception)
    except ValueError:return [],{**rapport,'refus':'representation_principale_non_applicable'}
    if principal.refute:return [],{**rapport,'refus':'principal_refute'}
    contexte=contexte_source(principal.grilles)
    if not contexte:return [],{**rapport,'refus':'aucun_marqueur_stable_principal'}
    reference=SimpleNamespace(contexte_selection=contexte)
    cles=sorted(contexte)
    def signature(image):
        vu=marqueurs(image)
        if any(len(vu.get(c,{}))!=1 for c in cles):return None
        return tuple((c,tuple(sorted(vu[c]))) for c in cles)
    candidats=[]
    for no,episode in enumerate(episodes):
        if time.process_time()-debut>=secondes:
            rapport['budget_epuise']=True;break
        try:
            # Revalidation du contrat/provenance, sans import implicite d'un autre épisode.
            valide=episode_observe(*(episode[k] for k in ('grilles','actions','issues')),films=episode.get('films'))
            sha=episode.get('provenance',{}).get('sha256_contenu')
            if sha!=valide['provenance']['sha256_contenu']:raise ValueError('Empreinte episode invalide')
            if any(i!='continue' for i in episode['issues'][:-1]):raise ValueError('Frontiere episode interne')
        except (ValueError,KeyError,TypeError) as exc:
            rapport['essais'].append({'episode':no,'refus':str(exc)});continue
        gs,acts,issues=episode['grilles'],episode['actions'],episode['issues']
        segments=[];debut_segment=None;sig_segment=None
        for i,issue in enumerate(issues):
            if issue!='continue':
                if debut_segment is not None:segments.append((debut_segment,i,sig_segment))
                debut_segment=None;break
            s0,s1=signature(gs[i]),signature(gs[i+1])
            stable=s0 is not None and s0==s1 and not compatible(reference,gs[i])
            if not stable or (debut_segment is not None and s0!=sig_segment):
                if debut_segment is not None:segments.append((debut_segment,i,sig_segment))
                debut_segment=None
            if stable and debut_segment is None:debut_segment=i;sig_segment=s0
        if debut_segment is not None:segments.append((debut_segment,len(acts),sig_segment))
        for start,end,sig in segments:
            if time.process_time()-debut>=secondes:
                rapport['budget_epuise']=True;break
            films=episode.get('films')
            c,diag=proposer(list(gs[:start+1]),list(gs[start:end+1]),list(acts[start:end]),
                           films=None if films is None else list(films[start:end]))
            preuve={'episode':no,'episode_sha256':sha,'images_induction':[start,end],
                    'transitions_induction':[start+1,end],'transitions_masque':[1,start],
                    'signature_contexte':sig,'provenance':episode['provenance'],
                    'futur_du_segment_utilise':False}
            rapport['essais'].append({**preuve,'diagnostic':diag})
            if c is not None:
                c.preuve_segment_contextuel=preuve
                candidats.append(c)
    rapport.update(statut='candidats_admis' if candidats else 'aucun_candidat',
                   candidats=len(candidats),cpu=time.process_time()-debut)
    return candidats,rapport
