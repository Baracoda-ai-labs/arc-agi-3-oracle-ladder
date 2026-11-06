"""Point d'action Franzen : observer sans choisir, bloquer ni rejouer un coup."""
import copy
import os
import types
from collections import deque

from observateur_cpu import cle_instantane


class Liaison:
    def __init__(self, solveur, observateur, partie, minimum=40, periode=20):
        if minimum < 1 or minimum > 40 or periode < 1:
            raise ValueError('Fenetre ou periode invalide')
        self.s, self.observateur, self.partie = solveur, observateur, partie
        self.minimum, self.periode = minimum, periode
        self.transitions_segment = 0
        self.actif = True
        self.coups = int(getattr(solveur, "action_count", 0))
        etat = getattr(getattr(solveur, "game", None), "current_state", None)
        self.score = int(getattr(etat, "levels_completed", 0))
        self.niveau = self.score + 1
        self.journal, self.derniere = deque(maxlen=1000), None
        self.images, self.lots, self.films = deque(maxlen=41), deque(maxlen=40), deque(maxlen=40)
        self.images.append(self._image())
        self.original = solveur._execute_action

        def executer(_s, *args, **kwargs):
            if self.actif:
                try:
                    self._lire()
                except Exception as e:  # noqa: BLE001 — observation uniquement, vrai coup encore à jouer
                    self._echec(e)
            payload = self.original(*args, **kwargs)  # toute erreur du vrai jeu remonte, jamais rejouée
            if self.actif:
                try:
                    self._observer(payload)
                except Exception as e:  # noqa: BLE001 — le vrai coup a déjà eu lieu, rendre son payload intact
                    self._echec(e)
            return payload
        self.enveloppe = executer
        solveur._execute_action = types.MethodType(executer, solveur)

    def _image(self):
        return [list(map(int, row)) for row in self.s.current_frame().grid]

    def _echec(self, erreur):
        self.actif = False
        self.journal.append({'statut': 'observateur_desactive', 'erreur': repr(erreur), 'coup': self.coups})

    def _historique(self):
        return {'grilles': list(self.images), 'lots': list(self.lots), 'films': list(self.films), 'precedents': []}

    def _contexte(self):
        return {'partie': self.partie, 'niveau': self.niveau, 'coup': self.coups}

    def _lire(self):
        f = self.observateur.future
        if f is None or not f.done():
            return
        r = self.observateur.lire(cle_instantane(self._historique(), self._contexte()))
        self.derniere = r
        self.journal.append({'statut': r['statut'], 'perime': r.get('perime'),
                             'droit_action': False, 'coup': self.coups,
                             'proposition': (r.get('proposition') or {}).get('statut')})

    def _observer(self, payload):
        if not isinstance(payload, dict) or not payload.get('executed'):
            return
        from chrysalide.arc3.moteur import nom_action
        self.coups += 1
        nom = str(payload['action_name']).upper()
        image = self._image()
        score = int(payload.get('score', self.score))
        frontiere = (nom == 'RESET' or payload.get('game_over') or payload.get('run_complete')
                     or payload.get('level_completed') or score != self.score)
        if frontiere:
            self.score, self.niveau = score, score + 1
            self.transitions_segment = 0
            self.images.clear(); self.lots.clear(); self.films.clear()
            self.images.append(image)
            self.journal.append({'statut': 'frontiere', 'action': nom, 'coup': self.coups})
            return
        action = {'action': nom}
        if nom_action(action)[0] == 'MOUSE':
            data = payload.get('action_data') or {}
            action.update(row=data.get('row', data.get('y')), col=data.get('col', data.get('x')))
            if action['row'] is None or action['col'] is None:
                raise ValueError('Clic sans coordonnees, ne pas inventer une observation')
        self.transitions_segment += 1
        self.images.append(image)
        self.lots.append({'actions': [action]})
        self.films.append(copy.deepcopy(payload.get('animation_chain')))
        if (self.transitions_segment >= self.minimum
                and (self.transitions_segment - self.minimum) % self.periode == 0):
            if self.observateur.future is None:
                r = self.observateur.soumettre(self._historique(), self._contexte())
                self.journal.append({**r, 'coup': self.coups, 'droit_action': False})
            else:
                self.journal.append({'statut': 'occupe_sans_file', 'coup': self.coups})

    def fermer(self):
        self.actif = False
        if getattr(self.s._execute_action, '__func__', None) is self.enveloppe:
            self.s._execute_action = self.original
        self.observateur.fermer()


def installer(solveur, partie):
    """Entrée explicite, uniquement appelée dans la copie expérimentale du harnais."""
    if os.environ.get('CHRYS_PORTE_V4') == '1' or os.environ.get('CHRYS_MOTEUR') == '1':
        raise ValueError('Observateur seul requis, sans porte ni moteur synchrone')
    if not 0 < float(os.environ.get('CHRYS_MOTEUR_PROCESSUS_DELAI_S', '0')) <= 15:
        raise ValueError('Delai dur observateur explicite requis, au plus 15 s')
    if not 1 <= int(os.environ.get('CHRYS_MOTEUR_OUVRIERS', '2')) <= 2:
        raise ValueError('Au plus deux ouvriers CPU')
    from moteur_observateur import MoteurObservateur
    from observateur_cpu import Observateur

    from chrysalide.arc3.moteur_processus import MoteurDistant
    return Liaison(solveur, Observateur(MoteurDistant(MoteurObservateur(budget=2))), partie)
