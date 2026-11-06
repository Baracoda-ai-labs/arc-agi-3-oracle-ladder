"""Propose quatre hypothèses de perception/clic ; admission sur tout l'historique."""
import copy
from chrysalide.arc3.logique.hitbox_formes import trajectoire,etendre_observations
from chrysalide.arc3.logique.induction import induire
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.moteur import MoteurC,_codes_c,_clics_offerts,_lot_c
from chaine_coherente import Chaine


def proposer(images,lots,films,prior=None):
    if not lots or len(images)!=len(lots)+1:
        return []
    actions=_codes_c(lots)
    if actions is None or not all(isinstance(a,tuple) for a in actions):
        return []
    calibration=min(8,len(lots))
    grilles=[g.tolist() if hasattr(g,'tolist') else g for g in images]
    candidats=[]
    for connexite in (4,8):
        for boites in (False,True):
            try:
                tr=trajectoire(grilles[:calibration+1],actions[:calibration],connexite,boites)
                th,_=induire([(tr,None,None)],limite_s=2,anciennes=copy.deepcopy(prior))
                th.hors_jeu=tr.exclues
                programme,non=exporter(th,tr.taille)
                if non:continue
                etendre_observations(tr,grilles,actions)
                m=MoteurC();m.tr=tr;m.th_releve=th;m.th_plan=th;m._couches=th.couches()
                c=Chaine(m,programme,grilles,lots,[],coups_deja_joues=len(lots),
                         reserve=2**63-1,origine='hypothese_clics_couples',films=films)
                controle,courant=c.rejouer()
                if courant is None:continue
                c.diagnostic_hitbox={**tr.hypothese_hitbox,'controle':controle,
                    'observations_validees':len(lots),'suffixe_sans_reinduction':len(lots)-calibration}
                c.actions=[Chaine.action_tuple(_lot_c(a,tr)) for a in _clics_offerts(th,tr)]
                c.activer_atms()
                candidats.append(c)
            except (ValueError,TypeError,KeyError,IndexError):
                continue
    return candidats
