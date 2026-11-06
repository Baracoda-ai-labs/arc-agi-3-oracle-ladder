# SPDX-License-Identifier: MIT-0
"""CW-203 [session B] : écrit `experiments/T3.7/regles/dedale.json`, programme du LANGAGE pour TOUS les jeux T4 « dédale »
(base, pousser, cibles, trous, glace, gravite, lave, portail, cle_porte, interrupteur, gemmes, recharge, modificateur,
poursuivant, selection). Ce script n'exécute aucune règle : il assemble des termes du langage (listes JSON) pour garder le
programme lisible. État logique en cases dans `etat` (comme le jeu) ; chaque coup : logique, puis mise à jour des sprites.
Plan du niveau = donnée `plan` du moteur ; palette (couleurs d'interrupteur, de compteur, d'attribut, formes d'icône) =
section `niveau` "*" injectée par le juge depuis les constantes du jeu (non visibles au début du niveau)."""
import json
import os
from pathlib import Path

# Ablation (prereg patchs_regles.md) : SANS="gravite,portail" retire ces blocs ; vide = programme complet (T3.7)
SANS = {x for x in os.environ.get("SANS", "").split(",") if x}


def on(nom):
    return nom not in SANS


def L(*a):
    return list(a)


def et(*a):
    a = [x for x in a if x is not True]  # interrupteur d'ablation allumé : disparaît (programme complet inchangé)
    return False if False in a else a[0] if len(a) == 1 else ["et", *a]


def ou(*a):
    a = [x for x in a if x is not False]
    return True if True in a else a[0] if len(a) == 1 else ["ou", *a]


def non(a):
    return (not a) if isinstance(a, bool) else ["non", a]


def eq(a, b):
    return ["=", a, b]


def ne(a, b):
    return ["!=", a, b]


def E(n):
    return ["etat", n]


def P(k):
    return ["plan", k]


def PL(k):
    return ["pl", k]


def poser(n, v):
    return ["poser", n, v]


def si_alors(c, a, b=None):
    return ["si_alors", c, a, b or []]


def elem(lst, i):
    return ["elem", lst, i]


def cont(lst, x):
    return ["contient", lst, x]


def cell(x, y):
    return ["liste", x, y]


def add(p, dx, dy):
    return cell(["+", elem(p, 0), dx], ["+", elem(p, 1), dy])


def remplacer(nom, i, v):
    """etat[nom][i] = v, en reconstruisant la liste (le langage n'a pas d'affectation indexée)."""
    return [poser("tmp", ["liste"]),
            ["pour", "$i_", ["intervalle", 0, ["longueur", E(nom)]],
             [["empiler", "tmp", ["si", eq("$i_", i), v, elem(E(nom), "$i_")]]]],
            poser(nom, E("tmp"))]


def retirer_de(nom, x):
    return poser(nom, ["filtrer", "$z_", E(nom), ne("$z_", x)])


