"""Préparation pure : accès observé puis contraste de déplacements, aucun SDK."""
import copy,hashlib
import numpy as np
from diagnostic_contexte_transfert import marqueurs
from transfert_objets_sans_but import reaffecter
from chaine_agent_integree import canon
from chrysalide.arc3.langage import Programme


def _hotes(image):
    return {c:tuple(sorted(h)) for c,h in marqueurs(image).items()}


def _etat_ayant_image(chaine,image):
    """Retrouve un état effectivement validé, sans reconstruire son état latent."""
    pc=Programme(chaine.programme);sc=chaine.perception.scene(chaine.grilles[0])
    attendu=chaine.perception.vue(image)
    if np.array_equal(chaine.perception.rendu(sc),attendu):return pc,sc
    for lot in chaine.lots:
        for action in lot['actions']:pc.step(sc,chaine.action_tuple(action))
        if np.array_equal(chaine.perception.rendu(sc),attendu):return pc,sc
    return None


def proposer_experience(principal,alternatif,images,actions,offre,archives=()):
    """archives = séquences (images, actions) observées ; jamais d'effet synthétique."""
    diag={'SDK':False,'but_suppose':False,'objectif':'discriminer_controle_contextuel',
          'risque':'inconnu','nouvelle_loi':False}
    def refus(raison):return {**diag,'statut':'experience_non_preparee','actions':[],'refus':raison}
    if len(images)!=len(actions)+1 or not images:return refus('historique_non_aligne')
    if principal.refute or alternatif.refute:return refus('modele_refute')
    hp,ha=_hotes(principal.grilles[0]),_hotes(alternatif.grilles[0])
    cles=sorted(c for c in hp.keys() & ha.keys() if hp[c]!=ha[c])
    if not cles:return refus('contextes_non_distingues')
    sig=lambda im:tuple((c,_hotes(im).get(c,())) for c in cles)
    sp,sa=sig(principal.grilles[0]),sig(alternatif.grilles[0])
    actuel=np.asarray(images[-1]);scourant=sig(actuel)
    sources=[(images,actions),*archives]
    if any(len(gs)!=len(acts)+1 for gs,acts in sources):return refus('archive_non_alignee')
    def deja(code,vue):
        now=vue.vue(actuel)
        return any(a==code and np.array_equal(vue.vue(g),now)
                   for gs,acts in sources for g,a in zip(gs,acts))
    if scourant==sp:
        passages=[]
        for gs,acts in sources:
            for i,code in enumerate(acts):
                if code in offre and sig(gs[i])==sp and sig(gs[i+1])==sa and not deja(code,principal.perception):
                    passages.append((code,i+1))
        if not passages:return refus('aucun_acces_observe_nouveau')
        code,coup=passages[0]
        return {**diag,'statut':'acces_contexte_observe','actions':[code],
                'preuve_passage_coup':coup,'prediction_image':None,
                'suite':'attendre_image_reelle_puis_reaffecter','contexte_cible':sa}
    if scourant!=sa:return refus('contexte_non_reconnu')
    candidat,admission=reaffecter(alternatif,actuel)
    if candidat is None:return refus('reaffectation_refusee:'+admission['refus'])
    # Le contraste principal vient d'un vrai passage observé à géométrie correspondante.
    reference=None
    for gs,acts in sources:
        for i,_ in enumerate(acts):
            if sig(gs[i])==sp and sig(gs[i+1])==sa and np.array_equal(candidat.perception.vue(gs[i+1]),candidat.perception.vue(actuel)):
                reference=_etat_ayant_image(principal,gs[i])
                if reference is not None:break
        if reference is not None:break
    if reference is None:return refus('etat_principal_correspondant_non_valide')
    _,courant=candidat.rejouer()
    experiences=[]
    for code in offre:
        if not isinstance(code,int) or deja(code,candidat.perception):continue
        if not any(d!=(0,0) and a==code for ms in candidat.perception.mouvements.values() for a,d in ms.items()):continue
        pc,sc=copy.deepcopy(courant);pi,si=copy.deepcopy(reference)
        avant_alt=candidat.perception.rendu(sc);avant_principal=principal.perception.rendu(si)
        pc.step(sc,canon(code));pi.step(si,canon(code))
        apres_alt=candidat.perception.rendu(sc);apres_principal=principal.perception.rendu(si)
        da=apres_alt!=avant_alt;dp=apres_principal!=avant_principal
        if not da.any() or sc.issue=='defaite' or np.array_equal(da,dp):continue
        experiences.append({'action':code,'pixels_modifies_alternatif':int(da.sum()),
          'pixels_contraste_effets':int(np.count_nonzero(da!=dp)),
          'prediction_image':apres_alt.tolist(),'issue_predite':sc.issue,
          'contraste_principal_image':apres_principal.tolist(),
          'contraste_principal_portee':'autre_contexte_observe_pas_prediction_du_contexte_actuel'})
    if not experiences:return refus('aucun_deplacement_discriminant_inedit')
    choix=max(experiences,key=lambda e:e['pixels_contraste_effets'])
    return {**diag,'statut':'experience_contexte_alternatif','actions':[choix['action']],
            'admission':admission,'choix':choix,'hypothese_provisoire':True,
            'image_source_sha256':hashlib.sha256(actuel.tobytes()).hexdigest()}
