"""Façade expérimentale : mêmes données et sémantique entre observation, code et plan."""
import ast
import copy
import hashlib
import json
import resource
import time
from pathlib import Path

import numpy as np

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.plan_langage import cle_complete, planifier_langage, regle_victoire
from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
from chrysalide.langue import appliquer_patch, depuis_python, lire_reponse, vers_python
from chrysalide.langue.theorie_contrats import vers_contrats


def empreinte(valeur):
    return hashlib.sha256(json.dumps(valeur, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Chaine:
    """Ne joue jamais un coup : propose, puis exige la prochaine observation réelle."""

    def __init__(self, perception, programme, grilles, lots, actions, coups_deja_joues=0,
                 reserve=150, origine='induit', films=None):
        if __package__:
            from .evidence_films import Films
        else:
            from evidence_films import Films
        assert len(grilles) == len(lots) + 1
        assert films is None or len(films) == len(lots)
        self.films = Films()
        for i in range(len(lots)):
            self.films.ajouter(grilles[i], films[i] if films is not None else None)
        self.perception = copy.deepcopy(perception)
        self.grilles, self.lots = copy.deepcopy(grilles), copy.deepcopy(lots)
        self.actions = copy.deepcopy(actions)
        self.coups = coups_deja_joues
        self.limite = reserve
        self.programme = copy.deepcopy(programme)
        self.origine = origine
        self.version = 1
        self.plan = None
        self.refute = False
        self.contre_exemples = []
        self.journal = []
        self.modele_sha = empreinte(self.programme)
        self._verifie = None
        self.atms = None

    def activer_atms(self):
        if __package__:
            from .atms import ATMS
        else:
            from atms import ATMS
        if self.atms is None:
            self.atms = ATMS()
        return self.atms

    def classifier(self, **indices):
        """Diagnostic seul ; la fiche est à recalculer après observation ou révision."""
        if __package__:
            from .ontologie_extensible import FicheRevision
        else:
            from ontologie_extensible import FicheRevision
        if not hasattr(self.perception, 'th_plan'):
            return {'statut': 'theorie_induite_absente', 'droit_action': False}
        if self.version != 1:
            return {'statut': 'contrats_a_reextraire_apres_revision', 'droit_action': False}
        if self.refute or empreinte(self.programme) != self.modele_sha:
            return {'statut': 'modele_invalide', 'droit_action': False}
        actions = [self.action_tuple(a)[0] for a in self.actions]
        return FicheRevision(self.perception.th_plan, actions, self.signature(), **indices).rapport()

    def _tracer_plan(self):
        if self.atms is None or self.plan is None:
            return True
        signature = self.signature()
        contexte = [f"{k}:{signature[k]}" for k in ("modele", "perception", "ontologie", "contrats")]
        contexte += ["validite_snapshot:" + signature["observations"]]
        for hypothese in contexte:
            self.atms.supposer(hypothese)
        observation = self.atms.fait("observation:" + signature["observations"])
        noeud = "plan:" + empreinte(self.plan)
        self.atms.justifier(noeud, [*contexte, observation])
        self.plan["contexte_atms"] = contexte
        self.plan["noeud_atms"] = noeud
        return self.atms.tient(noeud, contexte)

    @staticmethod
    def action_tuple(a):
        if isinstance(a, dict):
            from chrysalide.arc3.moteur import nom_action
            return nom_action(a)
        return tuple(a)

    def signature(self):
        return {'modele': self.modele_sha, 'observations': empreinte([self.grilles, self.lots]),
                'perception': empreinte(self.description_perception()),
                'films': empreinte(self.films.signatures()),
                'ontologie': self.ontologie_sha(), 'contrats': self.contrats_sha(), 'version': self.version}

    @staticmethod
    def ontologie_sha():
        from chrysalide.langue import ontologie_formelle
        return hashlib.sha256(Path(ontologie_formelle.__file__).read_bytes()).hexdigest()

    @staticmethod
    def contrats_sha():
        from chrysalide.langue import theorie_contrats
        return hashlib.sha256(Path(theorie_contrats.__file__).read_bytes()).hexdigest()

    def description_perception(self):
        if hasattr(self.perception, 'signature_observation'):
            return self.perception.signature_observation()
        tr = getattr(self.perception, 'tr', None)
        if tr is None:
            return {'methode': type(self.perception).__name__}
        return {'methode': type(self.perception).__name__, 'echelle': tr.s, 'origine': [tr.ox, tr.oy],
                'taille': list(tr.taille), 'fond': int(tr.fond),
                'masque': sorted([list(p) for p in tr.exclues])}

    def catalogue(self):
        ici = Path(__file__).resolve().parent
        bilan = json.loads((ici / 'bilan_skos_shacl.json').read_text())
        return (bool(bilan['conforme']) and self.ontologie_sha() == bilan['source_sha256']
                and self.contrats_sha() == bilan['contrats_sha256'])

    def rejouer(self, programme=None):
        if programme is None and empreinte(self.programme) != self.modele_sha:
            return {'refus': 'modele_modifie_hors_revision'}, None
        if programme is None and self._verifie is not None:
            debut_cache = time.process_time()
            signature, rapport, courant = self._verifie
            if signature == self.signature():
                if len(courant) == 2:  # anciens instantanés : migration du cache seulement
                    pc, sc = courant
                    courant = (pc.etat, pc.instantanes, pc.conflits, sc)
                etat, instantanes, conflits, sc = copy.deepcopy(courant)
                pc = ProgrammeCompile(self.programme)
                pc.etat, pc.instantanes, pc.conflits = etat, instantanes, conflits
                pc._ref.instantanes, pc._ref.conflits = instantanes, conflits
                return {**rapport, 'cache_verifie': True, 'cpu_rejeu': 0,
                        'cpu_cache': time.process_time() - debut_cache}, (pc, sc)
        p = self.programme if programme is None else programme
        debut = time.process_time()
        result = {'catalogue_shacl': self.catalogue(), 'traduction_python': False,
                  'rejeu': False, 'compilation_fidele': False}
        try:
            from cache_fidelite_traduction import fidele
            result['traduction_python'] = fidele(p, vers_python, depuis_python)
            if not result['traduction_python']:
                return result, None
            pi, pc = Programme(p), ProgrammeCompile(p)
            si, sc = self.perception.scene(self.grilles[0]), self.perception.scene(self.grilles[0])
            for k, (lot, image) in enumerate(zip(self.lots, self.grilles[1:], strict=True), 1):
                for action in lot['actions']:
                    a = self.action_tuple(action)
                    pi.step(si, a)
                    pc.step(sc, a)
                if (not np.array_equal(self.perception.rendu(si), self.perception.vue(image))
                        or si.issue is not None):
                    result.update(refus='observation', premiere_divergence=k)
                    return result, None
                if cle_complete(si, pi.etat) != cle_complete(sc, pc.etat):
                    result.update(refus='compilation', premiere_divergence=k)
                    return result, None
            result.update(rejeu=True, compilation_fidele=True, transitions=len(self.lots),
                          replis_compilation=len(pc.replis))
            if programme is None:
                self._verifie = (self.signature(), result,
                    copy.deepcopy((pc.etat, pc.instantanes, pc.conflits, sc)))
            return result, (pc, sc)
        except (ValueError, TypeError, KeyError, AssertionError) as e:
            result['refus'] = repr(e)
            return result, None
        finally:
            result['cpu_rejeu'] = time.process_time() - debut

    def verifier_plan(self, actions):
        controle, courant = self.rejouer()
        if courant is None:
            return False, controle
        pc, sc = courant
        pi = Programme(self.programme)
        pi.etat = copy.deepcopy(pc.etat)
        si = copy.deepcopy(sc)
        for k, action in enumerate(actions, 1):
            a = self.action_tuple(action)
            pi.step(si, a)
            pc.step(sc, a)
            if cle_complete(si, pi.etat) != cle_complete(sc, pc.etat):
                return False, {'refus': 'compilation_plan', 'pas': k}
            if sc.issue is not None:
                return sc.issue in ('niveau', 'victoire') and k == len(actions), {'issue': sc.issue, 'pas': k}
        return False, {'refus': 'pas_de_victoire_simulee'}

    def proposer(self, secondes=.5, methode='but', processus=2):
        self.plan = None
        if methode not in ('but', 'paliers', 'generique', 'portefeuille', 'nmcs', 'aleatoire', 'cegar'):
            return {'statut': 'methode_inconnue'}
        if empreinte(self.programme) != self.modele_sha or self.refute:
            return {'statut': 'modele_invalide'}
        controle, courant = self.rejouer()
        if courant is None or not controle['catalogue_shacl']:
            return {'statut': 'modele_non_admissible', 'controle': controle}
        pc, sc = courant
        debut = time.process_time()
        if methode == 'cegar':
            if __package__:
                from .cegar_compile import proposer as cegar
            else:
                from cegar_compile import proposer as cegar
            actions, infos = cegar(pc, sc, self.actions, secondes)
        elif methode in ('nmcs', 'aleatoire'):
            actions, infos = self.montecarlo(pc, sc, secondes, methode)
        elif methode == 'portefeuille':
            from chrysalide.arc3.logique.plan_portefeuille import portefeuille
            avant = resource.getrusage(resource.RUSAGE_CHILDREN)
            actions, infos = portefeuille(self.programme, sc, self.actions, noeuds=10000,
                secondes=secondes / processus, processus=processus, etat=pc.etat)
            apres = resource.getrusage(resource.RUSAGE_CHILDREN)
            infos['cpu_enfants'] = apres.ru_utime + apres.ru_stime - avant.ru_utime - avant.ru_stime
        else:
            actions, infos = planifier_langage(self.programme, sc, self.actions,
                recherche=methode, secondes=secondes, noeuds=10000, compiler=False, etat=pc.etat)
        cpu = time.process_time() - debut
        infos['budget_type'] = ('mur_par_processus' if methode == 'portefeuille' else
                                'cpu' if methode in ('nmcs', 'aleatoire', 'cegar') else 'mur')
        infos['cpu_total_mesure'] = cpu + infos.get('cpu_enfants', 0)
        if not actions:
            return {'statut': 'aucun_plan_retourne', 'infos': infos, 'cpu_recherche': cpu,
                    'preuve_impossibilite': False, 'controle': controle}
        if len(actions) > self.limite - self.coups:
            return {'statut': 'plan_hors_reserve', 'longueur': len(actions)}
        ok, preuve = self.verifier_plan(actions)
        if not ok:
            return {'statut': 'plan_refuse', 'preuve': preuve}
        self.plan = {'actions': [list(self.action_tuple(a)) for a in actions], **self.signature()}
        if not self._tracer_plan():
            self.plan = None
            return {'statut': 'contexte_atms_invalide'}
        return {'statut': 'plan_simule_valide', 'plan': copy.deepcopy(self.plan), 'preuve': preuve,
                'controle': controle, 'cpu_recherche': cpu, 'infos': infos}

    def montecarlo(self, pc, scene, secondes, methode):
        if __package__:
            from .montecarlo import chercher
        else:
            from montecarlo import chercher
        regle = regle_victoire(self.programme)
        if regle is None:
            return None, {'refus': 'pas_de_but_exprimable'}
        distance = pc.distance(regle)
        initial = cle_complete(scene, pc.etat)
        etats = {initial: (scene, copy.deepcopy(pc.etat))}

        def pas(cle, action):
            sc, etat = cloner(*etats[cle])
            pc.etat = etat
            pc.step(sc, action)
            nouvelle = cle_complete(sc, pc.etat)
            etats.setdefault(nouvelle, (sc, pc.etat))
            return nouvelle

        def gagne(cle):
            return etats[cle][0].issue in ('niveau', 'victoire')

        def perd(cle):
            return etats[cle][0].issue is not None and not gagne(cle)

        def note(cle):
            return -(distance(*etats[cle]) or 0)

        actions, infos = chercher(initial, self.actions, pas, gagne, perd, note,
            self.limite - self.coups, secondes, methode=methode, transitions_max=10000)
        return actions, {**infos, 'backend': 'ProgrammeCompile', 'etats_complets': len(etats)}

    def adopter_plan(self, actions, origine='moteur_existant'):
        self.plan = None
        if self.refute or empreinte(self.programme) != self.modele_sha:
            return {'statut': 'modele_invalide'}
        if len(actions) > self.limite - self.coups:
            return {'statut': 'plan_hors_reserve'}
        ok, preuve = self.verifier_plan(actions)
        if not ok or not self.catalogue():
            return {'statut': 'plan_refuse', 'preuve': preuve}
        self.plan = {'actions': [list(self.action_tuple(a)) for a in actions],
                     'origine': origine, **self.signature()}
        if not self._tracer_plan():
            self.plan = None
            return {'statut': 'contexte_atms_invalide'}
        return {'statut': 'plan_simule_valide', 'plan': copy.deepcopy(self.plan), 'preuve': preuve}

    def observer(self, action, image, victoire=False, termine=False, source='trace', film=None):
        ancienne_signature = self.signature()
        plan = self.plan
        self.plan = None
        if empreinte(self.programme) != self.modele_sha:
            return {'statut': 'modele_modifie_hors_revision', 'action_executee': False}
        if plan is None or any(plan[k] != ancienne_signature[k] for k in ancienne_signature):
            return {'statut': 'plan_absent_ou_perime', 'action_executee': False}
        if (self.atms is not None and plan.get('noeud_atms')
                and not self.atms.tient(plan['noeud_atms'], plan['contexte_atms'])):
            return {'statut': 'contexte_atms_invalide', 'action_executee': False}
        a = self.action_tuple(action)
        if a != tuple(plan['actions'][0]):
            return {'statut': 'action_hors_plan', 'action_executee': False}
        controle, courant = self.rejouer()
        if courant is None:
            return {'statut': 'modele_non_admissible', 'controle': controle}
        pc, sc = courant
        pc.step(sc, a)
        prediction, observation = self.perception.rendu(sc), self.perception.vue(image)
        juste = np.array_equal(prediction, observation)
        positions = np.argwhere(prediction != observation) if prediction.shape == observation.shape else None
        attendue = sc.issue
        if victoire:
            statut = 'victoire_reelle' if source == 'jeu' else 'victoire_verifiee_sur_trace'
        elif termine:
            statut = 'fin_sans_victoire'
        elif juste and attendue is None:
            statut = 'transition_confirmee'
        else:
            statut = 'but_refute' if juste and attendue in ('niveau', 'victoire') else 'modele_refute'
        film_aligne = film is None or (len(film) and np.array_equal(np.asarray(film)[-1], image))
        self.films.ajouter(self.grilles[-1], film if film_aligne else None)
        self.grilles.append(np.asarray(image).tolist())
        nom = a[0]
        self.lots.append({'actions': [{'action': nom, **({'row': a[1], 'col': a[2]} if nom == 'MOUSE' else {})}]})
        self.coups += 1
        if statut == 'transition_confirmee':
            self._verifie = (self.signature(), {**controle, 'transitions': len(self.lots)}, copy.deepcopy((pc.etat, pc.instantanes, pc.conflits, sc)))
        else:
            self._verifie = None
        if statut not in ('transition_confirmee', 'victoire_reelle', 'victoire_verifiee_sur_trace'):
            self.refute = True
            if self.atms is not None and plan.get('contexte_atms'):
                self.atms.interdire(plan['contexte_atms'])
            self.contre_exemples.append({'coup': self.coups, 'action': list(a), 'statut': statut,
                'victoire_observee': bool(victoire), 'issue_predite': attendue,
                'differences': [{'y': int(y), 'x': int(x), 'predit': int(prediction[y, x]),
                                'observe': int(observation[y, x])} for y, x in positions[:64]]
                               if positions is not None else 'forme_differente'})
        result = {'statut': statut, 'plan_invalide': True, 'image_exacte': bool(juste),
                  'pixels_ecart': len(positions) if positions is not None else None,
                  'issue_predite': attendue, 'source': source, 'film_aligne': bool(film_aligne)}
        self.journal.append(result)
        return result

    def patch(self, texte_python):
        try:
            reponse = lire_reponse(texte_python, mots=self.programme.get('mots', {}))
            if 'patch' not in reponse:
                return {'statut': 'abstention'}
            patch = reponse['patch']
            if set(patch.get('retire', [])) - {r.get('nom') for r in self.programme.get('regles', [])}:
                return {'statut': 'patch_refuse', 'raison': 'regle_retiree_inconnue'}
            nouveau = appliquer_patch(self.programme, patch)
            controle, courant = self.rejouer(nouveau)
            if courant is None or not controle['catalogue_shacl']:
                return {'statut': 'patch_refuse', 'controle': controle}
            self.programme, self.modele_sha = nouveau, empreinte(nouveau)
            self.version += 1
            self.plan, self.refute = None, False
            self._verifie = None
            return {'statut': 'patch_valide_sur_observations', 'version': self.version,
                    'nouvelle_victoire_prouvee': False}
        except (ValueError, SyntaxError, KeyError, TypeError) as e:
            return {'statut': 'patch_refuse', 'raison': repr(e)}

    def dossier_ia(self):
        from chrysalide.arc3 import langage
        contrat = vers_contrats(self.perception.th_plan) if hasattr(self.perception, 'th_plan') else None
        documentation = ast.get_docstring(ast.parse(Path(langage.__file__).read_text()))
        return {'langage': 'Python declaratif Chrysalide', 'signature': self.signature(),
                'programme': vers_python(self.programme), 'contrats_theorie_origine': contrat,
                'statut_contrats': 'origine' if self.version == 1 else 'a_revalider_apres_patch',
                'semantique_native': documentation, 'perception': self.description_perception(),
                'film_dernier_coup': self.films.analyser(-1) if self.films.entrees else {'statut': 'film_absent'},
                'contre_exemples': copy.deepcopy(self.contre_exemples),
                'contrat_reponse': 'REPONSE = Reponse(patch=Patch(retire=[...], ajoute=[Regle(...)]))',
                'role_ia': 'proposer seulement ; verification deterministe obligatoire'}

    def dossier_lecon(self):
        """Contrat effectivement lisible pour le proposeur, dans la langue existante."""
        exemple = Path(__file__).with_name('exemple_lecon.py').read_text()
        return {'langage': 'Python declaratif Chrysalide', 'signature': self.signature(),
                'programme_courant': vers_python(self.programme), 'exemple_lisible': exemple,
                'classification': self.classifier(),
                'reponse_attendue': 'LECON = Lecon(...) ; statut propose uniquement',
                'parametres': 'Liaisons fournies separement pour chaque scene ; param("nom") dans les expressions',
                'extensions': 'mots=Mot(...) et regles=Regle(...) ; memes interpretes et compilateur',
                'verification': 'rejeu, precondition puis plan simule ; aucune action autorisee par cette interface'}

    def evaluer_lecon(self, texte, valeurs, secondes=.2):
        from chrysalide.arc3.langage import ErreurLangage
        if __package__:
            from .lecons_python import LeconPython
        else:
            from lecons_python import LeconPython
        try:
            return LeconPython(texte).evaluer_strategie(self, valeurs, secondes)
        except (ErreurLangage, ValueError, SyntaxError, TypeError, KeyError, IndexError, ArithmeticError) as e:
            return {'statut': 'lecon_refusee', 'raison': str(e), 'droit_action': False}

    def demander_patch(self, generer, enumeration_infructueuse=False, modele='qwen3.8:27b-mlx', images=(), contexte=16384):
        if not enumeration_infructueuse:
            return {'statut': 'enumeration_deterministe_requise'}
        dossier = self.dossier_ia()
        prompt = ('Propose uniquement un patch minimal dans le Python declaratif de ce dossier, '
                  'ou REPONSE = Abstention(raison="..."). Pas de prose ni Python libre.\n'
                  + json.dumps(dossier, ensure_ascii=False, default=repr))
        options = {'images': images} if images else {}
        brut, metriques = generer(prompt, modele=modele, num_predict=1024, num_ctx=contexte, timeout=120, **options)
        texte = brut.rsplit('</think>', 1)[-1].strip()
        if texte.startswith('```python') and texte.endswith('```'):
            texte = texte[len('```python'): -3].strip()
        resultat = self.patch(texte)
        return {'statut': resultat['statut'], 'verification': resultat,
                'reponse_brute': brut, 'metriques': metriques, 'modele': modele}
