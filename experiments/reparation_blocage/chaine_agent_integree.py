"""Boucle commune de modèles révisables ; aucune identité de jeu dans les décisions."""

import copy
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

import numpy as np
from acquisition_prefixe import description as decrire_acquisition
from acquisition_prefixe import proposer as proposer_acquisition
from boucle_roles_autonome import comparer
from boucle_roles_autonome import decider as decider_existant
from buts_identites import programmes as programmes_identites
from chaine_coherente import Chaine
from classification_prefixe import information_film
from controleur_experimentation import Controleur, Dossier
from freinage_passif import candidats as candidats_freinage
from objets_variables import ObjetsVariables
from perception_guidee import proposer_calques
from plan_selection_dynamique import chercher
from roles_observes import PerceptionRoles
from selection_observee import SelectionObservee

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.plan_langage import cle_complete
from chrysalide.arc3.moteur import NOMS


def canon(a):
    return ("MOUSE", a[2], a[1]) if isinstance(a, list) else (NOMS[a],)


def sdk(a):
    return ["clic", int(a[2]), int(a[1])] if a[0] == "MOUSE" else next(k for k, v in NOMS.items() if v == a[0])


def lots(actions):
    return [
        {"actions": [{"action": a[0], **({"row": a[1], "col": a[2]} if a[0] == "MOUSE" else {})}]} for a in map(canon, actions)
    ]


def key(image, action):
    return hashlib.sha256(np.asarray(image[:-1]).tobytes() + json.dumps(action).encode()).hexdigest()


