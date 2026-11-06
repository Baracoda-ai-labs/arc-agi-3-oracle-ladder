"""[G] Correctif LOCAL (à intégrer par C) : `export_langage._condition_but` ne traduit pas le but `marques` et rend
`False` (but jamais atteint, et non signalé dans les non-exportés). Traduction de `theorie.marques_manquantes(...) == 0` :
chaque marque (x, y) est recouverte par une case visible d'une pièce (objet de plus d'une case, hors marqueur 512).
`installer()` remplace la fonction dans le module ; rien d'autre ne change."""
from chrysalide.arc3.logique import export_langage as el

_ORIG = el._condition_but


def _marque(x, y):
    v = "$cv"
    return ["existe", v, ["a", x, y], ["et", [">", ["*", ["largeur", v], ["hauteur", v]], 1],
                                          ["non", ["existe", "$q", el._objets(512), ["=", "$q", v]]],
                                          [">=", ["pixel", v, ["-", x, ["x", v]], ["-", y, ["y", v]]], 0]]]


def _condition_but(b):
    if b[0] == "marques":
        return ["et", True, *[_marque(x, y) for _c, cs in b[1] for x, y in cs]]
    return _ORIG(b)


def installer():
    el._condition_but = _condition_but
