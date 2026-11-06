"""Outils et expériences proposés dans le Python existant ; aucun accès au vrai jeu."""
import copy
import hashlib
import math
import time

import numpy as np

from chrysalide.arc3.langage import ErreurLangage, Programme, _appeler_fonction, _simple
from chrysalide.arc3.sim_rapide import cloner
from chrysalide.langue import depuis_python


class Proposition:
    def __init__(self, source):
        if len(source) > 16000:
            raise ValueError('Proposition trop longue')
        p = depuis_python(source)
        if set(p) - {'regles', 'fonctions', 'experience'} or p.get('regles'):
            raise ValueError('Un outil ou une experience ne peut modifier les regles du monde')
        self.programme = copy.deepcopy(p)
        self.source_sha = hashlib.sha256(source.encode()).hexdigest()
        try:
            self.outils = Programme({'regles': [], 'fonctions': p.get('fonctions', {})})
        except ErreurLangage as e:
            raise ValueError(str(e)) from e
        for d in p.get('fonctions', {}).values():
            if set(d) != {'params', 'expr'}:
                raise ValueError('Definition de fonction : params et expr uniquement')
        self.experience = p.get('experience')
        if self.experience is not None:
            if (not isinstance(self.experience, dict)
                    or set(self.experience) != {'actions', 'question'}
                    or not isinstance(self.experience['question'], str)):
                raise ValueError('Experience : actions et question requises')
            actions = self.experience['actions']
            if not isinstance(actions, list) or not 1 <= len(actions) <= 12:
                raise ValueError('Experience de 1 a 12 coups')
            for a in actions:
                if (not isinstance(a, list) or not a or not isinstance(a[0], str)
                        or len(a) not in (1, 3)):
                    raise ValueError('Action canonique attendue')
                if a[0] == 'MOUSE':
                    if len(a) != 3 or any(type(v) is not int or not 0 <= v < 64 for v in a[1:]):
                        raise ValueError('Coordonnees de clic invalides')
                elif len(a) != 1 or a[0] not in ('UP', 'DOWN', 'LEFT', 'RIGHT', 'SPACE', 'UNDO'):
                    raise ValueError('Action inconnue')

    def appeler(self, nom, *args):
        if nom not in self.outils.fonctions:
            raise ValueError('Outil inconnu')
        f = self.outils.fonctions[nom]
        if len(args) != len(f['params']):
            raise ValueError('Arite invalide')
        try:
            valeurs = [_simple(copy.deepcopy(a)) for a in args]
            return _appeler_fonction(f, valeurs, nom)
        except ErreurLangage as e:
            raise ValueError(str(e)) from e

    def tester_outil(self, nom, cas):
        debut = time.process_time()
        essais = []
        for args, attendu in cas:
            try:
                obtenu = self.appeler(nom, *args)
                essais.append({'conforme': obtenu == attendu, 'obtenu': obtenu, 'attendu': attendu})
            except (ValueError, TypeError, RuntimeError, IndexError) as e:
                essais.append({'conforme': False, 'erreur': repr(e)})
        return {'statut': 'tests_conformes' if essais and all(x['conforme'] for x in essais) else 'outil_refuse',
                'essais': essais, 'cpu_s': time.process_time() - debut, 'source_sha256': self.source_sha,
                'preuve_sur_jeu_reel': False}

    def evaluer_experience(self, chaines, poids=None):
        from agent_p1.experiences import evaluer_candidat
        debut = time.process_time()
        if self.experience is None or len(chaines) < 2:
            raise ValueError('Experience et au moins deux hypotheses requises')
        seq = [tuple(a) for a in self.experience['actions']]
        if poids is None:
            poids = dict.fromkeys(chaines, 1 / len(chaines))
        if (set(poids) != set(chaines) or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                                            for v in poids.values())):
            raise ValueError('Poids strictement positifs requis ; pas de probabilite inventee')
        modeles, controles = {}, {}
        base = None
        for nom, c in chaines.items():
            observation = [c.grilles, c.lots, c.coups, c.description_perception()]
            if base is None:
                base = observation
            if observation != base:
                raise ValueError('Hypotheses issues du meme historique et de la meme perception requises')
            if c.refute or len(seq) > c.limite - c.coups:
                raise ValueError('Hypothese refutee ou reserve de coups insuffisante')
            if any(a not in [tuple(v) for v in c.actions] for a in seq):
                raise ValueError('Action indisponible dans une hypothese')
            rapport, courant = c.rejouer()
            if courant is None or not rapport['catalogue_shacl']:
                raise ValueError('Hypothese non admissible au rejeu')
            controles[nom] = rapport
            modeles[nom] = _ModeleVisible(c, *courant)
        e = evaluer_candidat(seq, modeles, dict.fromkeys(chaines), poids)
        return {'statut': 'experience_discriminante_simulee' if e['groupes'] > 1 else 'sans_information_visible',
                'evaluation': e, 'question': self.experience['question'], 'controles': controles,
                'cout_coups_prefixe': len(e['seq']), 'cout_coups_propose': len(seq),
                'poids_statut': 'convention_de_comparaison_non_calibree',
                'risque_statut': 'conditionnel_aux_modeles_pas_garantie',
                'signatures_hypotheses': {n: c.signature() for n, c in chaines.items()}, 'cpu_s': time.process_time() - debut,
                'droit_action': False, 'nouveaux_coups_reels': 0, 'source_sha256': self.source_sha}


class _ModeleVisible:
    def __init__(self, chaine, pc, scene):
        self.c, self.pc = chaine, pc
        self.initial = cloner(scene, pc.etat)

    def simuler_seq(self, _etat, seq):
        scene, self.pc.etat = cloner(*self.initial)
        traj = []
        for a in seq:
            if scene.issue is None:
                self.pc.step(scene, a)
            if scene.issue is not None and scene.issue not in ('niveau', 'victoire'):
                obs = ('mort',)
            else:
                # Une différence cachée sans effet observable ne départage PAS les hypothèses.
                image = np.asarray(self.c.perception.rendu(scene))
                obs = (scene.issue, image.shape, image.tobytes())
            traj.append(obs)
        return traj, None
