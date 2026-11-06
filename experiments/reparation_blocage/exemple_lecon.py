"""Texte pour le proposeur : lu par LeconPython, jamais exécuté par Python."""
from chrysalide_langue import *

LECON = Lecon(
    id="alignement_vers_cible",
    version=1,
    portee="interjeux",
    statut="propose",
    params=["mobile", "cible"],
    mecanismes=["deplacement"],
    mots={
        "contient_couleur": Mot(params=["$o", "$c"], corps=existe(
            existe(pixel(o, xx, yy) == c for xx in intervalle(0, largeur(o)))
            for yy in intervalle(0, hauteur(o)))),
        "selection_couleur": Mot(params=["$c"], corps=filtrer(o for o in objets() if contient_couleur(o, c))),
        "meme_ligne": Mot(params=["$a", "$b"], corps=y(a) == y(b))
    },
    si=longueur(selection_couleur(param("mobile"))) == 1
       and longueur(selection_couleur(param("cible"))) == 1
       and meme_ligne(premier(selection_couleur(param("mobile"))), premier(selection_couleur(param("cible")))),
    regles=[],
    strategie={"methode": "but"},
    provenance={"methode": "proposition_a_tester"},
    limites="Alignement seulement ; obstacles et victoire doivent etre verifies par le modele."
)