class AgentIntegre:
    def __init__(self, images, actions, films, issues, limite=80, reparation=True, decouverte_courte=False, legacy_sans_but=False, utilite_sondes=False, exploration_p1=False, routage_classes=False, dreamcoder_mots=False, recherche_briques="off", aiguillage_provisoire=False, revision_solidite=False, revision_projection=False, couverture_commandes=False, graine_exploration=0, boucle_reparation=False, budget_sondes_reparation=3):
        self.images = [np.array(g) for g in images]
        self.actions = list(actions)
        self.films = list(films)
        self.issues = list(issues)
        self.limite = limite
        self.reparation = reparation
        self.boucle_reparation = bool(boucle_reparation)
        if budget_sondes_reparation < 0:
            raise ValueError("Budget de sondes négatif")
        self.budget_sondes_reparation = budget_sondes_reparation
        self.sondes_reparation_emises = 0
        self.decouverte_courte = decouverte_courte
        self.legacy_sans_but = legacy_sans_but
        self.utilite_sondes = utilite_sondes
        self.memoire_episodes = []
        self.graine_exploration = graine_exploration
        self.exploration_p1 = exploration_p1
        self.couverture_commandes = couverture_commandes
        self.sondes_contexte = []
        self.commandes_connues = set()
        self.modele_gagnant = None
        self.precedents = []
        self.theorie_precedente = None
        self.revision_projection = revision_projection
        self.revision_solidite = revision_solidite or revision_projection
        self.aiguillage_provisoire = aiguillage_provisoire
        self.routage_classes = routage_classes or aiguillage_provisoire
        self.dreamcoder_mots = dreamcoder_mots
        self.recherche_briques = recherche_briques
        self.routage_exhaustif = False
        self.capacites_differees = False
        self.releves_p1 = set()
        self.recherche_buts_en_attente = False
        self.chaines = {}
        self.journal = []
        self.revisions = 0
        self.vus = {key(g, a) for g, a in zip(self.images, self.actions)}
        self.reconstruction = True
        self.attente = None
        self.memoire_jeu = None
        self.transfert_empreintes = None
        self.diagnostic_transfert = None
        self.debut_contexte = 0
        self.sondes_inertes = 0

    def installer_modele_jeu(self, modele):
        if self.actions or self.attente is not None:
            raise ValueError("Réaffectation attendue au début d'un niveau")
        modele.installer(self)

    def consolider_modele_jeu(self, nom, provenance):
        from modele_jeu import ModeleJeu
        c = self.chaines[nom]
        from diagnostic_contexte_transfert import contexte_source
        return ModeleJeu("objets", (copy.deepcopy(c.perception), copy.deepcopy(c.programme)), provenance,
                         contexte_selection=contexte_source(self.images),
                         commandes_observees=set(self.commandes_connues) |
                             {a for a in self.actions if isinstance(a, int)})

    def _chaine(self, vue, programme):
        if self.dreamcoder_mots:
            from dreamcoder_mots import appliquer
            bibliotheque = json.loads((Path(__file__).parent / 'dreamcoder_bibliotheque.json').read_text())
            programme, preuve = appliquer(programme, bibliotheque)
            self.journal.append({'type':'bibliotheque_dreamcoder', **preuve})
        c = Chaine(
            vue,
            programme,
            [g.tolist() for g in self.images[self.debut_contexte:]],
            lots(self.actions[self.debut_contexte:]),
            [(NOMS[k],) for k in range(1, 5)],
            coups_deja_joues=len(self.actions),
            reserve=self.limite,
            films=self.films[self.debut_contexte:],
        )
        c.activer_atms()
        return c

    def _admettre(self, name, c):
        check, state = c.rejouer()
        self.journal.append({"type": "admission", "nom": name, "controle": check})
        if state is not None and check["catalogue_shacl"]:
            self.chaines[name] = c

    def reconstruire(self):
        self.reconstruction = False
        # Les capacités sont essayées puis vérifiées contre TOUT le préfixe ; un clic ne choisit pas à lui seul la famille.
        specs = [
            (
                "objets",
                lambda: ObjetsVariables(self.images, self.actions, clics_negatifs=self.decouverte_courte, films=self.films),
            ),
            (
                "objets_contact",
                lambda: ObjetsVariables(
                    self.images, self.actions, contact=True, clics_negatifs=self.decouverte_courte, films=self.films
                ),
            ),
            (
                "roles",
                lambda: PerceptionRoles(self.images, self.actions, clics_negatifs=self.decouverte_courte, films=self.films),
            ),
        ]
        if any(isinstance(a, list) for a in self.actions):
            specs += [
                (
                    f"selection_{mode}",
                    lambda mode=mode: SelectionObservee(
                        self.images, self.actions, contact=mode, films=self.films, clics_negatifs=self.decouverte_courte
                    ),
                )
                for mode in ("aucun", "pas", "glisse", "sortie")
            ]
        route = None
        if self.routage_classes and (self.aiguillage_provisoire or not self.routage_exhaustif):
            from classification_prefixe import classifier
            from ontologie_extensible import priorites_capacites
            route = priorites_capacites(classifier(self.images, self.actions, self.films), [n for n,_ in specs])
            self.journal.append({'type':'routage_ontologie', **route,
                'classifications_provisoires':self.aiguillage_provisoire,
                'voie_inconnue':'p1_graphe_observe' if self.exploration_p1 else None,
                'exclusion_par_priorite':False if self.aiguillage_provisoire else None})
            ordre = route['prioritaires'] + route['secondaires']
            specs.sort(key=lambda item: ordre.index(item[0]))
        for name, factory in specs:
            if not self.aiguillage_provisoire and route and route['prioritaires'] and name in route['secondaires'] and any(
                    not n.startswith('perception_sans_but') for n in self.chaines):
                self.capacites_differees = True
                self.journal.append({'type':'capacites_differees', 'noms':route['secondaires'],
                    'admissions':{n:c.classifier() for n,c in self.chaines.items()}})
                break
            try:
                v = factory()
                if self.decouverte_courte and isinstance(v, PerceptionRoles):
                    self._admettre("perception_sans_but_roles", self._chaine(v, v.programme()))
                programmes = [v.programme()] if isinstance(v, SelectionObservee) else [v.programme(b) for b in v.buts[:3]]
                for i, p in enumerate(programmes):
                    self._admettre(f"{name}_{i}", self._chaine(v, p))
            except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
                self.journal.append({"type": "capacite_non_applicable", "nom": name, "raison": repr(exc)})

        if (any(isinstance(a, list) for a in self.actions) or any(f is not None and len(f)>=3 for f in self.films)) and not self.capacites_differees:
            try:
                for name, vue in candidats_freinage(self.images, self.actions, self.films, clics_negatifs=self.decouverte_courte, sans_clic=True):
                    self._admettre(name, self._chaine(vue, vue.programme()))
            except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
                self.journal.append({"type": "capacite_non_applicable", "nom": "freinage_passif", "raison": repr(exc)})

        if not self.chaines:
            try:
                from perception_silhouette_atlas import SilhouetteAtlas
                vue=SilhouetteAtlas(self.images,self.actions)
                c=self._chaine(vue,vue.programme());c.but_inconnu=True
                self._admettre('silhouette_atlas',c)
                self.journal.append({'type':'silhouette_atlas_observe','preuves':vue.preuves,
                    'contradictions_statiques':vue.contradictions_statiques,
                    'admis':'silhouette_atlas' in self.chaines,'but_inconnu':True})
            except (ValueError,KeyError,TypeError,IndexError,RuntimeError) as exc:
                self.journal.append({'type':'capacite_non_applicable','nom':'silhouette_atlas','raison':repr(exc)})

        # La capacité plus large ne remplace pas les voies déjà admises.
        if not any(not name.startswith("perception_sans_but") for name in self.chaines):
            try:
                vue = ObjetsVariables(
                    self.images,
                    self.actions,
                    identites_temporelles=True,
                    jauge_validee=True,
                    clics_negatifs=self.decouverte_courte,
                    films=self.films,
                )
                self._admettre("perception_sans_but_identites", self._chaine(vue, vue.programme()))
                if "perception_sans_but_identites" in self.chaines:
                    for name, p in programmes_identites(vue, self.images[0]):
                        self._admettre("but_identites_" + name, self._chaine(vue, p))
            except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
                self.journal.append({"type": "capacite_non_applicable", "nom": "identites_jauge", "raison": repr(exc)})

        if self.legacy_sans_but and (self.aiguillage_provisoire or not self.chaines) and self.actions:
            from perception_echelles import proposer as proposer_echelles
            try:
                candidates, rapport = proposer_echelles({'grilles': [g.tolist() for g in self.images],
                    'lots': lots(self.actions), 'films': self.films}, secondes=2)
                for diagnostic in rapport['candidats']:
                    self.journal.append({'type': 'representation_legacy', **diagnostic})
                self.journal.append({'type': 'perception_echelles', **rapport})
                for nom, c in candidates:
                    c.limite = self.limite
                    c.activer_atms()
                    self._admettre('perception_sans_but_' + nom, c)
            except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
                self.journal.append({'type': 'capacite_non_applicable', 'nom': 'legacy_sans_but', 'raison': repr(exc)})

        if self.routage_classes and (self.aiguillage_provisoire or not self.chaines) and self.actions:
            from classification_prefixe import classifier
            from perception_routee import proposer
            description=classifier(self.images,self.actions,self.films)
            try:
                candidates,report=proposer(description,{'grilles':[g.tolist() for g in self.images],
                    'lots':lots(self.actions),'films':self.films},
                    toutes=self.aiguillage_provisoire)
                self.journal.append({'type':'perception_routee',**report})
                for name,c in candidates:
                    c.activer_atms()
                    self._admettre('perception_sans_but_'+name,c)
            except (ValueError,KeyError,RuntimeError) as exc:
                self.journal.append({'type':'perception_routee_refusee','raison':repr(exc)})

    def _suivre_experience(self, result):
        """Une sonde choisie hors solveur teste aussi les modèles déjà admis."""
        if not result.get('actions'):return
        action=canon(result['actions'][0])
        predictions=[]
        for name,c in self.chaines.items():
            p=self._predire(c,action)
            if p is None:continue
            c.plan={"actions":[list(action)],**c.signature(),"origine":"experience_p1_observee"}
            c._tracer_plan()
            predictions.append({"nom":name,**p})
        if predictions:
            result['modeles']=[p['nom'] for p in predictions]
            result['predictions']=[predictions]

    def _choisir_sonde_utile(self, dossier, candidates):
        # Comparer des observables de même portée, pas des rendus d'échelles différentes.
        espaces = [c.description_perception() for c in self.chaines.values()]
        if not espaces or any(e != espaces[0] for e in espaces[1:]):
            return None, {'refus': 'espaces_observables_non_alignes', 'obligations': []}
        experiences = []
        index = {}
        for i, candidate in enumerate(candidates):
            _, owner, action = candidate
            predictions = {n: self._predire(c, action) for n, c in self.chaines.items()}
            if any(p is None or p['issue'] == 'defaite' for p in predictions.values()):
                continue
            ident = str(i)
            index[ident] = candidate
            experiences.append({'id': ident, 'predictions': {
                n: {'image':p['image'], 'issue':p['issue'] or 'continue'}
                for n,p in predictions.items()},
                'cout_actions': 1, 'cout_acces': 0, 'accessible': True, 'risque': 'inconnu'})
        diagnostic = Controleur().choisir_experience(dossier, list(self.chaines), experiences)
        diagnostic['obligations'] = []  # aucune obligation nouvelle n'est déduite d'un effet non nul
        choix = diagnostic['choix']
        return index[choix['id']] if choix else None, diagnostic

    def _cle_sonde_revision(self, c, action, nouveau, ancien):
        from chrysalide.arc3.logique.plan_langage import _gel
        _, courant = c.rejouer()
        if courant is None:
            return None
        pc, scene = courant
        # Valeurs stables entre processus/snapshots : pas le hash Python de cle_complete.
        etat = (sorted((_gel(o) for o in scene.sprites), key=repr),
                scene.camera, getattr(scene, 'canevas', None),
                getattr(scene, 'donnees', None), scene.issue, pc.etat,
                getattr(pc, 'instantanes', None))
        question = (c.modele_sha, c.contraste_revision, c.description_perception(),
                    c.perception.vue(self.images[-1]), etat, action,
                    (nouveau['image'], nouveau.get('issue')),
                    (ancien['image'], ancien.get('issue')))
        return hashlib.sha256(repr(_gel(question)).encode()).hexdigest()

    def _sonder_revision(self, offre):
        if getattr(self, 'boucle_reparation', False):
            if self.attente is not None:
                raise ValueError("Observation requise avant prochaine décision")
            if self.sondes_reparation_emises >= self.budget_sondes_reparation:
                return None
        from revision_solidite import predire_contraste
        experiences=[];index={}
        for nom,c in self.chaines.items():
            if not hasattr(c,'contraste_revision'):continue
            codes = (1,2,3,4,5) if getattr(self, 'boucle_reparation', False) else (1,2,3,4)
            actions = [canon(code) for code in offre if code in codes]
            if getattr(self, 'boucle_reparation', False) and 6 in offre and hasattr(c, 'perception'):
                from buts_modele_conserve import actions_modele
                # Les clics viennent du même modèle admis que la planification.
                # Ni RESET ni UNDO, ni coordonnées inventées pour une sonde.
                actions += [a for a in actions_modele(c, [6])
                            if len(a) == 3 and a[0] == 'MOUSE'
                            and all(isinstance(v, (int, np.integer)) and 0 <= v < 64 for v in a[1:])]
            for action in dict.fromkeys(actions):
                code=sdk(action)
                nouveau=self._predire(c,action);ancien=predire_contraste(c,action)
                if nouveau is None or ancien is None or nouveau['issue']=='defaite':continue
                question=self._cle_sonde_revision(c,action,nouveau,ancien)
                if question is None or question in getattr(self,'sondes_revision_resolues',set()):continue
                ident=str(len(index));index[ident]=(nom,code,question)
                experiences.append({'id':ident,'predictions':{
                    'corrige':{'image':nouveau['image'],'issue':nouveau.get('issue') or 'continue'},
                    'ancienne_loi_refutee':{'image':ancien['image'],'issue':ancien.get('issue') or 'continue'}},
                    'cout_actions':1,'cout_acces':0,'accessible':True,'risque':'inconnu'})
        if not experiences:return None
        diagnostic=Controleur().choisir_experience(self.dossier(offre),
            ['corrige','ancienne_loi_refutee'],experiences)
        diagnostic['portee']='tester consequence nouvelle de revision ; ancienne loi deja refutee'
        self.journal.append({'type':'sonde_revision',**diagnostic})
        if not diagnostic['choix']:return None
        nom,code,question=index[diagnostic['choix']['id']]
        result={'statut':'experience_revision','origine':'consequence_revision',
            'actions':[code],'predictions':[[]],'modele_revision':nom,'question_revision':question,
            'risque':'inconnu','but':'inconnu','diagnostic':diagnostic}
        self._suivre_experience(result)
        if getattr(self, 'boucle_reparation', False):
            self.sondes_reparation_emises += 1
            result['prefixe_sha256'] = self.dossier(offre).signature()
            self.journal.append({'type':'boucle_reparation_decision',
                'question':question, 'prefixe_sha256':result['prefixe_sha256'],
                'action':code, 'modele':nom,
                'sondes_emises':self.sondes_reparation_emises,
                'budget_sondes':self.budget_sondes_reparation})
        self.attente=result
        return result

    def dossier(self, offre):
        return Dossier(
            self.images, self.actions, self.films, self.issues, len(self.actions), self.limite - len(self.actions), tuple(offre)
        )

    def _predire(self, c, action):
        _check, current = c.rejouer()
        if current is None:
            return None
        pc, sc = current
        pi = Programme(c.programme)
        pi.etat = copy.deepcopy(pc.etat)
        si = copy.deepcopy(sc)
        pc.step(sc, action)
        pi.step(si, action)
        if cle_complete(sc, pc.etat) != cle_complete(si, pi.etat):
            return None
        return {
            "image": c.perception.rendu(sc).tolist(),
            "fin": sc.issue in ("niveau", "victoire"),
            "issue": sc.issue,
            "hud": sorted(map(list, getattr(c.perception, "hud", getattr(getattr(c.perception, "base", None), "hud", [])))),
        }

    def _buts_en_attente(self):
        if hasattr(self, "recherche_buts_en_attente"):
            return self.recherche_buts_en_attente
        # Ancien snapshot : seules les admissions postérieures à la dernière
        # recherche justifient une reprise ; les tranches restent intactes.
        nouveaux = set()
        for entree in reversed(self.journal):
            if entree.get("type") == "buts_modele_conserve":
                return any(n in self.chaines and not self.chaines[n].refute for n in nouveaux)
            if entree.get("type") == "admission" and entree.get("controle", {}).get("catalogue_shacl"):
                nouveaux.add(entree.get("nom"))
        return False

    def _relever_p1(self, secondes, offre=(1, 2, 3, 4)):
        """Chercheur de buts existant, une fois par tranche de huit observations."""
        debut_releve = time.monotonic()
        tranche = len(self.actions) // 8
        en_attente = self._buts_en_attente()
        if secondes <= 0 or (not en_attente and
                ((not tranche and not self.chaines) or tranche in self.releves_p1)):
            return
        self.recherche_buts_en_attente = False
        self.releves_p1.add(tranche)
        from buts_modele_conserve import chercher, actions_modele
        nouveau, essais = chercher(self.chaines,
            lambda c: actions_modele(c, offre), secondes=secondes,
            accepter=lambda act: key(self.images[-1], sdk(act)) not in self.vus,
            but_prioritaire=getattr(self.theorie_precedente, 'but', None), processus=2)
        self.journal.append({'type':'buts_modele_conserve', 'coup':len(self.actions),
                             'essais':essais, 'plan_trouve':nouveau is not None})
        if nouveau is not None:
            self.chaines['p1_but_hypothese'] = nouveau
            return
        if en_attente:
            return  # Une seule reprise sur les nouveaux modèles, sans réinduction.
        from chrysalide.arc3.moteur import MoteurC
        restant = secondes - (time.monotonic() - debut_releve)
        if restant <= 0:
            return
        m = MoteurC(budget=restant, limite_plan=5000,
                    theorie_precedente=self.theorie_precedente)
        r = m.proposer({'grilles':[g.tolist() for g in self.images],
            'lots':lots(self.actions), 'films':self.films, 'precedents':self.precedents})
        self.journal.append({'type':'releve_p1', 'coup':len(self.actions), 'infos':m.infos})
        if r is None:
            # Une perception alternative peut expliquer les clics sans connaître le but.
            from perception_clics_couples import proposer
            for i, candidat in enumerate(proposer(self.images, lots(self.actions), self.films,
                                                  prior=self.theorie_precedente)):
                nom = f'perception_clics/{i}'
                self._admettre(nom, candidat)
                if self.chaines.get(nom) is candidat:
                    self.recherche_buts_en_attente = True
            return
        plan, programme = r
        c = self._chaine(m, programme)
        c.actions = [(x['action'], x['row'], x['col']) if x['action']=='MOUSE'
                     else (x['action'],) for x in plan]
        check, state = c.rejouer()
        if state is None or not all(check.get(k) for k in
                ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
            self.journal.append({'type':'releve_p1_refuse', 'controle':check})
            return
        adoption = c.adopter_plan(c.actions, origine='MoteurC_but_hypothese')
        if adoption['statut'] == 'plan_simule_valide':
            self.chaines['p1_but_hypothese'] = c

    def decider(self, offre, sortie=None, source=None, secondes=30):
        debut = time.monotonic()
        if (self.decouverte_courte or getattr(self, 'boucle_reparation', False)) and self.attente is not None:
            raise ValueError("Observation requise avant prochaine décision")
        if len(self.actions) >= self.limite or (self.issues and self.issues[-1] != "continue"):
            return {"statut": "fin_ou_budget", "actions": []}
        composition_installee = False
        if getattr(self, 'composition_contextuelle_auto', False):
            from orchestration_contextes import orchestrer
            composition_installee = orchestrer(self, max(0., secondes-(time.monotonic()-debut)))['installe']
        if self.couverture_commandes and self.sondes_contexte:
            while self.sondes_contexte:
                code=self.sondes_contexte.pop(0)
                if code not in offre:continue
                result={'statut':'experience_contexte_commande',
                    'origine':'directions_apres_changement_commande','actions':[code],
                    'predictions':[[]],'risque':'inconnu','but':'inconnu'}
                self._suivre_experience(result);self.attente=result
                return result
        if self.couverture_commandes:
            essayees={a for a in self.actions if isinstance(a,int)} | self.commandes_connues
            manquantes=[a for a in offre if a in (1,2,3,4,5,7) and a not in essayees]
            if manquantes:
                result={'statut':'experience_commande','origine':'commande_offerte_non_testee',
                    'actions':[manquantes[0]],'predictions':[[]],'risque':'inconnu','but':'inconnu'}
                self._suivre_experience(result)
                self.attente=result
                self.journal.append({'type':'couverture_commandes','essayees':sorted(essayees),
                                     'manquantes':manquantes,'action':manquantes[0]})
                return result
        if self.diagnostic_transfert is not None:
            if self.diagnostic_transfert.get("contrat_candidat")!="selection_marqueur":
                return {"statut":"diagnostic_transfert_non_resolu","actions":[],"diagnostic":self.diagnostic_transfert}
            # Seules les commandes sans déplacement appris sont candidates au changement de sélection.
            source=self.memoire_jeu.acquis[0]
            while hasattr(source,'base'):source=source.base
            candidates=[a for a in offre if a!=0 and a!=6 and all(ms.get(a)==(0,0) for ms in source.mouvements.values())
                        and key(self.images[-1],a) not in self.vus]
            if not candidates:return {"statut":"contexte_selection_non_resolu","actions":[],"diagnostic":self.diagnostic_transfert}
            self.attente={"statut":"experience_contrat_selection","actions":[candidates[0]],
                          "hypotheses":["marqueur_change_hote","marqueur_inchange"],"diagnostic":self.diagnostic_transfert}
            return self.attente
        if self.transfert_empreintes is not None:
            from transfert_empreintes import planifier
            m,instance=self.transfert_empreintes
            rapport,plan=planifier(m,instance,self.images,self.films)
            if not plan:return {"statut":"transfert_sans_plan","actions":[],"rapport":rapport}
            a=plan[0]
            if (6 if isinstance(a,list) else a) not in offre:raise ValueError("Action transférée indisponible")
            self.attente={"statut":"transfert_empreintes","actions":[a],"rapport":rapport}
            return self.attente
        plan_en_cours = any(c.plan and not c.refute and
                            c.verifier_plan(c.plan['actions'])[0]
                            for c in self.chaines.values())
        if (self.reconstruction and not plan_en_cours and
                not self._buts_en_attente()):
            self.reconstruire()
        from buts_roles_herites import admettre as admettre_buts_roles
        if not plan_en_cours:
            admettre_buts_roles(self, max(0., secondes-(time.monotonic()-debut)))
        buts_roles_installes = any(not c.refute and hasattr(c, 'preuve_but_elargi')
                                   for c in self.chaines.values())
        if self.utilite_sondes and not plan_en_cours and not buts_roles_installes:
            from sonde_roles_non_couverts import proposer as sonder_roles
            for nom, chaine in self.chaines.items():
                if not getattr(chaine, 'but_inconnu', False):
                    continue
                experience, diag_roles = sonder_roles(chaine, self.images, self.actions, offre,
                    getattr(self, 'observations_episodes', ()))
                self.journal.append({'type':'sonde_roles_non_couverts', 'modele':nom, **diag_roles})
                if experience is not None:
                    self._suivre_experience(experience)
                    self.attente = experience
                    return experience
        # Une conséquence nouvelle de la réparation peut être testée avant
        # qu'une hypothèse de but reconstruite ne masque cette expérience.
        # Les plans déjà validés et les sondes de rôles gardent leur priorité.
        if ((getattr(self, "boucle_reparation", False) or
                 os.environ.get("CHRYS_SONDE_REVISION_PRIORITAIRE", "0") == "1")
                and self.revision_solidite and not plan_en_cours
                and not composition_installee and not buts_roles_installes):
            sonde = self._sonder_revision(offre)
            if sonde is not None:
                return sonde
        if self.exploration_p1 and not plan_en_cours and not composition_installee and not buts_roles_installes:
            self._relever_p1(max(0., secondes - (time.monotonic() - debut)), offre)
            plan_en_cours = any(c.plan and not c.refute and
                                c.verifier_plan(c.plan["actions"])[0]
                                for c in self.chaines.values())
        if self.utilite_sondes and not plan_en_cours and not composition_installee:
            from sondes_portefeuille import proposer
            experience = proposer(self, offre)
            if experience is not None:
                return experience
        dossier = self.dossier(offre)
        # Diagnostic neuf par préfixe : les anciens nogoods de couverture ne contaminent pas un nouveau contexte.
        diagnostic = Controleur().decider(
            dossier,
            chaines={},
            couverture={
                "perception": "compatible" if self.chaines else "inconnue",
                "mouvement": "compatible" if self.chaines else "inconnue",
                "contact": "inconnue",
                "issues": "inconnue",
            },
        )
        acquisition = decrire_acquisition(dossier, self.chaines) if self.decouverte_courte else None
        if acquisition is not None:
            self.journal.append({"type": "acquisition_prefixe", **acquisition})
        proposed = []
        candidats = list(self.chaines.items())
        if self.recherche_briques == "dreamcoder":
            from dreamcoder_mots import appliquer
            bibliotheque = json.loads((Path(__file__).parent / 'dreamcoder_bibliotheque.json').read_text())
            scores = {}
            for name, c in candidats:
                _, preuve = appliquer(c.programme, bibliotheque)
                scores[name] = preuve['noeuds_total_apres']
            candidats.sort(key=lambda nc: scores[nc[0]])
            self.journal.append({'type':'priorite_recherche_dreamcoder', 'scores':scores,
                                 'ordre':[n for n,c in candidats]})
        recherches = []
        echecs_budget = {}
        for passage_composition in range(2):
            for name, c in candidats:
                if name.startswith("perception_sans_but"):
                    continue
                if time.monotonic() - debut >= secondes:
                    break
                recherches.append(name)
                plan = ({"statut":"plan_simule_valide", "plan":c.plan} if c.plan and not c.refute else
                    c.proposer(secondes=min(0.5, max(0.01, secondes - (time.monotonic() - debut)))))
                if getattr(self, 'composition_contextuelle_auto', False):
                    from orchestration_contextes import enregistrer_epuisement
                    enregistrer_epuisement(self, name, c, plan)
                if plan["statut"] != "plan_simule_valide" and isinstance(c.perception, SelectionObservee):
                    disponible = max(0.01, secondes - (time.monotonic() - debut))
                    part = disponible / max(1, len(candidats) - len(recherches) + 1)
                    seq, _infos = chercher(
                        c, c.perception, secondes=part, max_noeuds=100000, poids_heuristique=3
                    )
                    self.journal.append({'type':'recherche_selection','modele':name,
                        'budget_s':part,'poids_heuristique':3,'optimalite_non_garantie':True,**_infos})
                    if seq is not None:
                        plan = c.adopter_plan(seq, origine="selection_dynamique_existante")
                    elif _infos.get('refus') == 'budget' and getattr(self, 'recherche_prolongee', False):
                        from recherche_selection_prolongee import signature_recherche
                        echecs_budget[name] = {'refus':'budget', 'signature':signature_recherche(c, offre)}
                if plan["statut"] == "plan_simule_valide" and plan["plan"]["actions"]:
                    seq = plan["plan"]["actions"]
                    a = sdk(seq[0])
                    if (6 if isinstance(a, list) else a) in offre and key(self.images[-1], a) not in self.vus:
                        proposed.append((len(seq), name, tuple(seq[0])))
                        if self.recherche_briques != "off":
                            predictions = [self._predire(other, tuple(seq[0])) for other in self.chaines.values()]
                            if all(p is not None and p['issue'] != 'defaite' for p in predictions):
                                break
            if proposed or passage_composition or not getattr(self, 'composition_contextuelle_auto', False):
                break
            from orchestration_contextes import orchestrer
            nouvelle_composition = orchestrer(self, max(0., secondes-(time.monotonic()-debut)))
            if not nouvelle_composition['installe']:
                break
            composition_installee = True
            candidats = list(self.chaines.items())
            echecs_budget = {}
        if not proposed and echecs_budget and getattr(self, 'recherche_prolongee', False):
            from recherche_selection_prolongee import prolonger
            reprise = prolonger(self, offre, echecs_budget)
            if reprise.get('statut') == 'plan_simule_valide':
                name = reprise['modele']
                c = self.chaines[name]
                seq = c.plan['actions']
                if seq:
                    a = sdk(seq[0])
                    if (6 if isinstance(a, list) else a) in offre and key(self.images[-1], a) not in self.vus:
                        proposed.append((len(seq), name, tuple(seq[0])))
        if self.recherche_briques != "off":
            self.journal.append({'type':'recherche_briques', 'mode':self.recherche_briques,
                                 'modeles_explores':recherches, 'plans':len(proposed)})
        if not proposed and self.capacites_differees:
            self.capacites_differees = False
            self.routage_exhaustif = True
            self.reconstruction = True
            self.journal.append({'type':'routage_reouvert', 'raison':'aucun_plan_admis'})
            return self.decider(offre, sortie, source, max(.01, secondes-(time.monotonic()-debut)))
        if not proposed:
            for name, c in self.chaines.items():
                if name != "perception_sans_but_identites":
                    continue
                for code in offre:
                    if code not in (1, 2, 3, 4) or key(self.images[-1], code) in self.vus:
                        continue
                    prediction = self._predire(c, canon(code))
                    if prediction is not None and not np.array_equal(
                        np.asarray(prediction["image"]), c.perception.vue(self.images[-1])
                    ):
                        proposed.append((1, name, canon(code)))
        if not proposed and 'perception_sans_but_legacy' in self.chaines and 6 in offre:
            from representation_legacy_sans_but import clics_etayes
            c = self.chaines['perception_sans_but_legacy']
            for a in clics_etayes(c):
                if not (0 <= a[1] < 64 and 0 <= a[2] < 64) or key(self.images[-1], a) in self.vus:
                    continue
                prediction = self._predire(c, canon(a))
                if prediction is not None and not np.array_equal(np.asarray(prediction['image']), c.perception.vue(self.images[-1])):
                    proposed.append((1, 'perception_sans_but_legacy', canon(a)))
        utilite = None
        if (self.utilite_sondes or self.exploration_p1) and proposed and all(p[1].startswith('perception_sans_but') for p in proposed):
            choix, utilite = self._choisir_sonde_utile(dossier, proposed)
            self.journal.append({'type': 'utilite_sondes', **utilite})
            if choix is None and not self.exploration_p1:
                return {'statut': 'but_ou_experience_non_couvert', 'actions': [],
                    'modeles': list(self.chaines), 'utilite': utilite,
                    'coups_deja_payes': len(self.actions), 'victoire': False}
            proposed = [choix] if choix is not None else []
        for _, owner, action in sorted(proposed):
            predictions = {n: self._predire(c, action) for n, c in self.chaines.items()}
            if any(p is None or p["issue"] == "defaite" for p in predictions.values()):
                continue
            plan_owner = self.chaines[owner].plan
            suite_plan = (copy.deepcopy(plan_owner["actions"][1:])
                if plan_owner and tuple(plan_owner["actions"][0]) == action else [])
            for c in self.chaines.values():
                c.plan = {"actions": [list(action)], **c.signature(), "origine": "experience_un_coup_conditionnelle"}
                c._tracer_plan()
            result = {
                "statut": "action_conditionnelle",
                "actions": [sdk(action)],
                "predictions": [[{"nom": n, **p} for n, p in predictions.items()]],
                "modele_plan": owner,
                "suite_plan": suite_plan,
                "but": "absent_experience" if owner.startswith("perception_sans_but") else "hypothese_non_prouvee",
                "risque": "conditionnel_aux_modeles_partiels",
                "diagnostic_arbitre": diagnostic,
                "prefixe_sha256": dossier.signature(),
                "modeles": list(self.chaines),
            }
            if utilite is not None:
                result["utilite"] = utilite
            if acquisition is not None:
                result["acquisition"] = acquisition
            self.attente = result
            return result
        if self.revision_solidite:
            sonde=self._sonder_revision(offre)
            if sonde is not None:return sonde
        if self.exploration_p1:
            from relation_clic_observee import proposer_agent as proposer_relation_clic
            result = proposer_relation_clic(self, offre)
            if result is not None:
                result['prefixe_sha256'] = dossier.signature()
                self._suivre_experience(result)
                self.attente = result
                return result
            from selection_visuelle_immobile import proposer as proposer_selection_visuelle
            result = proposer_selection_visuelle(self.images, self.actions, self.films, self.issues, offre)
            if result is not None:
                result['prefixe_sha256'] = dossier.signature()
                self._suivre_experience(result)
                self.attente = result
                return result
            from exploration_p1_prefixe import proposer
            memoire=getattr(self, "memoire_episodes", ())
            anciens=getattr(self, "observations_episodes", ())
            options={}
            if memoire:options['memoire_episodes']=memoire
            if anciens:options['observations_episodes']=anciens
            result = proposer(self.images, self.actions, self.issues, offre,
                graine=getattr(self, "graine_exploration", 0), **options)
            if result is None:
                return {'statut':'frontieres_observees_epuisees', 'actions':[]}
            result['prefixe_sha256'] = dossier.signature()
            self._suivre_experience(result)
            self.attente = result
            return result
        if self.decouverte_courte:
            non_essayees = acquisition["questions_couvertes"]["commandes_non_essayees"]
            if self.sondes_inertes >= 3 and not non_essayees:
                return {"statut": "trois_films_inertes", "actions": [], "acquisition": acquisition}
            exp = proposer_acquisition(dossier, acquisition, self.chaines)
            if exp is not None:
                result = {
                    **exp,
                    "statut": "experience_conditionnelle",
                    "diagnostic_arbitre": diagnostic,
                    "prefixe_sha256": dossier.signature(),
                    "modeles": [],
                    "acquisition": acquisition,
                }
                self.attente = result
                return result
            return {"statut": "aucune_experience_nouvelle", "actions": [], "acquisition": acquisition}
        if self.sondes_inertes >= 3:
            return {"statut": "trois_sondes_inertes", "actions": [], "diagnostic_arbitre": diagnostic}
        if sortie is not None and source is not None:
            clean = Path(sortie) / "observations"
            shutil.copyfile(Path(source).with_suffix(".npz"), clean.with_suffix(".npz"))
            clean.with_suffix(".json").write_text(json.dumps({"rows": [{"action": a} for a in self.actions]}))
            exp = decider_existant(
                clean, Path(sortie) / "proposeur_existant", offre, timeout=max(0.1, secondes - (time.monotonic() - debut))
            )
            if exp is not None:
                old = json.loads(exp.read_text())
                a = old["actions"][0]
                if key(self.images[-1], a) not in self.vus:
                    result = {
                        **old,
                        "statut": "experience_conditionnelle",
                        "actions": [a],
                        "predictions": old["predictions"][:1],
                        "diagnostic_arbitre": diagnostic,
                        "prefixe_sha256": dossier.signature(),
                        "risque": "inconnu",
                        "modeles": [],
                    }
                    self.attente = result
                    return result
        return {"statut": "aucune_action_nouvelle", "actions": [], "diagnostic_arbitre": diagnostic}

    def observer(self, action, image, film, issue, *, source="jeu"):
        if self.attente is None or action != self.attente["actions"][0]:
            raise ValueError("Action sans décision prospective")
        if self.decouverte_courte and (not len(film) or not np.array_equal(np.asarray(film)[-1], image)):
            raise ValueError("Film non aligné : observation refusée")
        if (self.couverture_commandes and self.attente.get('statut')=='experience_commande'
                and action not in (1,2,3,4)
                and not np.array_equal(self.images[-1][1:-1,1:-1],np.asarray(image)[1:-1,1:-1])):
            self.sondes_contexte=[1,2,3,4]
            self.journal.append({'type':'contexte_commande_change',
                'action':action,'hypothese':'effet_sur_controle_a_tester',
                'directions_a_retester':[1,2,3,4]})
        if issue in ('niveau', 'victoire'):
            from memoire_issue_exploratoire import memoriser
            memoriser(self, canon(action), image, film, issue, source=source)
        self.vus.add(key(self.images[-1], action))
        self.images.append(np.array(image))
        self.actions.append(action)
        self.films.append(film)
        self.issues.append(issue)
        from memoire_contexte_objets import observer as observer_contexte
        reprise_contexte = observer_contexte(self, self.images[-2], image, action, issue)
        if reprise_contexte is not None:
            return reprise_contexte
        if self.attente.get("statut")=="experience_contrat_selection":
            from diagnostic_contexte_transfert import marqueurs,compatible
            before,after=marqueurs(self.images[-2]),marqueurs(image)
            record={"type":"experience_selection_observee","avant":before,"apres":after,"contexte_compatible":compatible(self.memoire_jeu,image)}
            if record['contexte_compatible']:
                # Nouveau contexte explicite, preuves et coûts anciens conservés dans cet agent.
                local=AgentIntegre([image],[],[],[],limite=self.limite-len(self.actions),reparation=self.reparation)
                try:local.installer_modele_jeu(self.memoire_jeu)
                except ValueError as exc:
                    record["reaffectation_refusee"]=str(exc);self.journal.append(record);self.attente=None
                    return record
                self.chaines=local.chaines
                self.debut_contexte=len(self.actions)
                for c in self.chaines.values():c.coups=len(self.actions);c.limite=self.limite
                self.diagnostic_transfert=None;self.reconstruction=False
                record['regles_reapprises']=0
            self.journal.append(record);self.attente=None
            return record
        if self.transfert_empreintes is not None:
            from transfert_empreintes import observer
            _,instance=self.transfert_empreintes
            terminal=issue in ("niveau","victoire")
            seen=None if terminal else observer(instance,self.images,self.films)[1]
            conforme=terminal or seen==self.attente["rapport"]["prediction_prochain_coup"]
            record={"type":"observation_transfert","conforme":conforme,"victoire":terminal,"observation":seen}
            if not conforme:
                self.transfert_empreintes=None;self.reconstruction=True
                record["retour"]="perception"
            self.journal.append(record);self.attente=None
            return record
        results = []
        anciens_modeles = list(self.chaines)
        survivors = {}
        repaired = {}
        if self.attente.get("modeles"):
            for name, c in self.chaines.items():
                if name not in self.attente['modeles']:
                    self.journal.append({'type':'modele_non_evalue','nom':name,
                        'raison':'prediction_indisponible_reconstruction_requise'})
                    self.reconstruction = True
                    continue
                r = c.observer(
                    canon(action),
                    image,
                    victoire=issue in ("niveau", "victoire"),
                    termine=issue != "continue",
                    source=source,
                    film=film,
                )
                results.append({"nom": name, **r, "atms": c.atms.rapport()})
                if r['statut'] == 'but_refute':
                    # Conserver les observations et la dynamique candidate ; le but et son plan restent réfutés.
                    stock = dict(getattr(self, 'modeles_but_refute', {}))
                    stock[name] = copy.deepcopy(c)
                    self.modeles_but_refute = stock
                    self.journal.append({'type':'modele_conserve_but_refute', 'nom':name,
                        'coup':len(self.actions), 'but_admis':False, 'plan_admis':False,
                        'portee':'rendu_de_la_transition_conforme_pas_preuve_de_completude'})
                    from revision_but_roles import proposer as reviser_but_roles
                    sans_but, diagnostic_but = reviser_but_roles(c)
                    self.journal.append({'type':'revision_but_roles', 'depuis':name, **diagnostic_but})
                    if sans_but is not None:
                        repaired['perception_sans_but_'+name] = sans_but
                    continue
                if issue == 'continue' and self.reparation and r['statut'] == 'modele_refute':
                    from revision_garde_commune import proposer as reparer_garde
                    new, diag = reparer_garde(c)
                    self.journal.append({'type':'revision_garde_commune','depuis':name,**diag})
                    if new is not None:
                        repaired[name+'/garde_commune']=new
                        continue
                    from revision_garde_face import proposer as reparer_garde_face
                    new, diag = reparer_garde_face(c)
                    self.journal.append({'type':'revision_garde_face','depuis':name,**diag})
                    if new is not None:
                        repaired[name+'/garde_face']=new
                        continue
                    from revision_faces_contact import proposer as reparer_faces
                    new, diag = reparer_faces(c)
                    self.journal.append({'type':'revision_faces_contact','depuis':name,**diag})
                    if new is not None:
                        repaired[name+'/face_contact']=new
                        continue
                    from revision_sol_revele import proposer as reparer_sol
                    new, diag = reparer_sol(c)
                    self.journal.append({'type':'revision_sol_revele','depuis':name,**diag})
                    if new is not None:
                        repaired[name+'/sol_revele']=new
                        continue
                    from revision_recouvrement_roles import proposer as reparer_recouvrement
                    new, diag = reparer_recouvrement(c)
                    self.journal.append({'type':'revision_recouvrement_roles','depuis':name,**diag})
                    if new is not None:
                        repaired[name+'/recouvrement']=new
                        continue
                    from glissade_distance_observee import proposer as reparer_distance
                    new, diag = reparer_distance(c, getattr(self,'precedents',[]))
                    self.journal.append({'type':'revision_distance_glissade','depuis':name,**diag})
                    if new is not None:
                        repaired[name+'/distance_glissade']=new
                        continue
                    from revision_poussee_chaine import proposer as reparer_poussee_chaine
                    new, diag = reparer_poussee_chaine(c)
                    self.journal.append({'type':'revision_poussee_chaine','depuis':name,**diag})
                    if new is not None:
                        repaired[name+'/poussee_chaine']=new
                        continue
                    from revision_prolongation_glisse import proposer as reparer_prolongation
                    new, diag = reparer_prolongation(c, getattr(self, 'precedents', []))
                    self.journal.append({'type':'revision_prolongation_glisse','depuis':name,**diag})
                    if new is not None:
                        repaired[name+'/prolongation_glisse']=new
                        continue
                    from revision_glissade_classe import proposer as reparer_classe_glissable
                    new, diag = reparer_classe_glissable(c, getattr(self, 'precedents', []))
                    self.journal.append({'type':'revision_classe_glissable','depuis':name,**diag})
                    if new is not None:
                        repaired[name+'/classe_glissable']=new
                        continue
                if r["statut"] == "transition_confirmee":
                    if name == self.attente.get("modele_plan") and self.attente.get("suite_plan"):
                        c.adopter_plan(self.attente["suite_plan"], origine="suite_revalidee_apres_observation")
                    survivors[name] = c
                elif issue == "continue" and self.reparation and not any(isinstance(a, list) for a in self.actions):
                    th = getattr(c.perception, 'th_releve', None)
                    if r['statut'] == 'modele_refute' and th is not None:
                        from revision_sans_effet import proposer as reparer_sans_effet
                        new, diag = reparer_sans_effet(c)
                        self.journal.append({'type':'revision_sans_effet','depuis':name,**diag})
                        if new is not None:
                            repaired[name+'/sans_effet']=new
                            continue
                    if (self.revision_projection and th is not None and th.porteur
                            and canon(action) == (NOMS[th.porteur[1]],)):
                        if (len(c.lots) != 1 or len(c.grilles) != 2
                                or len(c.perception.tr.etats) != 1):
                            self.journal.append({'type':'revision_perception_selection_limitee',
                                'depuis':name,'transitions':len(c.lots),
                                'raison':'prototype_premiere_transition_seulement_historique_conserve'})
                        else:
                            try:
                                from revision_perception_selection import reviser
                                new,diag=reviser(c,c.grilles[0],c.grilles[1],canon(action),film)
                                self.journal.append({'type':'revision_perception_selection',
                                    'depuis':name,**diag})
                                if diag['admis'] and all(diag['controle'].get(k) for k in
                                        ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
                                    assert new.lots == c.lots and new.grilles == c.grilles
                                    new.coups=c.coups
                                    new.contraste_revision=copy.deepcopy(c.programme)
                                    new.revision_locale={'operateur':'projection_selection',
                                        'portee':'prefixe_observe','generalisation':False}
                                    new.journal=copy.deepcopy(c.journal)
                                    repaired[name+'/projection_selection']=new
                                    continue
                            except (ValueError,KeyError,TypeError,IndexError,AssertionError) as exc:
                                self.journal.append({'type':'revision_perception_selection_refusee',
                                    'depuis':name,'raison':repr(exc)})
                    if self.revision_projection and th is not None and th.porteur:
                        from revision_calques_hotes import reviser as reviser_hotes
                        from revision_perception_selection import porteur_boite
                        with porteur_boite():
                            new, diag = reviser_hotes(c,c.grilles,c.lots,
                                films=[e['images'] if e else None for e in c.films.entrees])
                        self.journal.append({'type':'revision_calques_hotes','depuis':name,**diag})
                        if new is not None:
                            new.contraste_revision=copy.deepcopy(c.programme)
                            new.revision_locale={'operateur':'calques_hotes','portee':'prefixe_observe','generalisation':False}
                            repaired[name+'/calques_hotes']=new
                            continue
                        from revision_forme_occultee import reviser as reviser_forme
                        with porteur_boite():
                            new, diag = reviser_forme(c,c.grilles,c.lots,
                                films=[e['images'] if e else None for e in c.films.entrees])
                        self.journal.append({'type':'revision_forme_occultee','depuis':name,**diag})
                        if new is not None:
                            new.contraste_revision=copy.deepcopy(c.programme)
                            new.revision_locale={'operateur':'forme_occultee','portee':'prefixe_observe','generalisation':False}
                            repaired[name+'/forme_occultee']=new
                            continue
                    if self.memoire_jeu is not None and self.memoire_jeu.famille=='objets':
                        from diagnostic_contexte_transfert import diagnostiquer
                        prediction=next((p.get("image") for p in self.attente.get("predictions",[[]])[0] if p.get("nom")==name),None)
                        diag=diagnostiquer(c,self.memoire_jeu,self.images[-2],image,action,prediction)
                        if diag is not None:
                            self.diagnostic_transfert=diag
                            self.journal.append({'type':'diagnostic_contrat_transfert',**diag})
                            continue
                    if self.revision_solidite:
                        from revision_solidite import proposer as reparer_solidite
                        candidates,diag=reparer_solidite(c,projection=self.revision_projection)
                        self.journal.append({'type':'revision_regle' if self.revision_projection else 'revision_solidite','depuis':name,**diag})
                        for n,new in candidates:
                            repaired[name+'/'+n]=new
                    try:
                        base = getattr(c.perception, "base", c.perception)
                        candidates, diag = proposer_calques(
                            base, c.programme, c.grilles,
                            [c.action_tuple(a) for lot in c.lots for a in lot['actions']]
                        )
                        self.journal.append({"type": "revision_calques", "depuis": name, "diagnostic": diag})
                        for n, new in candidates:
                            new = Chaine(new.perception, new.programme, c.grilles, c.lots, c.actions,
                                coups_deja_joues=c.coups, reserve=c.limite,
                                films=[e['images'] if e else None for e in c.films.entrees])
                            new.intervalles_contexte = copy.deepcopy(getattr(c, 'intervalles_contexte', []))
                            new.activer_atms()
                            check, state = new.rejouer()
                            if state is None or not check["catalogue_shacl"]:
                                continue
                            repaired[name + "/" + n] = new
                    except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
                        self.journal.append({"type": "revision_refusee", "raison": repr(exc)})
            if any(r['statut'] in ('modele_refute', 'but_refute') for r in results):
                self.releves_p1.discard(len(self.actions) // 8)
            if issue == 'continue':
                from suite_apres_reparation import reprendre as reprendre_suite_reparee
                self.journal.extend(reprendre_suite_reparee(
                    repaired, self.attente, results, anciens_modeles, image))
            if issue == 'defaite':
                from readmission_episode import conserver_physique_terminale
                self.modeles_physiques_fin_episode = conserver_physique_terminale(self.chaines, results)
                self.journal.append({'type':'physique_terminale_archivee',
                    'modeles':list(self.modeles_physiques_fin_episode),
                    'surete_refutee':True,'but_confirme':False,'activation':False})
            self.chaines = {**survivors, **repaired}
            self.revisions += bool(repaired)
            self.reconstruction = not bool(self.chaines) or any(
                name not in self.attente['modeles'] for name in anciens_modeles)
            if self.routage_classes and any(r['statut'] != 'transition_confirmee' for r in results):
                self.routage_exhaustif = True
                self.capacites_differees = False
                self.reconstruction = True
                self.journal.append({'type':'routage_reouvert', 'raison':'divergence_observee'})
        else:
            results = comparer(
                self.attente["predictions"][0], image, film, self.attente.get("hud", []), issue in ("niveau", "victoire")
            )
            if self.decouverte_courte:
                info = information_film(self.images[-2], film, self.attente.get("hud", []), self.attente.get("preuve_masque"))
                self.sondes_inertes = self.sondes_inertes + 1 if info["inerte"] else 0
                self.journal.append({"type": "information_acquisition", "coup": len(self.actions), **info})
            else:
                self.sondes_inertes = self.sondes_inertes + 1 if np.array_equal(self.images[-2], self.images[-1]) else 0
            self.chaines = {}
            self.reconstruction = True
        question = self.attente.get('question_revision')
        if question and any(r.get('nom') == self.attente.get('modele_revision')
                and r.get('statut') in ('transition_confirmee', 'modele_refute', 'but_refute',
                                       'victoire_reelle', 'victoire_verifiee_sur_trace', 'fin_sans_victoire')
                for r in results):
            self.sondes_revision_resolues = set(getattr(self,'sondes_revision_resolues',set()))
            self.sondes_revision_resolues.add(question)
            self.journal.append({'type':'sonde_revision_resolue','question':question,
                                 'coup':len(self.actions)})
        record = {
            "type": "observation",
            "coup": len(self.actions),
            "resultats": results,
            "modeles_survivants": list(self.chaines),
            "revisions": self.revisions,
        }
        self.journal.append(record)
        self.attente = None
        return record
