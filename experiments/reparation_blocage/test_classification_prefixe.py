import json
import unittest
from pathlib import Path

import numpy as np
from classification_prefixe import classifier, information_film

R = Path(__file__).parent / "runs"


def charger(nom, n):
    p = R / nom / "N1/partie"
    z = np.load(p.with_suffix(".npz"))
    actions = [r["action"] for r in json.loads(p.with_suffix(".json").read_text())["rows"][:n]]
    return list(z["images"][: n + 1]), actions, [z[f"film_{i + 1}"] for i in range(n)]


class ClassificationPrefixe(unittest.TestCase):
    def test_cd82_causal_sans_masque_automatique(self):
        data = charger("transfert_commun_cd82_1/reel", 4)
        d = classifier(*data)
        self.assertEqual(d["coups_observes"], 4)
        self.assertEqual(d["transformation_motif"]["statut"], "candidate")
        self.assertIn("pisteur_chevauchement_atlas_motifs", d["capacites_a_essayer"])
        self.assertTrue(any(p["coup"] == 3 and p["quart_de_tour_non_suffisant"] for p in d["transformation_motif"]["preuves"]))
        self.assertFalse(d["droit_action"])
        self.assertFalse(d["modele_admis"])
        self.assertTrue(all(p["coup"] <= 4 for p in d["transformation_motif"]["preuves"]))
        # Descripteur indépendant sur le suffixe7/8, non donné au premier appel.
        gs, acts, fs = charger("transfert_commun_cd82_1/reel", 8)
        h = classifier(gs[6:9], acts[6:8], fs[6:8])
        self.assertEqual(h["transformation_motif"]["statut"], "candidate")

    def test_translation_archives(self):
        for name in ["multijeux_nuit_integre1/ar25", "multijeux_nuit_integre1/m0r0"]:
            d = classifier(*charger(name, 8))
            self.assertTrue(d["translation"]["preuves"])
            self.assertIn("objets_translation_identites", d["capacites_a_essayer"])
            self.assertIn("but", d["inconnues"])

    def test_animation_never_discarded_as_inert(self):
        a = np.zeros((4, 4), dtype=int)
        b = a.copy()
        b[1, 1] = 2
        d = information_film(a, [a, b, a])
        self.assertTrue(d["animation_transitoire"])
        self.assertFalse(d["inerte"])
        b = a.copy()
        b[3, 1] = 1
        with self.assertRaises(ValueError):
            information_film(a, [b], [(3, 1)])
        d = information_film(a, [b], [(3, 1)], {"source": "fixture region connue", "statut": "valide"})
        self.assertTrue(d["inerte"])
        self.assertFalse(information_film(a, [b])["inerte"])

    def test_palette_permutation(self):
        gs, acts, fs = charger("transfert_commun_cd82_1/reel", 4)
        perm = np.arange(16)[::-1]
        d = classifier([perm[g] for g in gs], acts, [perm[f] for f in fs])
        self.assertEqual(d["transformation_motif"]["statut"], "candidate")
        self.assertIn("pisteur_chevauchement_atlas_motifs", d["capacites_a_essayer"])


if __name__ == "__main__":
    unittest.main()
