"""Arbitre sans SDK : même dossier pour faits, modèles, questions et décisions."""

import hashlib
import json
from dataclasses import dataclass

import numpy as np
from atms import ATMS
from evidence_films import Films
from propositions_python import Proposition


@dataclass
class Dossier:
    images: list
    actions: list
    films: list
    issues: list
    coups_payes: int
    reserve: int
    offre: tuple = ()

    def __post_init__(self):
        n = len(self.actions)
        if len(self.images) != n + 1 or len(self.films) != n or len(self.issues) != n:
            raise ValueError("Historique incomplet")
        if self.coups_payes < n or self.reserve < 0:
            raise ValueError("Comptabilité invalide")
        self.preuves = Films()
        for i, film in enumerate(self.films):
            if not len(film) or not np.array_equal(film[-1], self.images[i + 1]):
                raise ValueError("Film final non aligné")
            self.preuves.ajouter(self.images[i], film)

    def signature(self):
        sha = hashlib.sha256()
        for g in self.images:
            sha.update(np.asarray(g, dtype=np.int16).tobytes())
        sha.update(json.dumps([self.actions, self.issues, self.coups_payes, self.reserve], sort_keys=True).encode())
        sha.update(json.dumps(self.preuves.signatures()).encode())
        return sha.hexdigest()


class Controleur:
    def __init__(self):
        self.atms = ATMS()

    def choisir_experience(self, dossier, hypotheses, experiences):
        """Interface commune aux proposeurs ; portée identique et coût d'accès explicite."""
        from espace_experiences import classer_experiences

        result = classer_experiences(experiences, hypotheses, dossier.reserve)
        result["prefixe_sha256"] = dossier.signature()
        result["coups_deja_payes"] = dossier.coups_payes
        return result

    def decider(self, dossier, chaines=None, experiences=(), local=None, couverture=None, petites_regles=False):
        """Aucun nom de jeu, futur, solution ou outil d'action dans cette interface."""
        chaines = chaines or {}
        couverture = dict(couverture or {})
        for key in ("perception", "mouvement", "contact", "issues"):
            couverture.setdefault(key, "inconnue")
        if any(v not in ("inconnue", "compatible", "contredite") for v in couverture.values()):
            raise ValueError("Statut de couverture inconnu")
        unknown = [k for k, v in couverture.items() if v != "compatible"]
        signature = dossier.signature()
        self.atms.fait("prefixe:" + signature)
        for key in couverture:
            self.atms.supposer("couverture:" + key)
        self.atms.justifier("plan_couvert", ["couverture:" + k for k in couverture])
        for key in unknown:
            self.atms.interdire(["couverture:" + key])
        report = {
            "prefixe_sha256": signature,
            "observations": len(dossier.actions),
            "couverture": couverture,
            "incertitudes": unknown,
            "cout": {"coups_deja_payes": dossier.coups_payes, "reserve": dossier.reserve, "nouveaux_coups": 0},
            "film_signatures": dossier.preuves.signatures(),
            "droit_action": False,
            "evaluations": [],
            "portee": "décision sur traces ; aucune expérience réellement exécutée",
        }
        if dossier.issues and dossier.issues[-1] != "continue":
            report.update(statut="episode_termine", question="Expliquer l’issue enregistrée avant toute nouvelle décision.")
            report["atms"] = self.atms.rapport()
            return report
        # Validation commune avant tout arbitrage : la présence dans un catalogue ne suffit pas.
        admitted = {}
        for name, c in chaines.items():
            aligned = len(c.lots) == len(dossier.actions) and np.array_equal(c.grilles, dossier.images)
            expected = []
            for a in dossier.actions:
                expected.append(
                    {"actions": [{"action": "MOUSE", "row": a[2], "col": a[1]}]}
                    if isinstance(a, list)
                    else {"actions": [{"action": {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT"}[a]}]}
                )
            aligned = aligned and c.lots == expected
            if not aligned:
                raise ValueError("Chaîne et dossier portent des préfixes distincts")
            check, cur = c.rejouer()
            if cur is not None and not c.refute:
                admitted[name] = c
            else:
                report["evaluations"].append({"hypothese": name, "refus": check})
        report["modeles_admissibles"] = list(admitted)
        useful = []
        if len(admitted) >= 2:
            for source in experiences:
                try:
                    p = Proposition(source)
                    e = p.evaluer_experience(admitted)
                    e["source_python"] = source
                    report["evaluations"].append(e)
                    if e["statut"] == "experience_discriminante_simulee" and e["cout_coups_prefixe"] <= dossier.reserve:
                        useful.append(e)
                except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                    report["evaluations"].append({"refus": repr(exc)})
        # Adaptateur local explicitement partiel : pas de faux certificat Chaine.
        if local is not None:
            report["modeles_locaux_partiels"] = local.actives()
            if local.actives():
                suggestion = local.proposer(dossier.images[-1], list(dossier.offre))
                for candidate in suggestion["experiences_candidates"]:
                    groups = {json.dumps(p, sort_keys=True, default=int) for p in candidate["predictions"].values()}
                    e = {
                        "statut": "experience_partielle" if len(groups) > 1 else "sans_separation",
                        "action": candidate["action"],
                        "predictions": candidate["predictions"],
                        "groupes": len(groups),
                        "cout_coups_prefixe": 1,
                        "risque": "inconnu",
                        "couvre_issues": False,
                    }
                    report["evaluations"].append(e)
                    if len(groups) > 1 and dossier.reserve >= 1:
                        useful.append(e)
        if petites_regles:
            from proposeur_petites_regles import proposer

            proposition = proposer(dossier, admitted, local)
            report["petites_regles"] = proposition
            useful.extend(e for e in proposition["experiences"] if e["statut"] == "experience_discriminante_simulee")
        if useful:
            chosen = max(useful, key=lambda e: (e.get("evaluation", e).get("groupes", 1), -e["cout_coups_prefixe"]))
            report.update(
                statut="experience_conditionnelle",
                experience=chosen,
                question="Quelle prédiction observable distingue les modèles compatibles ?",
                utilite="séparation simulée seulement",
                risque="inconnu" if "issues" in unknown else "conditionnel_aux_modeles",
                incertitudes_restantes=unknown,
            )
        elif not unknown and admitted:
            plans = {n: c.proposer(secondes=0.2) for n, c in admitted.items()}
            good = [p for p in plans.values() if p["statut"] == "plan_simule_valide"]
            if len(good) == len(admitted) and len({str(p["plan"]["actions"][0]) for p in good}) == 1:
                report.update(statut="plan_conditionnel", plan=good[0]["plan"])
            else:
                report.update(statut="aucun_plan_commun", plans=plans)
        else:
            report.update(
                statut="hypothese_manquante",
                question="Quelle condition observable pourrait changer une issue encore inconnue ?"
                if "issues" in unknown
                else "Quelle interprétation explique les observations non couvertes ?",
                demande={
                    "primitives_existantes": ["contact_moteur", "perdre", "gagner", "niveau_suivant"],
                    "attendus": ["hypothese", "alternative", "preuves_frames", "experience", "predictions_distinctes"],
                    "solution_fournie": False,
                },
                experience=None,
                utilite="aucune expérience discriminante établie avec les modèles disponibles",
            )
        report["atms"] = self.atms.rapport()
        return report
