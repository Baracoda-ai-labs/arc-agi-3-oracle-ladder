"""Calcul dans l'ouvrier existant, sans accès à un laboratoire ni au suffixe réel."""
import copy
import time

import numpy as np
from chaine_coherente import Chaine

from chrysalide.arc3.moteur import MoteurC, nom_action


class PerceptionTransmise(MoteurC):
    """Perception complète et couches matérialisées, sans fermeture lambda non sérialisable."""
    def __init__(self, moteur):
        self.tr = copy.deepcopy(moteur.tr)
        couleurs = set(range(16)) | {o[0] for etat in self.tr.etats for o in etat}
        couches = getattr(moteur, '_couches', lambda c: 0)
        self.couches_table = {c: couches(c) for c in couleurs}

    def _couches(self, couleur):
        return self.couches_table.get(couleur, 0)


class MoteurObservateur(MoteurC):
    def proposer(self, historique, coup=0):
        debut = time.process_time()
        r = super().proposer(historique)
        resultat = {'statut': 'sans_modele', 'predictions': [], 'droit_action': False}
        if r is not None and r[1] is not None:
            plan = [nom_action(a if 'action' in a else a['actions'][0]) for a in r[0]]
            c = Chaine(self, r[1], historique['grilles'], historique['lots'], plan,
                       coups_deja_joues=coup, films=historique.get('films'))
            # Le CPU ne choisit ici aucune variante : même plan que le moteur initial.
            controle = c.adopter_plan(plan)
            resultat.update(statut=controle['statut'], controle=controle,
                             programme=r[1], plan=plan, signature=c.signature())
            if controle['statut'] == 'plan_simule_valide':
                _, courant = c.rejouer()
                pc, sc = courant
                for action in plan[:12]:
                    pc.step(sc, action)
                    resultat['predictions'].append({'action': list(action),
                        'image': np.asarray(self.rendu(sc)).tolist(), 'issue': sc.issue})
        if r is not None and r[1] is not None:
            resultat['perception_complete'] = PerceptionTransmise(self)
        resultat['cpu_enfant_s'] = time.process_time() - debut
        # Ce rapport est transporté par l'interface existante ; pas d'état de jeu partagé.
        self.infos = copy.deepcopy(self.infos)
        return resultat
