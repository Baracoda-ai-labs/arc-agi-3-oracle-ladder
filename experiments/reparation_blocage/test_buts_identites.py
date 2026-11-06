"""Raccord perception sans but et objectifs bornés, préfixe causal uniquement."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np
from boucle_agent_integree import empreintes
from chaine_agent_integree import AgentIntegre, canon


class ButsIdentites(unittest.TestCase):
    def data(self):
        p = Path(__file__).parent / "runs/multijeux_nuit_integre1/m0r0/N1/partie"
        z = np.load(p.with_suffix(".npz"))
        acts = [r["action"] for r in json.loads(p.with_suffix(".json").read_text())["rows"]]
        a = AgentIntegre(z["images"][:9], acts[:8], [z[f"film_{i + 1}"] for i in range(8)], ["continue"] * 8)
        return a, z, acts

    def test_causal_induction_and_heldout(self):
        a, z, acts = self.data()
        a.reconstruire()
        neutral = a.chaines["perception_sans_but_identites"]
        self.assertEqual(neutral.perception.buts, [])
        self.assertEqual(len(neutral.perception.mobiles), 2)
        ctrl, state = neutral.rejouer()
        self.assertTrue(ctrl["compilation_fidele"])
        pc, sc = state
        for i in range(8, len(acts)):
            pc.step(sc, canon(acts[i]))
            self.assertTrue(np.array_equal(neutral.perception.rendu(sc), neutral.perception.vue(z["images"][i + 1])))
        goals = [n for n in a.chaines if n.startswith("but_identites_")]
        self.assertLessEqual(len(goals), 8)
        self.assertTrue(any("ancre_" in n for n in goals))
        self.assertTrue(any("contact_" in n for n in goals))
        d = a.decider([1, 2, 3, 4], secondes=4)
        self.assertEqual(d["statut"], "action_conditionnelle")
        self.assertEqual(d["but"], "hypothese_non_prouvee")

    def test_goal_refutation_keeps_perception(self):
        a, z, _acts = self.data()
        a.reconstruire()
        a.reparation = False
        neutral = a.chaines["perception_sans_but_identites"]
        name = next(n for n in a.chaines if n.startswith("but_identites_"))
        goal = a.chaines[name]
        a.chaines = {"perception_sans_but_identites": neutral, name: goal}
        neutral.observer = Mock(return_value={"statut": "transition_confirmee"})
        goal.observer = Mock(return_value={"statut": "but_refute"})
        a.attente = {"actions": [1], "modeles": list(a.chaines)}
        a.observer(1, z["images"][9], z["film_9"], "continue")
        self.assertIn("perception_sans_but_identites", a.chaines)
        self.assertNotIn(name, a.chaines)
        self.assertFalse(a.reconstruction)

    def test_dynamic_gauge_reader_manifest(self):
        self.assertTrue(any(n.endswith("/references/astra4/livraison_astra4/ajouts/boucle_v4/economie.py") for n in empreintes()))


if __name__ == "__main__":
    unittest.main()
