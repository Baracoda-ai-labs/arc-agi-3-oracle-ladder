"""Sous-grammaire des buts sortie/contact et ancre, sur identités observées.

Réutilise les formes de logique.induction.buts_candidats et la traduction
chevauche de contact_observe.programme. Les candidats ne sont jamais des faits.
"""

import copy
from itertools import combinations, islice

from chrysalide.arc3.langage import Programme


def programmes(vue, image_initiale=None, limite=8):
    base = vue.programme()
    mobiles = [f"mobile_{i}" for i in range(len(vue.mobiles))]
    statiques = [f"statique_{i}" for i in range(len(vue.statiques))]
    pairs = list(combinations(mobiles, 2)) + [(a, b) for a in mobiles for b in statiques]
    # Alternance des formes, comme _candidats_buts ; budget avant recherche.
    specs = ((forme, a, b) for a, b in pairs for forme in ("contact", "ancre"))
    for forme, a, b in islice(specs, limite):
        condition = (
            ["chevauche", "$a", "$b"]
            if forme == "contact"
            else ["et", ["=", ["x", "$a"], ["x", "$b"]], ["=", ["y", "$a"], ["y", "$b"]]]
        )
        p = copy.deepcopy(base)
        p["regles"].append(
            {
                "nom": f"but_{forme}_hypothese",
                "phase": 1,
                "quand": ["existe", "$a", ["objets", {"tag": a}], ["existe", "$b", ["objets", {"tag": b}], condition]],
                "alors": [["niveau_suivant"]],
            }
        )
        # Une condition déjà vraie sans victoire observée n'est pas un but admissible.
        probe = Programme(p)
        initial = vue.scene(image_initiale) if image_initiale is not None else None
        if initial is not None:
            probe.step(initial, ("OBSERVE",))
            if initial.issue is not None:
                continue
        yield f"{forme}_{a}_{b}", p
