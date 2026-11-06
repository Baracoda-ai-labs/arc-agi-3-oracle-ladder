# SPDX-License-Identifier: MIT-0
"""CW-241 [session E] : interpréteur des règles PuzzleScript ÉCRIT DANS LE LANGAGE (chrysalide/arc3/langage.py).
Ce script ne fait qu'écrire `interpreteur_ps.json` (le programme) ; les fonctions ci-dessous sont du sucre syntaxique pour
écrire des termes ["op", …] lisiblement. Aucun Python n'est exécuté pendant une partie : le programme lit les règles
analysées par `psmoteur.Jeu` (données, section « niveau ») et rejoue la sémantique de `psmoteur.Partie.tour`.
Représentation : l'état PuzzleScript EST la scène (un sprite par objet dessiné et par case) ; le mouvement d'un objet est
l'attribut "m" du sprite ; l'objet de fond (non dessiné) est implicite dans toute case dont sa couche est vide."""
import json
from pathlib import Path

ICI = Path(__file__).resolve().parent
N = None


def E(n):  # état nommé
    return ["etat", n]


def T(d, k):  # champ k d'un dict de données
    return ["table", d, k]


def L(*a):  # liste construite
    return ["liste", *a]


def mot(params, corps, sorte="terme"):
    return {"params": params, "corps": corps, "sorte": sorte}


def poser(n, v):
    return ["poser", n, v]


def ajouter(n, v):  # etat[n] = etat[n] + [v] (sans copie : garde l'identité des objets ; empiler copie en profondeur)
    return poser(n, ["+", E(n), L(v)])


def si(c, a, b):
    return ["si", c, a, b]


def dx(d):
    return ["elem", T(E("DIRS"), d), 0]


def dy(d):
    return ["elem", T(E("DIRS"), d), 1]


