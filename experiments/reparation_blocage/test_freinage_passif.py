"""Induction au préfixe 19 ; suffixe caché à l'inducteur ; permutations sans SDK."""

import json
import unittest
from pathlib import Path

import numpy as np
from chaine_agent_integree import AgentIntegre, canon
from freinage_passif import candidats


class Freinage(unittest.TestCase):
    def data(self):
        p = Path(__file__).parent / "runs/multijeux_nuit_integre1/ka59/N1/partie"
        z = np.load(p.with_suffix(".npz"))
        actions = [r["action"] for r in json.loads(p.with_suffix(".json").read_text())["rows"]]
        return z["images"], actions, [z[f"film_{i + 1}"] for i in range(len(actions))]

    def check_prefix(self, gs, actions, films):
        agent = AgentIntegre(gs[:20], actions[:19], films[:19], ["continue"] * 19)
        theories = candidats(gs[:20], actions[:19], films[:19])
        self.assertEqual({v.mode_frein for _, v in theories}, {"entree", "sortie_retardee"})
        admitted = []
        for name, v in theories:
            c = agent._chaine(v, v.programme())
            ctrl, state = c.rejouer()
            self.assertTrue(ctrl["compilation_fidele"], name)
            self.assertIsNotNone(state, name)
            admitted.append((v, state))
        return admitted

    def test_prefix_and_heldout(self):
        gs, actions, films = self.data()
        admitted = self.check_prefix(gs, actions, films)
        for v, (pc, sc) in admitted:
            # Les observations 20..75 ne sont pas données à l'inducteur.
            for i in range(19, 75):
                pc.step(sc, canon(actions[i]))
                self.assertTrue(np.array_equal(v.rendu(sc), v.vue(gs[i + 1])), i + 1)
            pc.step(sc, canon(actions[75]))
            # L'échec 76 est conservé : ces candidats ne constituent pas un modèle complet.
            self.assertFalse(np.array_equal(v.rendu(sc), v.vue(gs[76])))

    def test_palette_and_horizontal_reflection(self):
        gs, actions, films = self.data()
        perm = np.arange(16)[::-1]
        transformed = perm[gs[:20, :, ::-1]]
        fs = [perm[f[:, :, ::-1]] for f in films[:19]]
        acts = [(["clic", 63 - a[1], a[2]] if isinstance(a, list) else {3: 4, 4: 3}.get(a, a)) for a in actions[:19]]
        self.check_prefix(transformed, acts, fs)

    def test_bank_exposes_both(self):
        gs, actions, films = self.data()
        a = AgentIntegre(gs[:20], actions[:19], films[:19], ["continue"] * 19)
        a.reconstruire()
        self.assertEqual(len([n for n in a.chaines if n.startswith("frein_")]), 2)
        d = a.decider([1, 2, 3, 4, 6], secondes=3)
        self.assertEqual(d["statut"], "action_conditionnelle")
        self.assertEqual(d["but"], "hypothese_non_prouvee")


if __name__ == "__main__":
    unittest.main()
