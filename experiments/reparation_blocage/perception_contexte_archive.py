"""Induction locale avec masque acquis avant le contexte ; aucune loi spécifique."""
import hashlib,json
from itertools import pairwise
import numpy as np
from chrysalide.arc3.masque import Masque
from objets_variables import ObjetsVariables
from chaine_coherente import Chaine
from chaine_agent_integree import lots


def proposer(passe, images, actions, films=None):
    """Le passé s'arrête à l'image initiale ; aucune transition future pour le masque."""
    diag={'admis':False,'provisoire':True,'but_appris':False,
          'masque_source':'Masque sur passé antérieur au préfixe local'}
    if not passe or len(images)!=len(actions)+1 or not np.array_equal(passe[-1],images[0]):
        return None,{**diag,'refus':'frontiere_historique_non_alignee'}
    masque=Masque()
    for avant,apres in pairwise(passe):masque.observer(np.asarray(avant).tolist(),np.asarray(apres).tolist())
    hud=masque.cellules()
    diag.update(masque_cellules=[list(p) for p in sorted(hud)],
                transitions_masque=len(passe)-1,
                masque_passe_sha256=hashlib.sha256(json.dumps([np.asarray(g).tolist() for g in passe]).encode()).hexdigest())
    if not hud:return None,{**diag,'refus':'aucun_masque_anterieur'}
    # La valeur de remplissage sert seulement au Pisteur ; vue conserve le masque explicite.
    from collections import Counter
    fond=Counter(np.asarray(images[0]).ravel().tolist()).most_common(1)[0][0]
    propres=[np.asarray(g).copy() for g in images]
    for g in propres:
        for y,x in hud:g[y,x]=fond
    try:
        v=ObjetsVariables(propres,actions,contact=True)
        if not v.hud <= hud:return None,{**diag,'refus':'masque_local_nouveau_refuse'}
        v.hud=hud
        v.preuve_masque_herite={k:diag[k] for k in ('transitions_masque','masque_passe_sha256','masque_cellules')}
        c=Chaine(v,v.programme(),[np.asarray(g).tolist() for g in images],lots(actions),[],films=films)
        controle,state=c.rejouer()
    except (ValueError,TypeError,KeyError) as exc:
        return None,{**diag,'refus':repr(exc)}
    diag.update(controle=controle,mouvements=v.mouvements)
    if state is None:return None,{**diag,'refus':'rejeu_local'}
    c.activer_atms()
    return c,{**diag,'admis':True,'portee':'prefixe_local_observe','masque_provisoire':True}
