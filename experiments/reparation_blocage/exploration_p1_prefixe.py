"""Raccord lecture seule P1 : choix sans jouer/reset, graphe des observations intégrales."""
from types import SimpleNamespace
import numpy as np
from agent_p1.generique import Explorateur, type_action, objets, CLAVIER


class GrapheIntegral(Explorateur):
    def candidats(self, im):
        # Même abstraction/ordre P1, sans confondre plafond de liste et exploration épuisée.
        offre = self.lab.actions_disponibles
        out = [a for a in CLAVIER if a in offre]
        if 6 in offre:
            obs = sorted(objets(im), key=lambda o: (o['bord'], o['n'] > 400,
                         -self.mem.taux(f"clic:c{o['c']}"), o['n']))
            vus = set()
            for o in obs:
                point = (o['x'], o['y'])
                if point not in vus:
                    vus.add(point)
                    out.append(('clic', *point))
        return out

    def masque(self, im):
        # Aucun bord ni compteur présumé décoratif ; aucune preuve de masque importée.
        return np.asarray(im).copy()


def charger_observations(ex, episodes):
    resultats={}; ambigues=set(); n=0
    for episode in episodes:
        images,actions,issues=(episode[k] for k in ('grilles','actions','issues'))
        if len(images)!=len(actions)+1 or len(issues)!=len(actions):
            raise ValueError('Episode non aligne')
        for i, action in enumerate(actions):
            if action==0:raise ValueError('RESET ne constitue pas une arete apprise')
            avant,apres=map(np.asarray,images[i:i+2])
            a=tuple(action) if isinstance(action,list) else action
            k0,k1=ex.cle(avant),ex.cle(apres)
            ex.cands.setdefault(k0,ex.candidats(avant))
            for k,im in ((k0,avant),(k1,apres)):
                ex.progres.noter(im);ex.valeur.setdefault(k,ex.progres.evaluer(im)[0])
            mort=issues[i]=='defaite'; destination='mort' if mort else k1
            paire=(k0,a); observes=resultats.setdefault(paire,set());observes.add(destination)
            if len(observes)>1:
                ambigues.add(paire);ex.aretes.setdefault(k0,{}).pop(a,None)
            else:ex.aretes.setdefault(k0,{})[a]=destination
            ex.mem.noter(type_action(a,avant),k1!=k0,issues[i] in ('niveau','victoire'))
            if not mort and k1!=k0:
                ex.deltas.setdefault(type_action(a,avant),[]).append(ex.valeur[k1]-ex.valeur[k0])
            ex.trace.append((k0,a,k1));n+=1
    return n,ambigues


def priorite_compteur(ex,episodes,image,offre,choix,raison,prudence=()):
    """Heuristique de répétition ; ne modifie ni graphe intégral ni modèle."""
    from chrysalide.arc3.masque import Masque,etat_masque
    from collections import Counter
    masque=Masque()
    for episode in episodes:
        masque.nouvelle_vie()
        for avant,apres,issue in zip(episode['grilles'],episode['grilles'][1:],episode['issues']):
            if issue=='continue':masque.observer(np.asarray(avant).tolist(),np.asarray(apres).tolist())
    cellules=masque.cellules()
    diag={'cellules_compteur_hypothese':len(cellules),'cle_integrale_conservee':True,
          'preuve_inertie':False,'films_intermediaires_non_evalues':True,'decision_changee':False,
          'repetition':'couple_vue_percue_action_meme_si_effet'}
    if not cellules or raison!='exploration_nouvelle':return choix,raison,diag
    vue=etat_masque(np.asarray(image).tolist(),0,cellules);repetitions=Counter()
    for episode in episodes:
        for avant,apres,action,issue in zip(episode['grilles'],episode['grilles'][1:],episode['actions'],episode['issues']):
            if issue!='continue':continue
            a=tuple(action) if isinstance(action,list) else action
            if etat_masque(np.asarray(avant).tolist(),0,cellules)==vue:
                repetitions[a]+=1
    k=ex.cle(image);transitions=ex.aretes.get(k,{})
    candidats=[a for a in ex.candidats(image) if a not in prudence and a not in transitions
               and (6 if isinstance(a,tuple) else a) in offre]
    diag['repetitions_choix_initial']=repetitions[choix]
    if candidats:
        autre=max(candidats,key=lambda a:(-repetitions[a],ex.priorite(a,image)))
        if repetitions[autre]<repetitions[choix]:
            diag.update(decision_changee=True,repetitions_choix_final=repetitions[autre])
            return autre,'priorite_anti_repetition_compteur_hypothese',diag
    return choix,raison,diag


def proposer(images, actions, issues, offre, graine=0, memoire_episodes=(), observations_episodes=()):
    lab = SimpleNamespace(image=np.asarray(images[0]), actions_disponibles=list(offre))
    ex = GrapheIntegral(lab, None, graine=graine)
    n,ambigues=charger_observations(ex,[*observations_episodes,
        {'grilles':images,'actions':actions,'issues':issues}])
    lab.image = np.asarray(images[-1])
    if not offre:
        return None
    a, raison = ex.choisir()
    if raison == 'graphe_epuise_aleatoire':
        return None
    from memoire_episodes import risques
    prudence=risques(memoire_episodes,lab.image,offre)
    transitions=ex.aretes.get(ex.cle(lab.image),{}) if prudence else {}
    alternatives=[c for c in ex.candidats(lab.image) if c not in prudence
        and transitions.get(c) not in ('mort',ex.cle(lab.image))] if prudence else []
    if a in prudence and alternatives:
        a=max(alternatives,key=lambda c:ex.priorite(c,lab.image))
        raison='alternative_au_risque_episode_provisoire'
    if raison == 'graphe_epuise_aleatoire':
        return None
    a,raison,diag_compteur=priorite_compteur(ex,[*observations_episodes,
        {'grilles':images,'actions':actions,'issues':issues}],lab.image,offre,a,raison,prudence)
    if (6 if isinstance(a, tuple) else a) not in offre:
        return None
    return {'actions':[list(a) if isinstance(a,tuple) else a], 'predictions':[[]],
        'modeles':[], 'statut':'experience_conditionnelle', 'risque':'inconnu',
        'but':'inconnu', 'origine':'p1_graphe_observe', 'raison':raison, 'graine_exploration':graine,
        'heuristique':'progres_P1_non_preuve_de_but', 'masque':[],
        'memoire_defaites_provisoire':bool(prudence), 'etats_observes':len(ex.valeur), 'transitions_observees':len(ex.trace),
        'episodes_anterieurs':len(observations_episodes), 'aretes_ambigues':len(ambigues),
        'effet_visible_pas_preuve_utilite':True,'priorite_compteur':diag_compteur}