MOTS = {
    "plan": {"params": ["$k"], "corps": ["table", ["donnees_de_niveau", "plan"], "$k", None]},
    # liste du plan, vide si la clé est absente
    "pl": {"params": ["$k"], "corps": ["table", ["donnees_de_niveau", "plan"], "$k", ["liste"]]},
    "px": {"params": ["$p"], "corps": ["+", P("ox"), ["*", elem("$p", 0), P("s")]]},
    "py": {"params": ["$p"], "corps": ["+", P("oy"), ["*", elem("$p", 1), P("s")]]},
    "xy": {"params": ["$q"], "corps": cell(elem("$q", 0), elem("$q", 1))},
    "porte_fermee": {"params": ["$p"], "corps": ["existe", "$q", PL("portes"),
                                                  et(eq(["xy", "$q"], "$p"), non(cont(E("cles"), elem("$q", 2))))]},
    # _bloque du jeu : qui ∈ "joueur" | "boite" | "chasseur"
    "bloque": {"params": ["$p", "$qui"], "corps": ou(
        ["<", elem("$p", 0), 0], ["<", elem("$p", 1), 0], [">=", elem("$p", 0), P("C")], [">=", elem("$p", 1), P("R")],
        cont(PL("murs"), "$p"), ["porte_fermee", "$p"],
        et(cont(PL("grilles"), "$p"), eq(E("grilles"), 0)),
        et(ne("$qui", "joueur"), cont(PL("lave"), "$p")),
        et(cont(PL("trous"), "$p"), non(cont(E("trous"), "$p")), ou(ne("$qui", "boite"), eq(P("trous_murs"), True))),
        et(eq("$qui", "boite"), eq(P("pousse_off"), True)))},
    "libre_boite": {"params": ["$p"], "corps": et(non(["bloque", "$p", "boite"]), non(cont(E("boites"), "$p")),
                                                  non(cont(E("av"), "$p")), ne("$p", E("pours")))},
    "trou_ouvert": {"params": ["$p"], "corps": et(cont(PL("trous"), "$p"), non(cont(E("trous"), "$p")),
                                                  ne(P("trous_murs"), True))},
    "signe": {"params": ["$v"], "corps": ["si", [">", "$v", 0], 1, ["si", ["<", "$v", 0], -1, 0]]},
    "abs": {"params": ["$v"], "corps": ["si", ["<", "$v", 0], ["-", 0, "$v"], "$v"]},
    "ouverte": {"params": [], "corps": et(eq(["longueur", E("gem")], ["longueur", PL("gemmes")]),
                                          ["tous", "$c", PL("cibles"), cont(E("boites"), "$c")])},
}

AU_DEBUT = [
    poser("av", ["pl", "avatars"]), poser("sel", 0), poser("boites", ["pl", "boites"]), poser("cles", ["liste"]),
    poser("grilles", 0), poser("attr", ["si", eq(P("attr0"), None), ["liste", 0, 0, 0], P("attr0")]),
    poser("gem", ["liste"]), poser("rech", ["liste"]), poser("g", P("G")),
    poser("pours", ["si", eq(P("poursuivant"), None), None, ["xy", P("poursuivant")]]),
    poser("trous", ["liste"]), poser("statut", 0), poser("gens", ["liste"]),
]

