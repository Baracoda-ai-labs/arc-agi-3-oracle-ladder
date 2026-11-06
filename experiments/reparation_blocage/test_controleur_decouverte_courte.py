import json
import unittest
from pathlib import Path

import numpy as np
from controleur_decouverte_courte import DecouverteCourte
from controleur_experimentation import Controleur


class Decouverte(unittest.TestCase):
    def test_missing_raccord_before_first_action(self):
        image = np.zeros((8, 8), dtype=int)
        image[3:5, 3:5] = 2
        c = DecouverteCourte(image, budget=3)
        old = Controleur().decider(c.dossier([1, 2]), chaines={})
        self.assertFalse(old["droit_action"])
        self.assertFalse(old.get("actions"))
        new = c.decider([1, 2])
        self.assertEqual(new["statut"], "sonde_de_decouverte")
        self.assertEqual(len(new["actions"]), 1)
        self.assertEqual(len(c.actions), 0)
        self.assertEqual(new["connaissances"]["but"], "inconnu")
        with self.assertRaises(ValueError):
            c.decider([1, 2])
        c.observer(new["actions"][0], image, [image])
        self.assertEqual(c.dossier([1, 2]).coups_payes, 1)
        self.assertEqual(c.dossier([1, 2]).reserve, 2)
        self.assertEqual(c.decider([1, 2])["actions"], [2] if new["actions"] == [1] else [1])

    def test_cost_information_reuses_existing_selector(self):
        c = DecouverteCourte(np.zeros((8, 8), dtype=int), budget=2)
        hypotheses = ["h1", "h2"]
        ex = [
            {"id": "a", "actions": [1], "cout_actions": 1, "accessible": True, "predictions": {"h1": 0, "h2": 1}},
            {"id": "b", "actions": [2], "cout_actions": 2, "accessible": True, "predictions": {"h1": 0, "h2": 1}},
        ]
        expected = Controleur().choisir_experience(c.dossier([1, 2]), hypotheses, ex)
        got = c.decider([1, 2], hypotheses=hypotheses, experiences=ex)
        self.assertEqual(got["classement"]["choix"]["id"], expected["choix"]["id"])
        self.assertEqual(got["actions"], [1])
        self.assertEqual(got["statut"], "experience_discriminante")
        self.assertFalse(got["droit_action"])

    def test_transient_animation_instead_of_final_only_inertia(self):
        a = np.zeros((8, 8), dtype=int)
        b = a.copy()
        b[2, 2] = 1
        c = DecouverteCourte(a, budget=1)
        d = c.decider([1])
        result = c.observer(d["actions"][0], a, [a, b, a])
        self.assertTrue(np.array_equal(c.images[-2], c.images[-1]))
        self.assertFalse(result["information"]["inerte"])
        self.assertTrue(result["information"]["animation_transitoire"])
        self.assertEqual(c.decider([1])["statut"], "fin_ou_budget")

    def test_causal_cd82_prefix_without_fixed_probe(self):
        root = Path(__file__).parent / "runs/transfert_commun_cd82_1/reel/N1/partie"
        z = np.load(root.with_suffix(".npz"))
        rows = json.loads(root.with_suffix(".json").read_text())["rows"]
        c = DecouverteCourte(z["images"][0])
        # Les expériences sont fournies une à une ; le contrôleur n'a pas le suffixe.
        for i in range(4):
            action = rows[i]["action"]
            exp = {
                "id": str(i),
                "actions": [action],
                "cout_actions": 1,
                "accessible": True,
                "predictions": {"effet": True, "sans_effet": False},
            }
            d = c.decider([1, 2, 3, 4], hypotheses=["effet", "sans_effet"], experiences=[exp])
            c.observer(d["actions"][0], z["images"][i + 1], z[f"film_{i + 1}"])
        d = c.decider([1, 2, 3, 4])
        self.assertEqual(d["description"]["coups_observes"], 4)
        self.assertIn("pisteur_chevauchement_atlas_motifs", d["description"]["capacites_a_essayer"])
        self.assertEqual(d["connaissances"]["but"], "inconnu")
        self.assertFalse(d["description"]["modele_admis"])


if __name__ == "__main__":
    unittest.main()
