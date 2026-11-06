"""Raccord des calques existants à une scène composée ; aucune dynamique réécrite."""
import copy
import numpy as np
from chrysalide.arc3.moteur import MoteurFormel
from correspondance_contextes_objets import _base,reaffecter_observation
from perception_guidee import proposer_calques,PerceptionGuidee
from composition_depuis_observations import proposer_composition
from composition_contextes_objets import composer
from chaine_coherente import Chaine
from chaine_agent_integree import lots


class ProjectionCiblesComposees(MoteurFormel):
    """Métadonnées de rôles pour le proposeur existant ; rendu/scène inchangés."""
    def __init__(self,vue,principal,image):
        self.vue_composee=copy.deepcopy(vue)
        base,_=_base(principal.perception)
        for nom in ('mobiles','buts','statiques','hud','mouvements'):
            setattr(self,nom,copy.deepcopy(getattr(base,nom)))
        scene=vue.scene(image)
        for j,s in enumerate(self.statiques):
            matches=[o for o in scene.sprites if f'statique_{j}' in o['tags']]
            if len(matches)!=1:raise ValueError('cible_canonique_ambigue')
            s.update(x=matches[0]['x'],y=matches[0]['y'],pixels=matches[0]['pixels'].copy())
    def vue(self,image):return self.vue_composee.vue(image)
    def scene(self,image):return self.vue_composee.scene(image)
    def signature_observation(self):
        return {'methode':'projection_cibles_scene_composee','composee':self.vue_composee.signature_observation(),
                'buts_candidats':self.buts,'mouvements':self.mouvements}


def proposer_avec_revision(principal,alternatif,images,actions,issues=None,films=None,secondes=5.):
    c,diag=proposer_composition(principal,alternatif,images,actions,issues,films,secondes)
    if c is not None:return [c],diag
    if diag.get('refus')!='suffixe_refute':return [],diag
    fin=diag['fin_apprentissage'];contre=diag['transition_divergence']
    transitions=[(images[r['transition']-1],actions[r['transition']-1],images[r['transition']],r['mode_avant'])
                 for r in diag['commutations']]
    core,dc=composer(principal,alternatif,transitions,images[fin],diag['commutations'][-1]['mode_apres'])
    if core is None:return [],{'refus':'composition_initiale_refusee','diagnostic':dc}
    projection=ProjectionCiblesComposees(core.perception,principal,images[fin])
    # Aucune image après le contre-exemple n'entre dans le proposeur.
    propositions,calques=proposer_calques(projection,core.programme,
        [np.asarray(g).tolist() for g in images[fin:contre+1]],
        [core.action_tuple(l['actions'][0]) for l in lots(actions[fin:contre])])
    rapport={'SDK':False,'contre_exemple':contre,'apprentissage_commutations':diag['commutations'],
        'calques':calques,'suffixe_tenu_a_part':[contre+1,len(actions)],'essais':[],
        'programme_dynamique_modifie':False,'visibilite_transcontextuelle_provisoire':True}
    # Reconstruire depuis la première observation fournie, pas après un ancien écart.
    modes=[i for i,s in enumerate((principal,alternatif)) if reaffecter_observation(s,images[0])[0] is not None]
    if len(modes)!=1:return [],{**rapport,'refus':'mode_initial_ambigu'}
    origine,do=composer(principal,alternatif,transitions,images[0],modes[0])
    if origine is None:return [],{**rapport,'refus':'origine_non_reaffectable','diagnostic':do}
    resultat=[]
    for nom,p in propositions:
        vue=PerceptionGuidee(ProjectionCiblesComposees(origine.perception,principal,images[0]),p.perception.points)
        candidat=Chaine(vue,origine.programme,[np.asarray(g).tolist() for g in images],lots(actions),
            origine.actions,coups_deja_joues=len(actions),reserve=principal.limite,films=films)
        controle,state=candidat.rejouer()
        admis=state is not None and all(controle.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele'))
        rapport['essais'].append({'nom':nom,'points':p.perception.points,'controle':controle,'admis':admis})
        if admis:
            candidat.activer_atms();candidat.preuve_calque_contextuel={'contre_exemple':contre,'nom':nom,
                'suffixe_tenu_a_part':[contre+1,len(actions)],'provisoire':True,'causalite_prouvee':False}
            resultat.append(candidat)
    rapport.update(admis=bool(resultat),candidats=len(resultat),rejeu_integral=True)
    return resultat,rapport
