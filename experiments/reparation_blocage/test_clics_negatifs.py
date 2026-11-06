"""Préfixe causal10, métamorphismes et refus des fausses inerties, aucun SDK."""

import json
import unittest
from pathlib import Path

import numpy as np
from chaine_agent_integree import AgentIntegre
from clics_negatifs import normaliser
from roles_observes import PerceptionRoles
from selection_observee import SelectionObservee

R = Path(__file__).parent / "runs"


def lire(path, n):
    p = R / path / "N1/partie"
    z = np.load(p.with_suffix(".npz"))
    actions = [r["action"] for r in json.loads(p.with_suffix(".json").read_text())["rows"][:n]]
    return list(z["images"][: n + 1]), actions, [z[f"film_{i + 1}"] for i in range(n)]


class ClicsNegatifs(unittest.TestCase):
    def verifier_prefixe(self, gs, actions, films):
        normalized, proofs = normaliser(gs, actions, films)
        self.assertEqual(normalized[-1], 6)
        self.assertEqual(proofs[-1]["coup"], 10)
        v = PerceptionRoles(gs, actions, clics_negatifs=True, films=films)
        a = AgentIntegre(gs, actions, films, ["continue"] * len(actions), decouverte_courte=True)
        c = a._chaine(v, v.programme())
        ctrl, state = c.rejouer()
        self.assertTrue(ctrl["compilation_fidele"])
        self.assertIsNotNone(state)
        self.assertEqual(len(c.lots), 10)
        self.assertEqual(len(c.films.entrees), 10)
        d = a.decider([1, 2, 3, 4, 6], secondes=3)
        self.assertIn("perception_sans_but_roles", a.chaines)
        self.assertFalse(d["acquisition"]["prerequis_selection"]["clic_differe"])
        self.assertEqual(d["actions"][0][0], "clic")
        self.assertNotEqual(d["actions"][0], actions[-1])

    def test_causal_ten_and_transformation(self):
        gs, actions, films = lire("decouverte_courte_arc1/ka59", 10)
        self.verifier_prefixe(gs, actions, films)
        perm = np.arange(16)[::-1]
        changed = [perm[np.roll(g, 1, axis=1)] for g in gs]
        fs = [perm[np.roll(f, 1, axis=2)] for f in films]
        acts = [["clic", a[1] + 1, a[2]] if isinstance(a, list) else a for a in actions]
        self.verifier_prefixe(changed, acts, fs)

    def test_animation_and_nonselection_change_rejected(self):
        gs, actions, films = lire("decouverte_courte_arc1/ka59", 10)
        frame = gs[9].copy()
        frame[20, 20] = (int(frame[20, 20]) + 1) % 16
        animation = films[:-1] + [np.array([gs[9], frame, gs[10]])]
        with self.assertRaisesRegex(ValueError, "effet visible"):
            normaliser(gs, actions, animation)
        changed = gs[:-1] + [frame]
        fs = films[:-1] + [np.array([frame])]
        with self.assertRaisesRegex(ValueError, "effet visible"):
            normaliser(changed, actions, fs)
        with self.assertRaisesRegex(ValueError, "Films requis"):
            normaliser(gs, actions, None)

    def test_interpretable_click_after_negative_fixture(self):
        gs, actions, films = lire("freinage_commun_ka59_1/reel", 12)
        # Métamorphisme de trace : une transition explicitement sans effet avant le clic positif existant.
        augmented = gs[:12] + [gs[11].copy()] + gs[12:]
        acts = actions[:11] + [["clic", 0, 0]] + actions[11:]
        fs = films[:11] + [np.array([gs[11]])] + films[11:]
        v = SelectionObservee(augmented, acts, films=fs, clics_negatifs=True)
        self.assertEqual(v.premier_clic_interpretable, 12)
        a = AgentIntegre(augmented, acts, fs, ["continue"] * 13)
        c = a._chaine(v, v.programme())
        ctrl, state = c.rejouer()
        self.assertTrue(ctrl["compilation_fidele"])
        self.assertIsNotNone(state)
        self.assertEqual(len(c.lots), 13)
        self.assertEqual(len(c.films.entrees), 13)
        self.assertEqual(v.preuves_clics_negatifs[0]["coup"], 12)


if __name__ == "__main__":
    unittest.main()