MOTS = {
    # ---- géométrie : case (x, y) de la grille PuzzleScript ↔ pixels de la vue 64×64
    "px": mot(["$x"], ["+", E("OX"), ["*", "$x", E("C")]]),
    "py": mot(["$y"], ["+", E("OY"), ["*", "$y", E("C")]]),
    "cx": mot(["$s"], ["//", ["-", ["x", "$s"], E("OX")], E("C")]),
    "cy": mot(["$s"], ["//", ["-", ["y", "$s"], E("OY")], E("C")]),
    "dans": mot(["$x", "$y"], ["et", [">=", "$x", 0], ["<", "$x", E("W")], [">=", "$y", 0], ["<", "$y", E("H")]]),
    # objets dessinés de la case : jusqu'à 3 pixels sondes (terme natif a(x, y), qui ne voit que les pixels opaques),
    # plus un balayage par position pour les objets qu'aucune sonde ne voit (objets transparents)
    "objs": mot(["$x", "$y"], ["objs_px", ["px", "$x"], ["py", "$y"]]),
    "sonde": mot(["$X", "$Y", "$q"], si(["=", "$q", N], L(), ["a", ["+", "$X", ["%", "$q", E("C")]], ["+", "$Y", ["//", "$q", E("C")]]])),
    "union": mot(["$l1", "$l2"], ["+", "$l1", ["filtrer", "$s", "$l2", ["non", ["contient", "$l1", "$s"]]]]),
    "objs_px": mot(["$X", "$Y"], ["union", ["union", ["sonde", "$X", "$Y", E("P1")], ["sonde", "$X", "$Y", E("P2")]],
        si(["et", ["=", E("P3"), N], ["vide", E("INVIS")]], L(),
           ["union", ["sonde", "$X", "$Y", E("P3")],
            si(["vide", E("INVIS")], L(), ["filtrer", "$s", ["objets", {}],
                ["et", ["=", ["x", "$s"], "$X"], ["=", ["y", "$s"], "$Y"], ["contient", E("INVIS"), ["nom", "$s"]]]])])]),
    "opaque": mot(["$o", "$q"], [">=", ["pixel", T(E("MOD"), "$o"), ["%", "$q", E("C")], ["//", "$q", E("C")]], 0]),
    "premier_opaque": mot(["$o"], si(["=", "$o", N], N,
                                     ["premier_tel_que", "$q", ["intervalle", 0, ["*", E("C"), E("C")]], ["opaque", "$o", "$q"]])),
    "objs_tri": mot(["$x", "$y"], ["trier", ["objs", "$x", "$y"], "$s", ["calque", "$s"]]),
    "fond_la": mot(["$cel"], ["non", ["existe", "$s", "$cel", ["=", ["calque", "$s"], E("KFOND")]]]),
    "nom_de": mot(["$o"], si(["contient", E("NOMS"), "$o"], "$o", ["nom", "$o"])),
    # ---- modificateurs de mouvement (> < ^ v relatifs à la direction de la règle)
    "absolu": mot(["$mod", "$d"], si(["contient", L("^", "v", "<", ">"), "$mod"], T(T(E("REL"), "$d"), "$mod"), "$mod")),
    "mod_abs_ok": mot(["$a", "$m"], si(["=", "$a", "moving"], ["!=", "$m", N],
                                       si(["=", "$a", "stationary"], ["=", "$m", N], ["=", "$m", "$a"]))),
    "mod_ok": mot(["$mod", "$m", "$d"], si(["=", "$mod", N], True, ["mod_abs_ok", ["absolu", "$mod", "$d"], "$m"])),
    # objet de la case qui satisfait le terme (sprite, ou le nom du fond implicite), None sinon
    "trouve": mot(["$cel", "$t", "$d"], si(
        ["et", ["contient", T("$t", "ens"), E("FOND")], ["fond_la", "$cel"], ["mod_ok", T("$t", "mod"), N, "$d"]],
        E("FOND"),
        ["premier_tel_que", "$s", "$cel", ["et", ["contient", T("$t", "ens"), ["nom", "$s"]],
                                           ["mod_ok", T("$t", "mod"), ["attr", "$s", "m"], "$d"]]])),
    "cell_ok": mot(["$cp", "$cel", "$d"], ["tous", "$t", "$cp", si(T("$t", "neg"), ["=", ["trouve", "$cel", "$t", "$d"], N],
                                                                    ["!=", ["trouve", "$cel", "$t", "$d"], N])]),
    "motif_ok": mot(["$p", "$d", "$x", "$y"], ["et", ["dans", "$x", "$y"],
        ["dans", ["+", "$x", ["*", dx("$d"), ["-", ["longueur", "$p"], 1]]],
                 ["+", "$y", ["*", dy("$d"), ["-", ["longueur", "$p"], 1]]]],
        ["tous", "$n", ["intervalle", 0, ["longueur", "$p"]],
         ["cell_ok", ["elem", "$p", "$n"], ["objs_tri", ["+", "$x", ["*", dx("$d"), "$n"]], ["+", "$y", ["*", dy("$d"), "$n"]]],
          "$d"]]]),
    "ancre_ok": mot(["$t"], ["et", ["non", T("$t", "neg")], ["non", ["contient", T("$t", "ens"), E("FOND")]]]),
    # ---- victoire (psmoteur.Partie.victoire)
    "a_dans": mot(["$cel", "$X"], ["ou", ["existe", "$s", "$cel", ["contient", "$X", ["nom", "$s"]]],
                                   ["et", ["contient", "$X", E("FOND")], ["fond_la", "$cel"]]]),
    "sur": mot(["$Y", "$x", "$y"], si(["=", "$Y", N], True, ["a_dans", ["objs", "$x", "$y"], "$Y"])),
    "cond_v": mot(["$v"], si(["contient", ["elem", "$v", 1], E("FOND")], ["cond_v_cases", "$v"], ["cond_v_objets", "$v"])),
    "cond_v_objets": mot(["$v"], ["cond_q", ["elem", "$v", 0],
        ["filtrer", "$s", ["objets", {}], ["contient", ["elem", "$v", 1], ["nom", "$s"]]], ["elem", "$v", 2]]),
    "cond_q": mot(["$q", "$xs", "$Y"], si(["=", "$q", "all"], ["tous", "$s", "$xs", ["sur", "$Y", ["cx", "$s"], ["cy", "$s"]]],
        si(["=", "$q", "no"], ["non", ["existe", "$s", "$xs", ["sur", "$Y", ["cx", "$s"], ["cy", "$s"]]]],
           si(["=", "$q", "some"], ["existe", "$s", "$xs", ["sur", "$Y", ["cx", "$s"], ["cy", "$s"]]], True)))),
    "cond_v_cases": mot(["$v"], ["cond_q_cases", ["elem", "$v", 0], ["filtrer", "$i", ["intervalle", 0, ["*", E("W"), E("H")]],
        ["a_dans", ["objs", ["%", "$i", E("W")], ["//", "$i", E("W")]], ["elem", "$v", 1]]], ["elem", "$v", 2]]),
    "cond_q_cases": mot(["$q", "$is", "$Y"], si(["=", "$q", "all"],
        ["tous", "$i", "$is", ["sur", "$Y", ["%", "$i", E("W")], ["//", "$i", E("W")]]],
        si(["=", "$q", "no"], ["non", ["existe", "$i", "$is", ["sur", "$Y", ["%", "$i", E("W")], ["//", "$i", E("W")]]]],
           si(["=", "$q", "some"], ["existe", "$i", "$is", ["sur", "$Y", ["%", "$i", E("W")], ["//", "$i", E("W")]]], True)))),
    "gagne_ps": mot([], ["et", ["non", ["vide", E("VICT")]], ["tous", "$v", E("VICT"), ["cond_v", "$v"]]]),
    "bouge_ok": mot(["$s"], ["et", ["!=", ["attr", "$s", "m"], N], ["!=", ["attr", "$s", "m"], "action"]]),
    "peut_aller": mot(["$s"], ["et", ["!=", ["calque", "$s"], E("KFOND")],
        ["dans", ["+", ["cx", "$s"], dx(["attr", "$s", "m"])], ["+", ["cy", "$s"], dy(["attr", "$s", "m"])]],
        ["non", ["existe", "$u", ["objs", ["+", ["cx", "$s"], dx(["attr", "$s", "m"])], ["+", ["cy", "$s"], dy(["attr", "$s", "m"])]],
                 ["=", ["calque", "$u"], ["calque", "$s"]]]]]),
    "cle_case": mot(["$s"], ["+", ["*", ["+", ["*", ["cy", "$s"], E("W")], ["cx", "$s"]], 100], ["calque", "$s"]]),
    "joueurs": mot([], ["filtrer", "$s", ["objets", {}], ["contient", E("JOUEURS"), ["nom", "$s"]]]),
    "mod_droite": mot(["$a", "$m0"], si(["=", "$a", "moving"], "$m0", si(["=", "$a", "stationary"], N, "$a"))),
}