# ---- un pas de déplacement (corps de la boucle de glisse) ----
T = E("t")
ARRIVEE = [  # p = t ; ramassages puis lave / portail / glace, dans l'ordre du jeu
    poser("p", T),
    si_alors(et(on("cle_porte"), ["existe", "$q", PL("cles"), eq(["xy", "$q"], T)]),
             [["empiler", "cles", elem(["premier_tel_que", "$q", PL("cles"), eq(["xy", "$q"], T)], 2)]]),
    si_alors(et(on("gemmes"), cont(PL("gemmes"), T), non(cont(E("gem"), ["indice", PL("gemmes"), T]))),
             [["empiler", "gem", ["indice", PL("gemmes"), T]]]),
    si_alors(et(on("recharge"), cont(PL("recharges"), T), non(cont(E("rech"), ["indice", PL("recharges"), T]))),
             [["empiler", "rech", ["indice", PL("recharges"), T]], poser("g", ["+", P("G"), 1])]),
    si_alors(et(on("modificateur"), ["existe", "$q", PL("mods"), eq(["xy", "$q"], T)]),
             [poser("k", elem(["premier_tel_que", "$q", PL("mods"), eq(["xy", "$q"], T)], 2)),
              si_alors(eq(E("k"), "forme"), remplacer("attr", 0, ["%", ["+", elem(E("attr"), 0), 1], P("nformes")]),
                       [si_alors(eq(E("k"), "couleur"), remplacer("attr", 1, ["%", ["+", elem(E("attr"), 1), 1], P("ncouleurs")]),
                                 remplacer("attr", 2, ["%", ["+", elem(E("attr"), 2), 1], 4]))])]),
    ["pour", "$i", ["intervalle", 0, ["longueur", PL("generateurs")]], [  # création (CW-209) : une boîte en S, une fois
        poser("gq", elem(PL("generateurs"), "$i")),
        poser("gs", cell(elem(E("gq"), 2), elem(E("gq"), 3))),
        si_alors(et(on("creation"), eq(["xy", E("gq")], T), non(cont(E("gens"), "$i")), non(cont(E("boites"), E("gs"))),
                    non(cont(E("av"), E("gs"))), ne(E("gs"), E("pours"))),
                 [["empiler", "boites", E("gs")], ["empiler", "gens", "$i"]])]],
    si_alors(et(on("interrupteur"), cont(PL("inters"), T)), [poser("grilles", ["-", 1, E("grilles")])]),
    si_alors(et(on("lave"), cont(PL("lave"), T)), [poser("statut", -1), poser("go", False)], [
        si_alors(et(on("portail"), ["existe", "$q", PL("portails"), ou(eq(["xy", "$q"], T), eq(cell(elem("$q", 2), elem("$q", 3)), T))]),
                 [poser("q", ["si", non(["existe", "$q", PL("portails"), eq(["xy", "$q"], T)]),
                              ["xy", ["premier_tel_que", "$q", PL("portails"), eq(cell(elem("$q", 2), elem("$q", 3)), T)]],
                              cell(elem(["premier_tel_que", "$q", PL("portails"), eq(["xy", "$q"], T)], 2),
                                   elem(["premier_tel_que", "$q", PL("portails"), eq(["xy", "$q"], T)], 3))]),
                  si_alors(et(non(cont(E("boites"), E("q"))), non(cont(E("av"), E("q"))), ne(E("q"), E("pours"))),
                           [poser("p", E("q"))]),
                  poser("go", False)],
                 [si_alors(ou(non(on("glace")), non(cont(PL("glace"), T))), [poser("go", False)])])]),
]
PAS = [
    poser("t", add(E("p"), E("dx"), E("dy"))),
    si_alors(ou(["bloque", T, "joueur"], cont(E("av"), T)), [poser("go", False)], [
        si_alors(cont(E("boites"), T), [
            si_alors(ou(eq(P("pousse_off"), True), non(on("poussee"))), [poser("go", False)], [
                poser("t2", add(T, E("dx"), E("dy"))),
                si_alors(["trou_ouvert", E("t2")], [retirer_de("boites", T), ["empiler", "trous", E("t2")]], [
                    si_alors(["libre_boite", E("t2")], [retirer_de("boites", T), ["empiler", "boites", E("t2")]],
                             [poser("go", False)])])])]),
        si_alors(E("go"), ARRIVEE)]),
]
DEPLACER = [
    poser("dx", ["table", {"LEFT": -1, "RIGHT": 1}, ["action"], 0]),
    poser("dy", ["table", {"UP": -1, "DOWN": 1}, ["action"], 0]),
    poser("p", elem(E("av"), E("sel"))), poser("go", True),
    poser("p0", E("p")), poser("derriere", add(E("p"), ["-", 0, E("dx")], ["-", 0, E("dy")])),
    ["tant_que", E("go"), PAS, ["*", P("C"), P("R")]],
    *remplacer("av", E("sel"), E("p")),
    si_alors(et(on("tirer"), eq(P("tirer"), True), ne(E("p"), E("p0")), cont(E("boites"), E("derriere")), non(cont(E("boites"), E("p0")))),
             [retirer_de("boites", E("derriere")), ["empiler", "boites", E("p0")]]),  # tirer (CW-209) : la boîte suit
]
GRAVITE = [
    poser("bouge", True),
    ["tant_que", E("bouge"), [
        poser("bouge", False),
        ["pour", "$b", ["trier", E("boites"), "$o", ["-", 0, elem("$o", 1)]], [
            poser("d", add("$b", 0, 1)),
            si_alors(["trou_ouvert", E("d")], [retirer_de("boites", "$b"), ["empiler", "trous", E("d")], poser("bouge", True)], [
                si_alors(["libre_boite", E("d")], [retirer_de("boites", "$b"), ["empiler", "boites", E("d")], poser("bouge", True)])])]]],
     200],
]
CX = ["-", elem(elem(E("av"), 0), 0), elem(E("pours"), 0)]
CY = ["-", elem(elem(E("av"), 0), 1), elem(E("pours"), 1)]
OPT1 = ["si", [">", ["abs", CY], ["abs", CX]], cell(0, ["signe", CY]), cell(["signe", CX], 0)]
OPT2 = ["si", [">", ["abs", CY], ["abs", CX]], cell(["signe", CX], 0), cell(0, ["signe", CY])]


