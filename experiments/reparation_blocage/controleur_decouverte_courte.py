"""Ordre des questions à chaque observation, hors SDK, sans séquence initiale fixe."""

import copy

import numpy as np
from classification_prefixe import classifier, information_film
from controleur_experimentation import Controleur, Dossier
from experience_sans_but import proposer as proposer_sonde

from chrysalide.arc3.moteur import NOMS


class DecouverteCourte:
    def __init__(self, image, budget=80, masque=(), preuve_masque=None):
        self.images = [np.asarray(image).copy()]
        self.actions = []
        self.films = []
        self.issues = []
        self.budget = budget
        self.masque = tuple(masque)
        self.preuve_masque = preuve_masque
        self.attente = None
        self.journal = []
        self.connaissances = {}
        self._modele = None

    def dossier(self, offre):
        return Dossier(
            self.images,
            self.actions,
            self.films,
            self.issues,
            len(self.actions),
            max(0, self.budget - len(self.actions)),
            tuple(offre),
        )

    def decider(self, offre, chaines=None, hypotheses=(), experiences=(), secondes=1):
        if self.attente is not None:
            raise ValueError("Observation attendue avant nouvelle décision")
        d = self.dossier(offre)
        description = classifier(self.images, self.actions, self.films, self.masque, self.preuve_masque)
        precedentes = set(self.connaissances.get("capacites_candidates", []))
        capacites = description["capacites_a_essayer"]
        connaissances = {
            "commandes": {
                "offertes": list(offre),
                "essayees": description["canaux_observes"],
                "statut": "observees" if self.actions else "inconnu",
            },
            "perception": {"statut": "partielle", "preuves": description["translation"]["preuves"]},
            "capacites_candidates": capacites,
            "regles": "inconnues",
            "but": "inconnu",
            "issues": "inconnues",
        }
        arbitre = Controleur()  # Les nogoods de couverture ne traversent pas les préfixes.
        diagnostic = arbitre.decider(d, chaines={}, couverture={})
        result = {
            "prefixe_sha256": d.signature(),
            "description": description,
            "connaissances": connaissances,
            "categories_reouvertes": sorted(precedentes - set(capacites)),
            "diagnostic": diagnostic,
            "droit_action": False,
            "verification": "hors_SDK",
            "actions": [],
            "question": None,
        }
        self.connaissances = connaissances
        if d.reserve <= 0 or (self.issues and self.issues[-1] != "continue"):
            return {**result, "statut": "fin_ou_budget"}
        expected = [
            {"actions": [{"action": NOMS[a]} if isinstance(a, int) else {"action": "MOUSE", "row": a[2], "col": a[1]}]}
            for a in self.actions
        ]
        for name, c in (chaines or {}).items():
            if (
                c.refute
                or c.lots != expected
                or not np.array_equal(c.grilles, self.images)
                or c.films.signatures() != d.preuves.signatures()
            ):
                continue
            check, state = c.rejouer()
            if state is None:
                continue
            connaissances["regles"] = "compatibles_sur_prefixe"
            plan = c.proposer(secondes=secondes)
            if plan["statut"] != "plan_simule_valide" or not plan["plan"]["actions"]:
                continue
            a = plan["plan"]["actions"][0]
            action = ["clic", a[2], a[1]] if a[0] == "MOUSE" else next(k for k, v in NOMS.items() if v == a[0])
            if (6 if isinstance(action, list) else action) not in offre:
                continue
            self._modele = c
            result.update(
                statut="plan_conditionnel",
                actions=[action],
                modele=name,
                question="La prochaine transition et son issue correspondent-elles au modèle ?",
                risque="couverture_partielle",
                controle=check,
            )
            break
        else:
            atomiques = [
                e
                for e in experiences
                if len(e.get("actions", [])) == 1
                and e.get("cout_acces", 0) == 0
                and (6 if isinstance(e["actions"][0], list) else e["actions"][0]) in offre
            ]
            classement = arbitre.choisir_experience(d, hypotheses, atomiques) if hypotheses else None
            choix = classement["choix"] if classement else None
            if choix:
                result.update(
                    statut="experience_discriminante",
                    actions=choix["actions"],
                    question=choix.get("question", "Quelle hypothèse explique cette transition ?"),
                    classement=classement,
                    risque=choix.get("risque", "inconnu"),
                )
            else:
                sonde, _diag = proposer_sonde(self.images, self.actions, self.films, offre)
                if sonde:
                    question = (
                        "Quel effet produit cette commande ?"
                        if len(set(description["canaux_observes"])) < 2
                        else "Quels éléments changent et quelle capacité manque pour expliquer leur évolution ?"
                    )
                    result.update(
                        statut="sonde_de_decouverte",
                        actions=sonde["actions"][:1],
                        question=question,
                        risque="inconnu",
                        cout_actions=1,
                        classement=classement,
                    )
                else:
                    result.update(statut="hors_catalogue_sans_experience", question="Quelle capacité manque à ce préfixe ?")
        if result["actions"]:
            self.attente = copy.deepcopy(result)
        self.journal.append(copy.deepcopy(result))
        return result

    def observer(self, action, image, film, issue="continue"):
        if self.attente is None or self.attente["actions"] != [action]:
            raise ValueError("Observation sans décision prospective")
        film = np.asarray(film)
        image = np.asarray(image)
        if not len(film) or not np.array_equal(film[-1], image):
            raise ValueError("Film non aligné")
        info = information_film(self.images[-1], film, self.masque, self.preuve_masque)
        modele = None
        if self._modele is not None:
            canon = ("MOUSE", action[2], action[1]) if isinstance(action, list) else (NOMS[action],)
            modele = self._modele.observer(
                canon, image, victoire=issue in ("niveau", "victoire"), termine=issue != "continue", source="trace", film=film
            )
            if modele["statut"] != "transition_confirmee":
                self.connaissances["regles"] = "a_reouvrir"
        self.images.append(image.copy())
        self.actions.append(copy.deepcopy(action))
        self.films.append(film.copy())
        self.issues.append(issue)
        result = {
            "coup": len(self.actions),
            "information": info,
            "modele": modele,
            "issue_observee": issue,
            "regle_prouvee": False,
            "nouvelle_observation_requise": True,
        }
        self.attente = None
        self._modele = None
        self.journal.append(result)
        return result