# départ du motif déduit d'un objet d'ancrage $s placé dans la cellule n0 du motif ; ancres en ordre ligne par ligne
SX = ["-", ["cx", "$s"], ["*", E("n0"), dx("$d")]]
SY = ["-", ["cy", "$s"], ["*", E("n0"), dy("$d")]]
ANCRES = ["trier", ["filtrer", "$s", ["objets", {}], ["contient", T(E("ta"), "ens"), ["nom", "$s"]]],
          "$s", ["+", ["*", ["y", "$s"], 100], ["x", "$s"]]]

EFFETS = {
    # ---- correspondances d'un motif [c1 | c2 | …] dans la direction d → etat starts = [[x, y]…] (ordre ligne par ligne)
    "chercher": mot(["$p", "$d"], [
        poser("starts", L()),
        poser("n0", ["premier_tel_que", "$n", ["intervalle", 0, ["longueur", "$p"]],
                     ["existe", "$t", ["elem", "$p", "$n"], ["ancre_ok", "$t"]]]),
        ["si_alors", ["=", E("n0"), N],
         [["pour", "$i", ["intervalle", 0, ["*", E("W"), E("H")]],
           [["si_alors", ["motif_ok", "$p", "$d", ["%", "$i", E("W")], ["//", "$i", E("W")]],
             [ajouter("starts", L(["%", "$i", E("W")], ["//", "$i", E("W")]))]]]]],
         [poser("ta", ["premier_tel_que", "$t", ["elem", "$p", E("n0")], ["ancre_ok", "$t"]]),
          ["pour", "$s", ANCRES, [["si_alors", ["et", ["non", ["contient", E("starts"), L(SX, SY)]], ["motif_ok", "$p", "$d", SX, SY]],
                                   [ajouter("starts", L(SX, SY))]]]]]],
    ]),
    # produit cartésien de etat listes → etat combos (comme itertools.product : la dernière liste varie le plus vite)
    "produit": mot([], [
        poser("combos", L(L())),
        ["pour", "$l", E("listes"), [
            poser("nv", L()),
            ["pour", "$c", E("combos"), [["pour", "$e", "$l", [ajouter("nv", ["+", "$c", L("$e")])]]]],
            poser("combos", E("nv"))]],
    ]),
    "oter": mot(["$o"], [
        ["si_alors", ["et", ["!=", "$o", N], ["contient", ["objets", {}], "$o"]], [["retirer", "$o"], poser("gch", True)]],
    ]),
    # cellule ← [objet, mouvement] sur la couche de l'objet (psmoteur.Partie._remplacer, fin)
    "poser_case": mot(["$on", "$t", "$tg", "$x", "$y", "$d"], [
        poser("anc", ["premier_tel_que", "$s", ["objs", "$x", "$y"], ["=", ["calque", "$s"], T(E("COUCHE"), "$on")]]),
        poser("m0", si(["et", ["!=", E("anc"), N], ["=", ["nom", E("anc")], "$on"]], ["attr", E("anc"), "m"], N)),
        poser("mn", si(["!=", T("$t", "mod"), N], ["mod_droite", ["absolu", T("$t", "mod"), "$d"], E("m0")],
                       si(["et", ["!=", "$tg", N], ["!=", T("$tg", "mod"), N]], N, E("m0")))),
        ["si_alors", ["=", "$on", E("FOND")],
         [["si_alors", ["!=", E("anc"), N], [["retirer", E("anc")], poser("gch", True)]]],
         [["si_alors", ["et", ["!=", E("anc"), N], ["=", ["nom", E("anc")], "$on"]],
           [["si_alors", ["!=", ["attr", E("anc"), "m"], E("mn")], [["poser_attr", E("anc"), "m", E("mn")], poser("gch", True)]]],
           [["si_alors", ["!=", E("anc"), N], [["retirer", E("anc")]]],
            ["soit_creer", "$s", T(E("MOD"), "$on"), ["px", "$x"], ["py", "$y"], [["poser_attr", "$s", "m", E("mn")]]],
            poser("gch", True)]]]],
    ]),
    "remplacer_case": mot(["$gp", "$dp", "$li", "$x", "$y", "$d"], [
        # objets liés à gauche dont le nom n'est plus à droite : retirés
        ["pour", "$n", ["intervalle", 0, ["longueur", "$gp"]], [
            ["si_alors", ["et", ["non", T(["elem", "$gp", "$n"], "neg")],
                          ["non", ["existe", "$u", "$dp", ["et", ["non", T("$u", "neg")],
                                                          ["=", T("$u", "nom"), T(["elem", "$gp", "$n"], "nom")]]]]],
             [["si_alors", ["=", ["elem", "$li", "$n"], E("FOND")], [poser("fond_ote", True)],
               [["oter", ["elem", "$li", "$n"]]]]]]]],
        ["pour", "$t", "$dp", [
            ["si_alors", T("$t", "neg"),
             [["pour", "$s", ["filtrer", "$s", ["objs", "$x", "$y"], ["contient", T("$t", "ens"), ["nom", "$s"]]],
               [["retirer", "$s"], poser("gch", True)]]],
             [poser("ln", ["premier_tel_que", "$n", ["intervalle", 0, ["longueur", "$gp"]],
                           ["et", ["non", T(["elem", "$gp", "$n"], "neg")], ["=", T(["elem", "$gp", "$n"], "nom"), T("$t", "nom")]]]),
              poser("ob", si(["!=", E("ln"), N], ["elem", "$li", E("ln")],
                             si(["=", ["longueur", T("$t", "ens")], 1], ["elem", T("$t", "ens"), 0], "REFUS"))),
              ["si_alors", ["=", E("ob"), "REFUS"], [poser("refus", "propriété créée sans lien")],
               [["poser_case", ["nom_de", E("ob")], "$t", si(["!=", E("ln"), N], ["elem", "$gp", E("ln")], N),
                 "$x", "$y", "$d"]]]]]]],
    ]),
    "remplacer_motif": mot(["$p", "$q", "$d", "$st"], [
        poser("liens", L()),
        ["pour", "$n", ["intervalle", 0, ["longueur", "$p"]], [
            poser("cel", ["objs_tri", ["+", ["elem", "$st", 0], ["*", dx("$d"), "$n"]], ["+", ["elem", "$st", 1], ["*", dy("$d"), "$n"]]]),
            poser("tmp", L()),
            ["pour", "$t", ["elem", "$p", "$n"], [ajouter("tmp", ["trouve", E("cel"), "$t", "$d"])]],
            ajouter("liens", E("tmp"))]],
        ["pour", "$n", ["intervalle", 0, ["longueur", "$p"]], [
            ["remplacer_case", ["elem", "$p", "$n"], ["elem", "$q", "$n"], ["elem", E("liens"), "$n"],
             ["+", ["elem", "$st", 0], ["*", dx("$d"), "$n"]], ["+", ["elem", "$st", 1], ["*", dy("$d"), "$n"]], "$d"]]],
    ]),
    "appliquer": mot(["$r"], [
        ["pour", "$d", T("$r", "dirs"), [
            poser("listes", L()), poser("vide", False),
            ["pour", "$p", T("$r", "g"), [
                ["chercher", "$p", "$d"],
                ["si_alors", ["vide", E("starts")], [poser("vide", True)]],
                ajouter("listes", E("starts"))]],
            ["si_alors", ["non", E("vide")], [
                ["produit"],
                ["pour", "$co", E("combos"), [
                    ["si_alors", ["tous", "$n", ["intervalle", 0, ["longueur", T("$r", "g")]],
                                  ["motif_ok", ["elem", T("$r", "g"), "$n"], "$d", ["elem", ["elem", "$co", "$n"], 0],
                                   ["elem", ["elem", "$co", "$n"], 1]]],
                     [poser("cmds", ["+", E("cmds"), T("$r", "cmds")]),
                      ["pour", "$n", ["intervalle", 0, ["longueur", T("$r", "d")]], [
                          ["remplacer_motif", ["elem", T("$r", "g"), "$n"], ["elem", T("$r", "d"), "$n"], "$d",
                           ["elem", "$co", "$n"]]]]]]]]]]]]]),
    # groupes de règles jusqu'au point fixe (≤ 200 passages par groupe, comme psmoteur)
    "regles_ps": mot(["$G"], [
        ["pour", "$g", "$G", [
            poser("gch", True),
            ["tant_que", E("gch"), [poser("gch", False), ["pour", "$r", "$g", [["appliquer", "$r"]]]], 200]]],
    ]),
    "mouvements": mot([], [
        poser("bouge", True),
        ["tant_que", E("bouge"), [
            poser("bouge", False),
            ["pour", "$s", ["trier", ["filtrer", "$s", ["objets", {}], ["bouge_ok", "$s"]], "$s", ["cle_case", "$s"]], [
                ["si_alors", ["et", ["bouge_ok", "$s"], ["peut_aller", "$s"]], [
                    ["deplacer", "$s", ["*", dx(["attr", "$s", "m"]), E("C")], ["*", dy(["attr", "$s", "m"]), E("C")]],
                    ["poser_attr", "$s", "m", N], poser("bouge", True)]]]]], 100000],
        ["pour", "$s", ["filtrer", "$s", ["objets", {}], ["!=", ["attr", "$s", "m"], N]], [["poser_attr", "$s", "m", N]]],
    ]),
    "pos_joueurs": mot([], [
        poser("pj", L()),
        ["pour", "$s", ["trier", ["joueurs"], "$s", ["cle_case", "$s"]],
         [ajouter("pj", ["+", ["*", ["cy", "$s"], E("W")], ["cx", "$s"]])]],
    ]),
    "signature": mot([], [
        poser("sig", L()),
        ["pour", "$s", ["trier", ["objets", {}], "$s", ["cle_case", "$s"]],
         [ajouter("sig", L(["cle_case", "$s"], ["nom", "$s"]))]],
    ]),
    "fin_tour": mot([], [
        ["mouvements"],
        ["regles_ps", E("GTARD")],
        ["si_alors", ["contient", E("cmds"), "cancel"], [["restaurer", "sauve"], poser("fini", True)], [
            ["si_alors", ["contient", E("cmds"), "restart"], [["restaurer", "depart"], poser("fini", True)], [
                ["pos_joueurs"],
                ["si_alors", ["et", E("RPM"), ["!=", E("act"), N], ["=", E("pj"), E("pj0")]],
                 [["restaurer", "sauve"], poser("fini", True)], [
                    ["si_alors", ["ou", ["contient", E("cmds"), "win"], ["gagne_ps"]], [["niveau_suivant"], poser("fini", True)], [
                        ["si_alors", E("AGAIN"), [["signature"]]],
                        ["si_alors", ["ou", ["non", ["contient", E("cmds"), "again"]], ["=", E("sig"), E("sig0")]],
                         [poser("fini", True)], [poser("act", N)]]]]]]]]]],
    ]),
    "iteration": mot([], [
        ["si_alors", E("AGAIN"), [["signature"], poser("sig0", E("sig"))]],
        ["instantane", "sauve"],
        ["si_alors", ["!=", E("act"), N], [["pour", "$s", ["joueurs"], [["poser_attr", "$s", "m", E("act")]]]]],
        ["pos_joueurs"], poser("pj0", E("pj")),
        poser("cmds", L()),
        ["regles_ps", E("GTOT")],
        ["si_alors", ["contient", E("cmds"), "cancel"], [["restaurer", "sauve"], poser("fini", True)], [["fin_tour"]]],
    ]),
    "tour": mot(["$a"], [
        poser("act", "$a"), poser("fini", False),
        ["tant_que", ["non", E("fini")], [["iteration"]], 50],
    ]),
    # ---- début de niveau : données du jeu analysé (section « niveau ») et géométrie du rendu (runtime_ps._dessiner)
    "init": mot([], [
        poser("W", ["param", "w"]), poser("H", ["param", "h"]),
        poser("C", ["//", 64, si([">", ["param", "w"], ["param", "h"]], ["param", "w"], ["param", "h"])]),
        poser("C", si([">", E("C"), 5], 5, si(["<", E("C"), 1], 1, E("C")))),
        poser("OX", ["//", ["-", 64, ["*", E("C"), E("W")]], 2]),
        poser("OY", ["//", ["-", 64, ["*", E("C"), E("H")]], 2]),
        *[poser(k, ["param", k.lower()]) for k in ("REL", "DIRS", "COUCHE", "FOND", "JOUEURS", "VICT", "GTOT", "GTARD", "RPM",
                                                     "MOD", "NOMS")],
        poser("KFOND", T(E("COUCHE"), E("FOND"))),
        poser("AGAIN", ["existe", "$g", ["+", E("GTOT"), E("GTARD")], ["existe", "$r", "$g", ["contient", T("$r", "cmds"), "again"]]]),
        # pixels sondes (glouton, ≤ 3) : chaque objet dessiné doit avoir un pixel opaque sur une sonde ; les autres → INVIS
        poser("U0", ["filtrer", "$o", E("NOMS"), ["!=", "$o", E("FOND")]]),
        poser("INVIS", ["filtrer", "$o", E("U0"), ["=", ["premier_opaque", "$o"], N]]),
        poser("U0", ["filtrer", "$o", E("U0"), ["!=", ["premier_opaque", "$o"], N]]),
        *[x for i in (1, 2, 3) for x in (
            poser(f"P{i}", ["premier_opaque", ["premier", E(f"U{i - 1}")]]),
            poser(f"U{i}", si(["=", E(f"P{i}"), N], L(), ["filtrer", "$o", E(f"U{i - 1}"), ["non", ["opaque", "$o", E(f"P{i}")]]])))],
        poser("INVIS", ["+", E("INVIS"), E("U3")]),
        ["instantane", "depart"],
    ]),
}

