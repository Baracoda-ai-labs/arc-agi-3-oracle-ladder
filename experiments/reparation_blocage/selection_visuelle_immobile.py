"""Attribut visuel réversible avant mouvement : hypothèse locale, pas simulateur."""
import hashlib
import numpy as np
from agent_p1.generique import objets
from chrysalide.arc3.masque import Masque
from chrysalide.langue.ontologie_formelle import MECANISMES


def _vue(image, cellules):
    vue=np.asarray(image).copy()
    for y,x in cellules:vue[y,x]=-1
    return vue


def _signature(image):
    return hashlib.sha256(np.asarray(image,dtype=np.int16).tobytes()).hexdigest()


def analyser(images,actions,films,issues):
    """Ne généralise ni causalité ni inertie depuis la projection du compteur."""
    if len(images)!=len(actions)+1 or len(films)!=len(actions) or len(issues)!=len(actions):raise ValueError('Historique non aligné')
    for i,film in enumerate(films):
        if not len(film) or not np.array_equal(film[-1],images[i+1]):raise ValueError('Film non aligné')
    m=Masque()
    for a,b,issue in zip(images,images[1:],issues):
        if issue=='continue':m.observer(np.asarray(a).tolist(),np.asarray(b).tolist())
    cellules=m.cellules();vues=[_vue(g,cellules) for g in images]
    sorties=[]
    for i,action in enumerate(actions):
        if not isinstance(action,(list,tuple)) or action[0]!='clic':continue
        avant,apres=vues[i:i+2];delta=avant!=apres
        if not delta.any():continue
        _,x,y=action
        # Réutilise les composantes perceptives existantes, sans exiger une mobilité.
        ancres=[o for o in objets(images[i]) if abs(o['x']-x)<=1 and abs(o['y']-y)<=1]
        for o in ancres:
            # Le coeur de cette classe reste identique ; le changement est un attribut autour.
            coeur=np.asarray(images[i])==o['c']
            if not np.array_equal(coeur,np.asarray(images[i+1])==o['c']):continue
            actifs=[p for p in objets(images[i+1]) if p['c'] not in np.unique(images[i])]
            proches=[p for p in actifs if abs(p['x']-x)<=3 and abs(p['y']-y)<=3]
            if not proches:continue
            # Retour exact dans la vue projetée ; toujours provisoire vis-à-vis du compteur/phase.
            retours=[j for j in range(i+1,len(actions)) if np.array_equal(vues[j],apres)
                     and np.array_equal(vues[j+1],avant)]
            distants=[p for p in actifs if p not in proches]
            sorties.append({'coup_activation':i+1,'action_activation':list(action),'ancre':o,
                'pixels_attribut':int(delta.sum()),'marqueurs_proches':proches,'marqueurs_distants':distants,
                'retours_observes':[j+1 for j in retours],
                'contrat_candidat':'selection_clic','roles_candidats':MECANISMES['selection_clic']['roles'],
                'heuristique_spatiale':{'rayon_ancre':1,'rayon_marqueur':3,'regle_apprise':False},
                'films_utilises':'alignement seulement ; attribut mesuré sur images finales',
                'hypothese':'attribut_selection_visuelle','mouvement_observe':False,'controle_valide':False,
                'but_valide':False,'portee':'locale_provisoire','cellules_compteur_hypothese':list(cellules),
                'sha_integral_avant':_signature(images[i]),'sha_integral_actif':_signature(images[i+1]),
                'vue_avant':avant,'vue_active':apres})
    return sorties


def proposer(images,actions,films,issues,offre):
    """Une étape d'expérience ; toute réactivation est suivie d'une nouvelle observation."""
    if 6 not in offre:return None
    for h in reversed(analyser(images,actions,films,issues)):
        if not h['retours_observes'] or not h['marqueurs_distants']:continue
        cellules=h['cellules_compteur_hypothese'];courant=_vue(images[-1],cellules)
        historique=[(_vue(g,cellules),a) for g,a in zip(images,actions)]
        nouvelles=[]
        for o in h['marqueurs_distants']:
            cible=['clic',o['x'],o['y']]
            if not any(np.array_equal(g,h['vue_active']) and list(a)==cible
                       for g,a in historique if isinstance(a,(tuple,list))):nouvelles.append(cible)
        if not nouvelles:continue
        if np.array_equal(courant,h['vue_active']):
            action=nouvelles[0];etape='sonder_marqueur_contextuel'
        elif np.array_equal(courant,h['vue_avant']):
            # Une seule réactivation d'accès autorisée par hypothèse : éviter boucle persistante.
            n=sum(np.array_equal(g,h['vue_avant']) and list(a)==h['action_activation']
                  for g,a in historique if isinstance(a,(tuple,list)))
            if n>1:continue
            action=h['action_activation'];etape='retablir_contexte_pour_sonde_nouvelle'
        else:continue
        preuve={k:v for k,v in h.items() if k not in ('vue_avant','vue_active')}
        return {'actions':[action],'predictions':[[]],'modeles':[],
            'statut':'experience_conditionnelle','origine':'selection_visuelle_immobile',
            'raison':etape,'but':'inconnu','risque':'inconnu','cout_coup':1,
            'cible_experience_nouvelle':nouvelles[0],'hypothese_selection':preuve,
            'questions':['marqueur distant interactif ou simple indication visuelle',
                         'effet dépendant du contexte sélectionné ou indépendant'],
            'cle_integrale_conservee':True,'projection_pas_preuve_equivalence':True}
    return None
