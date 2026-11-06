"""Révision de clauses natives sur épisodes observés, mémoire conditionnelle révocable."""

import copy
import importlib.util
from pathlib import Path

from atms import ATMS

from chrysalide.arc3.langage import Programme
from chrysalide.langue import depuis_python


def magasin(path):
    source = Path(__file__).resolve().parents[2] / "chrysalide/memory/facts.py"
    spec = importlib.util.spec_from_file_location("_facts_regles", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FactStore(path)


def activation(code, scenes):
    programme = Programme(depuis_python(code))
    for i, scene in enumerate(scenes):
        s = copy.deepcopy(scene)
        programme.step(s, ("OBSERVE",))
        if s.issue is not None:
            return {"frame": i, "issue": s.issue}
    return None


class Apprentissage:
    def __init__(self, candidats, fichier, contexte=None):
        self.contexte = contexte or {"famille": "non_specifiee", "transfert_autorise": False}
        self.candidats = {c["id"]: c for c in candidats}
        self.atms = ATMS()
        self.memoire = magasin(fichier)
        self.episodes = []
        self.supports = {n: [] for n in self.candidats}
        for n in self.candidats:
            self.atms.supposer(n)

    def actives(self, explique=False):
        return [n for n in self.candidats if self.atms.tient(n, [n]) and (not explique or self.supports[n])]

    def observer(self, scenes, issue, preuve, prospectif=False, predictions=None):
        if issue not in ("continue", "niveau", "victoire", "defaite"):
            raise ValueError("Issue inconnue")
        if any(e["preuve"] == preuve for e in self.episodes):
            raise ValueError("Même preuve déjà assimilée")
        decisions = []
        for n in self.actives():
            event = activation(self.candidats[n]["python"], scenes)
            contradictoire = event is not None and event["issue"] != issue
            soutient = event is not None and event["issue"] == issue
            prediction = (predictions or {}).get(n)
            confirmation = bool(prospectif and soutient and prediction == issue)
            result = {
                "id": n,
                "activation": event,
                "contradiction": contradictoire,
                "support": soutient,
                "prediction_avant_action": prediction,
                "confirmation_prospective": confirmation,
            }
            decisions.append(result)
            if contradictoire:
                self.atms.interdire([n])
                self.memoire.invalider(n, "regle_candidate")
            elif soutient:
                self.supports[n].append({"preuve": preuve, "prospectif": confirmation})
                self.memoire.promote(
                    n,
                    "regle_candidate",
                    {
                        "python": self.candidats[n]["python"],
                        "contexte": self.contexte,
                        "supports": self.supports[n],
                        "statut_epistemique": "prediction_confirmee_localement"
                        if any(s["prospectif"] for s in self.supports[n])
                        else "hypothese_soutenue_sur_traces",
                        "portee": "perception et épisodes fournis ; pas de causalité ni universalité prouvée",
                    },
                    provenance=preuve,
                )
        self.episodes.append({"preuve": preuve, "issue": issue, "prospectif": prospectif, "decisions": decisions})
        self.memoire.save()
        return self.episodes[-1]

    def rapport(self):
        return {
            "contexte": self.contexte,
            "actives": self.actives(),
            "expliquantes": self.actives(True),
            "episodes": self.episodes,
            "atms": self.atms.rapport(),
            "supports": self.supports,
        }
