# SPDX-License-Identifier: MIT-0
"""C (E2, V1) : fermeture arrière des objets du but et sous-buts lus dans la victoire."""
from chrysalide.arc3.logique.plan_langage import _Vue, conjoints, objets_du_but, regle_victoire

TEXTE = {"regles": [
    {"quand": ["=", ["action"], "UP"], "alors": [["deplacer", ["premier", ["objets", {"tag": "joueur"}]], 0, -1],
                                                 ["pousser", ["objets", {"tag": "caisse"}]]]},
    {"quand": ["vrai"], "alors": [["clignoter", ["objets", {"tag": "decor"}]]]},
    {"quand": ["et", ["=", ["action"], "SPACE"], ["vide", ["objets", {"tag": "caisse"}]], ["etat", "ouvert"]],
     "alors": [["niveau_suivant"]]}]}


def test_fermeture_arriere():
    r = regle_victoire(TEXTE)
    assert objets_du_but(TEXTE, r) == {"caisse", "joueur"}  # le décor qui clignote sort de la clé


def test_filtre_generique_desactive():
    t = {"regles": [*TEXTE["regles"], {"quand": ["vrai"], "alors": [["pousser", ["objets"]], ["noter", ["objets", {"tag": "caisse"}]]]}]}
    assert objets_du_but(t, regle_victoire(t)) is None


def test_sous_buts_sans_action():
    sous = conjoints(regle_victoire(TEXTE))
    assert [s["quand"][0] for s in sous] == ["vide", "etat"]


def test_vue_garde_les_indices():
    class S:
        sprites = ({"tags": ["decor"], "x": 1}, {"tags": ["caisse"], "x": 2})
        camera = None
    v = _Vue(S(), lambda o: "caisse" in o["tags"])
    assert v.sprites == [{}, {"tags": ["caisse"], "x": 2}] and v.camera is None
