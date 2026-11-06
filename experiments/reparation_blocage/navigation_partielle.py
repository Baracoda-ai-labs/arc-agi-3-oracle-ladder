"""Adaptateur prospectif de navigation ; aucune promesse de rendu ou d'issue."""
import copy
import hashlib
import json
import numpy as np
from navigation_gravite_visible import NavigationVisible
from hypotheses_navigation import HypothesesNavigation


def code_action(action):
    if type(action) is int and action in (3, 4):
        return action
    if (isinstance(action, list) and len(action) == 3 and action[0] == 'clic'
            and all(type(v) is int and 0 <= v < 64 for v in action[1:])):
        return 6
    raise ValueError('Action hors catalogue ou clic malforme')


class NavigationPartielle:
    def __init__(self, images, actions, films, issues, limite=80):
        if len(images) != len(actions)+1 or len(films)!=len(actions) or len(issues)!=len(actions):
            raise ValueError('Prefixe incomplet')
        for a in actions:
            code_action(a)
        self.images=[np.array(x,copy=True) for x in images]
        self.actions=copy.deepcopy(actions); self.films=copy.deepcopy(films); self.issues=list(issues)
        self.limite=limite; self.attente=None; self.journal=[]
        m=NavigationVisible(self.images,self.actions)
        m.apprendre_clics(self.images,self.actions)
        self.h=HypothesesNavigation(m)
        for i,a in enumerate(self.actions):
            self.h.observer(self.images[i],a,self.images[i+1],self.films[i],self.issues[i])
        if not self.h.actives(): raise ValueError('Catalogue refute sur prefixe')
        self.admission={'statut':'compatible_sur_champs_partiels','coups':len(actions),'issue':'inconnue','limite':'ajustement retrospectif sur prefixe fourni seulement'}

    def signature(self):
        h=hashlib.sha256()
        for im in self.images: h.update(im.tobytes())
        h.update(json.dumps([self.actions,self.issues,self.h.actives()],sort_keys=True).encode())
        return h.hexdigest()

    def predire(self, action, offre):
        if code_action(action) not in offre: raise ValueError('Action non offerte')
        if self.attente is not None: raise ValueError('Observation precedente attendue')
        if len(self.actions)>=self.limite or (self.issues and self.issues[-1]!='continue'): raise ValueError('Fin ou budget')
        preds={n:self.h.predire(self.images[-1],action,n) for n in self.h.actives()}
        if not preds: raise ValueError('Catalogue refute')
        result={'actions':[copy.deepcopy(action)],'predictions_partielles':preds,'couverts':['position_controle','disparition_locale_conditionnelle'],
                'inconnus':['issue','contacts','decor_dynamique','pixels_complets','phase'],
                'conditions':['camera_alignable_erreur_max_0.15','silhouette_identifiable','disparition_non_occultee'],
                'issue':'inconnue','risque':'inconnu','prefixe_sha256':self.signature(),'coups_deja_joues':len(self.actions)}
        # L'observateur existant réévalue la projection : figer son modèle AVANT l'action.
        self.attente=(copy.deepcopy(result),copy.deepcopy(self.h),self.images[-1].copy())
        return copy.deepcopy(result)

    def decider(self, offre):
        # Le solveur existant borne les noeuds, pas le temps mural.
        p=self.h.proposer(self.images[-1],offre)
        r=self.predire(p['action'], offre);r['raison']=p['raison'];r['but']='hypothese_non_prouvee'
        return r

    def observer(self,action,image,film,issue):
        if self.attente is None or action!=self.attente[0]['actions'][0]: raise ValueError('Action sans prediction prospective')
        prediction,original,before=self.attente
        h=copy.deepcopy(original)
        try:
            record=h.observer(before,action,image,film,issue)
            record['statut_partiel']='issue_non_modelisee' if issue!='continue' else ('divergence_partielle' if any(not x['conforme'] for x in record['comparaisons']) else 'compatible_sur_champs_observes')
        except (ValueError,IndexError) as exc:
            h=original  # aucune révocation partielle ne survit à un contrôle incomplet
            record={'statut_partiel':'observation_non_comparable','raison':str(exc),'actives':h.actives()}
        self.h=h;self.images.append(np.array(image,copy=True));self.actions.append(copy.deepcopy(action));self.films.append(copy.deepcopy(film));self.issues.append(issue)
        self.attente=None
        record.update({'prediction_avant_action':prediction,'coups_deja_joues':len(self.actions),'issue_couverte':False,'plan_invalide':issue!='continue' or record['statut_partiel']!='compatible_sur_champs_observes'})
        self.journal.append(record)
        return record