def essai(opt):
    q = add(E("pours"), elem(opt, 0), elem(opt, 1))
    return et(E("cherche"), ou(ne(elem(opt, 0), 0), ne(elem(opt, 1), 0)), non(["bloque", q, "chasseur"]), non(cont(E("boites"), q)))


POURSUIVANT = [
    si_alors(et(on("poursuivant"), ne(E("pours"), None), eq(E("statut"), 0)), [
        si_alors(cont(E("av"), E("pours")), [poser("statut", -1)], [
            poser("cherche", True),
            si_alors(essai(OPT1), [poser("pours", add(E("pours"), elem(OPT1, 0), elem(OPT1, 1))), poser("cherche", False)]),
            si_alors(essai(OPT2), [poser("pours", add(E("pours"), elem(OPT2, 0), elem(OPT2, 1))), poser("cherche", False)]),
            si_alors(cont(E("av"), E("pours")), [poser("statut", -1)])])])]

FIN = [
    poser("g", ["-", E("g"), 1]),
    si_alors(et(eq(E("statut"), 0), ["ouverte"],
                ["tous", "$i", ["intervalle", 0, ["longueur", E("av")]], eq(elem(E("av"), "$i"), elem(PL("sorties"), "$i"))],
                ou(eq(P("but_attr"), None), eq(E("attr"), P("but_attr")))),
             [poser("statut", 1)],
             [si_alors(et(eq(E("statut"), 0), ["<=", E("g"), 0]), [poser("statut", -1)])]),
]


def placer_case(o, p):
    return ["placer", o, ["px", p], ["py", p]]


def un(nom):
    return ["premier", ["objets", {"nom": nom}]]


def par_rang(tag, n, corps):
    """Le k-ième sprite d'un type, dans l'ordre de construction du niveau (le langage n'a pas de conversion texte ↔ nombre
    pour lire l'indice dans le nom : mot manquant noté)."""
    return ["pour", "$k", ["intervalle", 0, ["longueur", ["objets", {"tag": tag}]]],
            [["pour", "$o", ["liste", elem(["objets", {"tag": tag}], "$k")], corps]]]


def en_place(q):
    return et(eq(["px", q], ["x", "$o"]), eq(["py", q], ["y", "$o"]))


def entree(nom_plan):
    return ["premier_tel_que", "$q", PL(nom_plan), en_place("$q")]