ACTIONS = {"UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right", "SPACE": "action"}

PROGRAMME = {
    "etat": {},
    "mots": {**MOTS, **{k: dict(v, sorte="effet") for k, v in EFFETS.items()}},
    "au_debut": [["init"]],
    "regles": [{"nom": "tour PuzzleScript", "quand": ["contient", L(*ACTIONS), ["action"]],
                "alors": [["tour", ["table", ACTIONS, ["action"]]]]}],
}

# v2 (CCM-229/230-A) : le mot natif objets_dans_boite rend les objets d'une case, transparents compris, en un appel
V2 = "--v2" in __import__("sys").argv
if V2:
    # sprite de moins de c lignes ou colonnes (p126 : joueur dessiné sur 4 lignes) : pixel hors dessin = None, non opaque
    PROGRAMME["mots"]["opaque"] = mot(["$o", "$q"], ["et", ["!=", ["pixel", T(E("MOD"), "$o"), ["%", "$q", E("C")], ["//", "$q", E("C")]], N],
                                                        [">=", ["pixel", T(E("MOD"), "$o"), ["%", "$q", E("C")], ["//", "$q", E("C")]], 0]])
    PROGRAMME["mots"]["objs_px"] = mot(["$X", "$Y"], ["objets_dans_boite", "$X", "$Y", E("C"), E("C")])

if __name__ == "__main__":
    (ICI / ("interpreteur_ps_v2.json" if V2 else "interpreteur_ps.json")).write_text(json.dumps(PROGRAMME, ensure_ascii=False, indent=1))
    from chrysalide.arc3.langage import Programme
    Programme(PROGRAMME)  # vérification à la définition (portée, récursion, arités)
    print("interpreteur_ps.json :", len(json.dumps(PROGRAMME)), "caractères,", len(PROGRAMME["mots"]), "mots")
