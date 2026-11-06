"""Induction/export existants, sans appel au chercheur de buts ni au SDK."""
import copy
import numpy as np
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import MoteurC, _codes_c, _trajectoire_heritee
from chrysalide.arc3.logique.induction import induire
from chrysalide.arc3.logique.export_langage import exporter


def construire(historique, limite_s=10, echelle=None, trajectoire_factory=None, presence_prudente=False, prior_solide=True, dedoublonne_poussee=False, debord_visible=False, ancre_complete=False):
    h=copy.deepcopy(historique)
    h["grilles"]=[np.asarray(g).tolist() for g in h["grilles"]]
    actions=_codes_c(h['lots'])
    if actions is None or not actions:raise ValueError('Transitions atomiques requises')
    if len(h['grilles'])!=len(actions)+1:raise ValueError('Prefixe non aligne')
    if trajectoire_factory is not None:
        tr=trajectoire_factory(h['grilles'],actions)
    elif echelle is None:
        tr=_trajectoire_heritee(h['grilles'],actions,[])
    else:
        from chrysalide.arc3.logique.faits import Trajectoire
        tr=Trajectoire(h['grilles'],actions,ech=echelle)
    tr.presence_prudente=presence_prudente
    tr.ancre_complete=ancre_complete
    tr.masque_projection=bord_masque(tr.taille,tr.exclues) if ancre_complete else frozenset()
    th,infos=induire([(tr,None,None)],limite_s=limite_s,prior_solide=prior_solide)
    th.dedoublonne_poussee=dedoublonne_poussee
    th.but=None;th.hors_jeu=tr.exclues
    if debord_visible:
        from chrysalide.arc3.logique.induction import trouver_debord
        th.masque_projection=bord_masque(tr.taille,tr.exclues)
        th.debordent=trouver_debord(th,[(tr,None,None)],th.masque_projection)
    if ancre_complete:
        th.ancres_bornees=dict(getattr(tr,'ancres',{}))
        th.calques_observes={m:4 for c,f,m,ax,ay in getattr(tr,'modeles_complets',[])}
        th.masque_projection=bord_masque(tr.taille,tr.exclues)
    prog,non=exporter(th,tr.taille)
    m=MoteurC();m.tr=tr;m.th_releve=th;m._couches=th.couches()
    c=Chaine(m,prog,h['grilles'],h['lots'],[],coups_deja_joues=len(actions),films=h.get('films'))
    controle,etat=c.rejouer()
    rapport={'induction':infos,'non_exporte':non,'controle':controle,'admis':not non and etat is not None and all(controle.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')),'couverts':['etats_finaux_dans_vue_percue'],'inconnus':['but','issues','evenements_intermediaires','interactions_inedites'],'droit_action':False,'mouvements':len(th.moves),'bascules':repr(th.bascule),'motif':repr(th.motif)}
    return c,rapport


def clics_etayes(chaine):
    """Actions candidates existantes : formes déjà vues basculer, aucune cible fournie."""
    from chrysalide.arc3.moteur import _clics_offerts, _lot_c
    m=chaine.perception
    return [['clic',a['col'],a['row']] for a in (_lot_c(x,m.tr) for x in _clics_offerts(m.th_releve,m.tr))]


def bord_masque(taille, masque):
    """Bandes complètes contiguës aux bords ; aucun trou intérieur retiré."""
    w,h=taille;result=set()
    for rows in (range(h),range(h-1,-1,-1)):
        for y in rows:
            bande={(y,x) for x in range(w)}
            if not bande<=masque:break
            result|=bande
    for cols in (range(w),range(w-1,-1,-1)):
        for x in cols:
            bande={(y,x) for y in range(h)}
            if not bande<=masque:break
            result|=bande
    return frozenset(result)
