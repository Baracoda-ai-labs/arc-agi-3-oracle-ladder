"""Contrôles du raccord optionnel ; aucun vrai SDK ni futur donné au pilote."""

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import boucle_agent_integree as cli
import numpy as np
from chaine_agent_integree import AgentIntegre

R = Path(__file__).parent
CASES = {
    "ar25": "multijeux_nuit_integre1/ar25",
    "ka59": "freinage_commun_ka59_1/reel",
    "m0r0": "multijeux_nuit_integre1/m0r0",
    "cd82": "transfert_commun_cd82_1/reel",
}


def prefix(name, n):
    p = R / "runs" / CASES[name] / "N1/partie"
    z = np.load(p.with_suffix(".npz"))
    acts = [r["action"] for r in json.loads(p.with_suffix(".json").read_text())["rows"][:n]]
    return list(z["images"][: n + 1]), acts, [z[f"film_{i + 1}"] for i in range(n)], ["continue"] * n


class AcquisitionIntegree(unittest.TestCase):
    def test_zero_actions_four_archives_no_click_poison(self):
        for name in CASES:
            data = prefix(name, 0)
            old = AgentIntegre(*data).decider([1, 2, 3, 4, 6], secondes=1)
            self.assertFalse(old["actions"])
            agent = AgentIntegre(*data, decouverte_courte=True)
            new = agent.decider([1, 2, 3, 4, 6], secondes=1)
            self.assertEqual(len(new["actions"]), 1)
            self.assertIn(new["actions"][0], [1, 2, 3, 4])
            self.assertTrue(new["acquisition"]["prerequis_selection"]["clic_differe"])
            self.assertEqual(new["acquisition"]["classification"]["coups_observes"], 0)
            with self.assertRaises(ValueError):
                agent.decider([1, 2, 3, 4, 6])

    def test_offer_click_only_does_not_require_movement(self):
        agent = AgentIntegre(*prefix("cd82", 0), decouverte_courte=True)
        d = agent.decider([6], secondes=1)
        self.assertEqual(d["actions"][0][0], "clic")
        self.assertFalse(d["acquisition"]["prerequis_selection"]["clic_differe"])

    def test_prefix_eight_keeps_existing_plans(self):
        for name in ["ar25", "ka59", "m0r0"]:
            data = prefix(name, 8)
            before = AgentIntegre(*data).decider([1, 2, 3, 4, 6], secondes=5)
            after = AgentIntegre(*data, decouverte_courte=True).decider([1, 2, 3, 4, 6], secondes=5)
            self.assertEqual(before["actions"], after["actions"])
            self.assertEqual(after["statut"], "action_conditionnelle")

    def test_transient_not_inert_and_invalid_film_rejected(self):
        data = prefix("cd82", 0)
        agent = AgentIntegre(*data, decouverte_courte=True)
        d = agent.decider([1], secondes=1)
        a = data[0][0]
        b = a.copy()
        b[20, 20] = (int(b[20, 20]) + 1) % 16
        with self.assertRaises(ValueError):
            agent.observer(1, a, [b], "continue")
        self.assertEqual(len(agent.actions), 0)
        agent.observer(d["actions"][0], a, [a, b, a], "continue")
        self.assertEqual(agent.sondes_inertes, 0)
        self.assertEqual(len(agent.actions), 1)

    def test_option_cli_counts_every_step_without_fixed_probes(self):
        class FakeLab:
            def __init__(self, jeu, level, racine, out):
                self.output = out
                self.output.parent.mkdir(parents=True)
                self.images = [np.zeros((64, 64), dtype=np.int8)]
                self.images[0][20:23, 20:23] = 2
                self.rows = []
                self.films = {}
                self.actions_disponibles = [1, 2, 3, 4]
                self.finished = self.won = self.partie_gagnee = False
                self.save()

            def save(self):
                np.savez_compressed(self.output.with_suffix(".npz"), images=self.images, **self.films)

            def play(self, a, purpose):
                im = self.images[-1].copy()
                self.images.append(im)
                self.films[f"film_{len(self.rows) + 1}"] = np.array([im])
                self.won = self.finished = len(self.rows) == 1
                self.rows.append({"action": a, "state": "NOT_FINISHED", "levels_completed": int(self.won), "purpose": purpose})
                self.save()
                return im, np.array([im])

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            args = argparse.Namespace(jeu="ar25", sortie=out, coups=8, secondes=10, sans_reparation=False, decouverte_courte=True)
            with patch.object(cli, "LaboP1", FakeLab):
                cli.main(args)
            b = json.loads((out / "bilan.json").read_text())
            self.assertEqual(b["coups_reels"], 2)
            self.assertEqual(b["appels_step_tentes"], 2)
            self.assertEqual(b["initialisations"], 1)
            self.assertTrue((out / "decision_000/observation.json").exists())
            d = json.loads((out / "decision_000/decision.json").read_text())
            self.assertEqual(d["acquisition"]["classification"]["coups_observes"], 0)


if __name__ == "__main__":
    unittest.main()
