"""Préflight sur traces existantes uniquement ; aucun SDK."""

import argparse
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import boucle_agent_integree as pilote
import numpy as np
from chaine_agent_integree import AgentIntegre, canon, sdk

R = Path(__file__).parent


def archive(folder):
    p = R / "runs" / folder / "N1/partie"
    z = np.load(p.with_suffix(".npz"))
    j = json.loads(p.with_suffix(".json").read_text())
    return AgentIntegre(
        list(z["images"][:9]), [r["action"] for r in j["rows"][:8]], [z[f"film_{i + 1}"] for i in range(8)], ["continue"] * 8
    )


class Integration(unittest.TestCase):
    def test_archives_no_false_authority(self):
        for folder in ("perception_guidee_arc1", "guidage_ka59_fige1"):
            a = archive(folder)
            d = a.decider([1, 2, 3, 4, 6], secondes=3)
            self.assertEqual(d["statut"], "action_conditionnelle")
            self.assertEqual(d["but"], "hypothese_non_prouvee")
            self.assertFalse(d["diagnostic_arbitre"]["droit_action"])
            self.assertTrue(d["modeles"])
            # Observation prospective de la prédiction : simulation, aucune victoire réelle revendiquée.
            pred = d["predictions"][0][0]["image"]
            a.observer(d["actions"][0], np.array(pred), np.array([pred]), "continue")
            self.assertEqual(len(a.actions), 9)
            self.assertIsNone(a.attente)
            self.assertTrue(a.journal[-1]["resultats"])

    def test_offered_actions_and_no_unplanned_observation(self):
        a = archive("perception_guidee_arc1")
        self.assertEqual(a.decider([], secondes=1)["actions"], [])
        with self.assertRaises(ValueError):
            a.observer(1, a.images[-1], [], "continue")

    def test_coordinate_roundtrip(self):
        for action in (1, 2, 3, 4, ["clic", 7, 12]):
            self.assertEqual(sdk(canon(action)), action)

    def test_timeout_initialisation_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            args = argparse.Namespace(jeu="ar25", sortie=out, coups=80, secondes=0.02, sans_reparation=False)
            with patch.object(pilote, "LaboP1", side_effect=lambda *a: time.sleep(0.2)):
                pilote.main(args)
            b = json.loads((out / "bilan.json").read_text())
            self.assertEqual(b["statut"], "budget_mural")
            self.assertEqual(b["coups_reels"], 0)
            self.assertEqual(b["initialisations"], 0)
            self.assertEqual(b["initialisations_tentees"], 1)

    def test_manifest_has_compiler_and_adapter(self):
        names = pilote.empreintes()
        self.assertTrue(any(n.endswith("/agent_p1/labo.py") for n in names))
        self.assertTrue(any(n.endswith("/sim_rapide.py") for n in names))


if __name__ == "__main__":
    unittest.main()