SPRITES = [  # _sync du jeu
    par_rang("type:avatar", None, [placer_case("$o", elem(E("av"), "$k"))]),
    ["pour", "$o", ["objets", {"tag": "type:selection"}], [placer_case("$o", elem(E("av"), E("sel")))]],
    poser("bs", ["trier", E("boites"), "$o", ["+", ["*", elem("$o", 0), 1000], elem("$o", 1)]]),
    par_rang("type:boite", None, [
        si_alors(["<", "$k", ["longueur", E("bs")]], [["montrer", "$o", True], placer_case("$o", elem(E("bs"), "$k"))],
                 [["montrer", "$o", False]])]),
    ["pour", "$o", ["objets", {"tag": "type:cle"}], [["montrer", "$o", non(cont(E("cles"), elem(entree("cles"), 2)))]]],
    ["pour", "$o", ["objets", {"tag": "type:porte"}], [["montrer", "$o", non(cont(E("cles"), elem(entree("portes"), 2)))]]],
    ["pour", "$o", ["objets", {"tag": "type:grille"}], [["montrer", "$o", eq(E("grilles"), 0)]]],
    ["pour", "$o", ["objets", {"tag": "type:interrupteur"}],
     [["recolorer", "$o", ["si", eq(E("grilles"), 1), ["param", "inter_off"], ["param", "inter_on"]],
       ["si", eq(E("grilles"), 1), ["param", "inter_on"], ["param", "inter_off"]]]]],
    ["pour", "$o", ["objets", {"tag": "type:trou"}], [["montrer", "$o", non(["existe", "$t", E("trous"), en_place("$t")])]]],
    ["pour", "$o", ["objets", {"tag": "type:gemme"}],
     [["montrer", "$o", non(cont(E("gem"), ["indice", PL("gemmes"), entree("gemmes")]))]]],
    ["pour", "$o", ["objets", {"tag": "type:compteur"}],
     [si_alors(cont(E("gem"), ["//", ["-", ["x", "$o"], elem(P("pos_pips"), 0)], P("pas_pip")]),
               [["recolorer", "$o", ["param", "pip_vide"], ["param", "pip_plein"]]])]],
    ["pour", "$o", ["objets", {"tag": "type:recharge"}],
     [["montrer", "$o", non(cont(E("rech"), ["indice", PL("recharges"), entree("recharges")]))]]],
    ["pour", "$o", ["objets", {"tag": "type:generateur"}],
     [["montrer", "$o", non(cont(E("gens"), ["indice", PL("generateurs"), entree("generateurs")]))]]],
    si_alors(ne(E("pours"), None), [["pour", "$o", ["objets", {"tag": "type:poursuivant"}], [placer_case("$o", E("pours"))]]]),
    ["pour", "$o", ["objets", {"tag": "type:sortie_fermee"}], [["montrer", "$o", non(["ouverte"])]]],
    si_alors(ne(P("but_attr"), None), [
        ["pour", "$o", ["objets", {"tag": "type:cle_courante"}], [
            ["poser_motif", "$o", elem(["param", "formes"], elem(E("attr"), 0))],
            ["recolorer", "$o", elem(["param", "couleur_formes"], elem(E("attr"), 0)), elem(["param", "attr"], elem(E("attr"), 1))],
            ["tourner", "$o", ["%", ["-", elem(E("attr"), 2), E("rot_indic")], 4]],
            poser("rot_indic", elem(E("attr"), 2))]]]),
]

PROGRAMME = {
    "notes": "CW-203 [B] : programme de FAMILLE pour tous les jeux T4 « dédale », assemblé par construire_dedale.py. "
             "État en cases (positions des avatars, boîtes, clés prises, grilles, attribut, gemmes, recharges, jauge, "
             "poursuivant, trous comblés) ; un coup = sélection (SPACE) ou glisse case par case (poussée, trou comblé, "
             "ramassages, modificateurs, interrupteur, lave, portail, glace), gravité des boîtes, pas du poursuivant, "
             "jauge, victoire / défaite ; puis placement des sprites comme le jeu.",
    "mots_manquants": [],
    "etat": {"rot_indic": 0},
    "mots": MOTS,
    "au_debut": [*AU_DEBUT, poser("rot_indic", elem(E("attr"), 2))],
    "regles": [
        {"nom": "coup", "alors": [
            si_alors(eq(["action"], "SPACE"), [poser("sel", ["%", ["+", E("sel"), 1], ["longueur", E("av")]])]),
            si_alors(cont(["liste", "UP", "DOWN", "LEFT", "RIGHT"], ["action"]), DEPLACER),
            si_alors(et(on("gravite"), eq(P("gravite"), True)), GRAVITE),
            *POURSUIVANT, *FIN, *SPRITES,
            si_alors(eq(E("statut"), 1), [["niveau_suivant"]], [si_alors(eq(E("statut"), -1), [["perdre"]])])]},
    ],
}

if __name__ == "__main__":
    sortie = Path(os.environ.get("SORTIE") or Path(__file__).resolve().parent / "regles/dedale.json")
    sortie.write_text(json.dumps(PROGRAMME, ensure_ascii=False, indent=1))
    print("écrit", sortie, len(sortie.read_text()), "octets")
