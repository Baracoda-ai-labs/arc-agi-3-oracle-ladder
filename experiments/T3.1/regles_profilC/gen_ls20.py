# SPDX-License-Identifier: MIT-0
"""CW-112 : écrit ls20.json en PROFIL C (gabarits fixes, paramètres finis). Les gabarits répétés (directions, décalages,
distances, valeurs de jauge, itérations sur une classe) sont déroulés ici ; le JSON produit est la seule chose exécutée.
Usage : uv run python experiments/T3.1/regles_profilC/gen_ls20.py"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from atomiser import atomiser

J, K, MUR, PORTE, MODELE, CADRE = "sfqyzhzkij", "wgmbtyhvbc", "ihdgageizm", "rjlbuycveu", "kvynsvxbpi", "vjotnebuqo"
IND_PORTE, IND_CLE, RECH, POUSSOIR = "hoswmpiqkw", "ghizzeqtoh", "npxgalaybz", "gbvqrjtaqo"
M_FORME, M_COUL, M_ROT, CADRE_IND = "ttfwljgohq", "soyhouuebz", "rhsxkxzdjz", "vfkkzdgxzx"
MASQUES = [[[0, 0, -1], [-1, 0, 0], [0, -1, 0]], [[-1, 0, -1], [-1, 0, -1], [0, 0, 0]], [[0, -1, 0], [0, -1, 0], [0, 0, 0]],
           [[-1, 0, 0], [0, -1, 0], [-1, 0, -1]], [[-1, 0, -1], [0, 0, -1], [-1, 0, 0]], [[0, 0, 0], [-1, -1, 0], [0, -1, 0]]]
COULEURS = [12, 9, 14, 8]
MARQUE = {12: 2, 9: 3, 14: 6, 8: 7}  # couleur temporaire d'un objet déjà parcouru (absente des objets marqués)
VEC = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
POUSSOIRS = {"kapcaakvb_b": (0, 1), "lujfinsby_t": (0, -1), "yjgargdic_r": (1, 0), "tihiodtoj_l": (-1, 0)}  # noms vus
# décalage (x, y) mod 5 de chaque poussoir vu par rapport à la grille du joueur (x ≡ 4, y ≡ 0 mod 5)
MOD_POUSSOIR = {"kapcaakvb_b": (4, 4), "lujfinsby_t": (4, 1), "yjgargdic_r": (3, 0), "tihiodtoj_l": (0, 0)}
OFFS_MUR = [(0, 0), (0, 4)]  # origines de murs vues dans une case (niveau 2 : un mur à y ≡ 4)
# Niveaux vus dans la trace (lus sur la scène initiale) : position du modèle (identifie le niveau), cran de jauge,
# départ du joueur, motif 3×3 de la clé et du modèle.
NIVEAUX = [
    {"modele": (35, 11), "cran": 1, "j0": (34, 45), "cle": [[9, 9, 9], [9, -1, -1], [9, -1, 9]], "mod": [[9, 9, 9], [-1, -1, 9], [9, -1, 9]]},
    {"modele": (15, 41), "cran": 2, "j0": (29, 40), "cle": [[9, 9, 9], [-1, -1, 9], [9, -1, 9]], "mod": [[9, 9, 9], [9, -1, -1], [9, -1, 9]]},
    {"modele": (55, 51), "cran": 2, "j0": (9, 45), "cle": [[12, 12, 12], [-1, -1, 12], [12, -1, 12]], "mod": [[9, -1, 9], [9, -1, -1], [9, 9, 9]]},
    {"modele": (10, 6), "cran": 1, "j0": (54, 5), "cle": [[-1, 14, -1], [14, 14, -1], [-1, 14, 14]], "mod": [[9, 9, 9], [-1, -1, 9], [9, -1, 9]]},
]
JAUGE, N_RECH, N_PORTE, K_MAX = 42, 2, 2, 11


def attributs(motif):
    p = np.asarray(motif)
    c = int(p[p >= 0][0])
    for f, m in enumerate(MASQUES):
        for q in range(4):
            if np.array_equal(np.rot90(np.asarray(m), -q) >= 0, p >= 0):
                return f, q, c
    raise ValueError(motif)


SJ = {"j": ["premier", ["objets", {"tag": J}]], "k": ["premier", ["objets", {"tag": K}]]}
G = ["=", ["etat", "fini"], False]


def E(n, v):
    return ["=", ["etat", n], v]


def rel(axe, var, d):
    return [axe, var] if d == 0 else ["+", [axe, var], d]


def en(var, ox, oy, ref="$j"):
    """origine de var = origine de ref + (ox, oy)."""
    return ["et", ["=", ["x", var], rel("x", ref, ox)], ["=", ["y", var], rel("y", ref, oy)]]


def ex(var, classe, cond=True):
    return ["existe", var, ["objets", classe], cond]


def conf(p):
    """La porte p est conforme : son modèle (case p + 1) a la forme, la rotation et la couleur de la clé."""
    return ex("$m", {"tag": MODELE, "visible": True}, ["et", en("$m", 1, 1, p), ["=", ["attr", "$m", "f"], ["etat", "f"]],
              ["=", ["attr", "$m", "q"], ["etat", "q"]], ["=", ["attr", "$m", "c"], ["etat", "c"]]])


def regle(nom, quand, alors, soit=None):
    r = {"nom": nom, "soit": dict(soit or SJ), "quand": quand, "alors": alors, "puis": "continuer"}
    return r


def iterer(nom, classe, couleur, n, garde, cond, effets):
    """Objet de la classe vérifiant cond($o) : parcours déroulé (premier de la classe, puis marqué d'une couleur
    temporaire), marques retirées à la fin."""
    cl = dict(classe, couleur=couleur)
    soit = dict(SJ, o=["premier", ["objets", cl]])
    out = []
    for i in range(n):
        out.append(regle(f"{nom} : objet {i}", ["et", *garde, ["!=", "$o", None], cond], effets, soit))
        out.append(regle(f"{nom} : suivant {i}", ["et", *garde, ["!=", "$o", None]], [["recolorer", "$o", couleur, MARQUE.get(couleur, 7)]], soit))
    out.append(regle(f"{nom} : marques retirées", True,
                     [["pour", "$p", ["objets", dict(classe, couleur=MARQUE.get(couleur, 7))], [["recolorer", "$p", MARQUE.get(couleur, 7), couleur]]]]))
    return out


def case(garde, s):
    """Effets de la case où se trouve le joueur : recharge, modificateurs de forme, de couleur, de rotation."""
    out = iterer(f"recharge{s}", {"tag": RECH, "visible": True}, 11, N_RECH, garde, en("$o", 1, 1),
                 [["poser", "rech", True], ["poser", "jauge", JAUGE], ["montrer", "$o", False]])
    for f in range(6):
        out.append(regle(f"forme suivante{s} f={f}", ["et", *garde, E(f"dF{s}", False), ex("$o", {"tag": M_FORME}, en("$o", 0, 0)), E("f", f)],
                         [["poser", "f", (f + 1) % 6], ["poser", f"dF{s}", True], ["poser", "redessin", True], ["poser", "modif", True]]))
    for i, c in enumerate(COULEURS):
        n = COULEURS[(i + 1) % 4]
        out.append(regle(f"couleur suivante{s} c={c}", ["et", *garde, E(f"dC{s}", False), ex("$o", {"tag": M_COUL}, en("$o", 0, 0)), E("c", c)],
                         [["recolorer", "$k", c, n], ["poser", "c", n], ["poser", f"dC{s}", True], ["poser", "modif", True]]))
    for q in range(4):
        out.append(regle(f"rotation{s} q={q}", ["et", *garde, E(f"dR{s}", False), ex("$o", {"tag": M_ROT}, en("$o", 0, 0)), E("q", q)],
                         [["poser", "q", (q + 1) % 4], ["poser", f"dR{s}", True], ["poser", "redessin", True], ["poser", "modif", True]]))
    return out


R = []
DRAPEAUX = ["fini", "bloque", "rech", "modif", "epuise", "gagne", "pousse", "redessin", "mort", "dF1", "dC1", "dR1", "dF2", "dC2", "dR2"]
R.append(regle("coup : drapeaux remis", True, [["poser", d, False] for d in DRAPEAUX]))
for L, nv in enumerate(NIVEAUX):
    f0, q0, c0 = attributs(nv["cle"])
    fm, qm, cm = attributs(nv["mod"])
    R.append(regle(f"début du niveau {L} (modèle en {nv['modele']})",
                   ["et", ["debut_niveau"], ex("$m", {"tag": MODELE}, ["et", ["=", ["x", "$m"], nv["modele"][0]], ["=", ["y", "$m"], nv["modele"][1]]])],
                   [["poser", "niv", L], ["poser", "cran", nv["cran"]], ["poser", "vies", 3], ["poser", "jauge", JAUGE],
                    ["poser", "f", f0], ["poser", "q", q0], ["poser", "c", c0],
                    ["poser_attr", "$m", "f", fm], ["poser_attr", "$m", "q", qm], ["poser_attr", "$m", "c", cm]],
                   dict(SJ, m=["premier", ["objets", {"tag": MODELE}]])))
R.append(regle("hors flèche : rien", ["et", G, *[["!=", ["action"], a] for a in VEC]], [["poser", "fini", True]]))
for a, (dx, dy) in VEC.items():
    R.append(regle(f"{a} : porte non conforme, pause", ["et", G, ["=", ["action"], a],
                   ex("$p", {"tag": PORTE, "visible": True}, ["et", en("$p", 5 * dx, 5 * dy), ["non", conf("$p")]])], [["poser", "fini", True]]))
    for ox, oy in OFFS_MUR:
        R.append(regle(f"{a} : mur (+{ox},+{oy})", ["et", G, ["=", ["action"], a], ex("$w", {"tag": MUR}, en("$w", 5 * dx + ox, 5 * dy + oy))],
                       [["poser", "bloque", True]]))
    R.append(regle(f"{a} : avancer", ["et", G, ["=", ["action"], a], E("bloque", False)], [["deplacer", "$j", 5 * dx, 5 * dy]]))
R += case([G, E("bloque", False)], "1")
R.append(regle("niveau 1 : clé devenue conforme, pause (indice)",
               ["et", G, E("niv", 0), E("modif", True), ex("$p", {"tag": PORTE, "visible": True}, conf("$p"))], [["poser", "fini", True]]))
for cran in (1, 2):
    for n in range(JAUGE + 1):  # ordre croissant : une règle ne voit jamais la valeur posée par une autre
        R.append(regle(f"jauge cran {cran} : {n}", ["et", G, E("rech", False), E("cran", cran), E("jauge", n)], [["poser", "jauge", n - cran]]))
for n in (-1, -2):
    R.append(regle(f"jauge épuisée ({n})", ["et", G, E("rech", False), E("jauge", n)], [["poser", "epuise", True]]))
for nom, (dx, dy) in POUSSOIRS.items():
    mx, my = MOD_POUSSOIR[nom]
    oxs = sorted({o for o in range(-4, 5) if (o - (mx - 4)) % 5 == 0})
    oys = sorted({o for o in range(-4, 5) if (o - my) % 5 == 0})
    for ox in oxs:
        for oy in oys:
            def obst(kk, tag, var, ox=ox, oy=oy, dx=dx, dy=dy):
                return ex(var, {"tag": tag}, en(var, ox + dx * (1 + 5 * kk), oy + dy * (1 + 5 * kk)))
            for k in range(2, K_MAX + 1):
                libres = [["non", obst(kk, t, "$w")] for kk in range(1, k) for t in (MUR, PORTE)]
                for t in (MUR, PORTE):
                    R.append(regle(f"poussoir {nom} en ({ox},{oy}) : obstacle ({t[:4]}) à {k}",
                                   ["et", G, E("epuise", False), E("pousse", False), ex("$p", {"tag": POUSSOIR, "nom": nom}, en("$p", ox, oy)),
                                    *libres, obst(k, t, "$w")],
                                   [["deplacer", "$j", dx * 5 * (k - 1), dy * 5 * (k - 1)], ["poser", "pousse", True]]))
R += case([G, E("pousse", True)], "2")
R.append(regle("après poussée : fin du coup", ["et", G, E("pousse", True)], [["poser", "fini", True]]))
R += iterer("victoire : porte", {"tag": PORTE, "visible": True}, 5, N_PORTE, [G], ["et", en("$o", 0, 0), conf("$o")],
            [["poser", "gagne", True], ["montrer", "$o", False]])
for c in COULEURS:
    R += iterer(f"victoire : modèle {c}", {"tag": MODELE, "visible": True}, c, N_PORTE, [G, E("gagne", True)], en("$o", 1, 1),
                [["montrer", "$o", False]])
R += iterer("victoire : cadre à indice", {"tag": CADRE_IND, "visible": True}, 5, N_PORTE, [G, E("gagne", True)], en("$o", -1, -1),
            [["poser", "indices", True], ["montrer", "$o", False]])
for t in (IND_PORTE, IND_CLE):
    R.append(regle(f"victoire : indices cachés ({t})", ["et", G, E("indices", True)],
                   [["pour", "$p", ["objets", {"tag": t, "visible": True}], [["montrer", "$p", False]]], ["poser", "indices", False]]))
R.append(regle("victoire : plus aucune porte, niveau suivant", ["et", G, E("gagne", True), ["non", ex("$p", {"tag": PORTE, "visible": True})]],
               [["niveau_suivant"], ["poser", "fini", True]]))
R.append(regle("jauge épuisée, dernière vie : défaite", ["et", G, E("epuise", True), E("vies", 1)],
               [["poser", "vies", 0], ["perdre"], ["poser", "fini", True]]))
for v in (2, 3):
    R.append(regle(f"jauge épuisée : vie perdue ({v})", ["et", G, E("epuise", True), E("vies", v)], [["poser", "vies", v - 1], ["poser", "mort", True]]))
for L, nv in enumerate(NIVEAUX):
    f0, q0, c0 = attributs(nv["cle"])
    R.append(regle(f"mort niveau {L} : clé d'origine", ["et", G, E("mort", True), E("niv", L)],
                   [["poser", "f", f0], ["poser", "q", q0], ["poser", "c", c0], ["poser", "redessin", True]]))
    R.append(regle(f"mort niveau {L} : joueur au départ (HORS PROFIL A : placer)", ["et", G, E("mort", True), E("niv", L)],
                   [["placer", "$j", nv["j0"][0], nv["j0"][1]]]))
R.append(regle("mort : jauge pleine", ["et", G, E("mort", True)], [["poser", "jauge", JAUGE]]))
for t, vis in ((RECH, True), (PORTE, True), (MODELE, True), (CADRE, True), (IND_CLE, False), (IND_PORTE, False)):
    R.append(regle(f"mort : {t} {'remontrés' if vis else 'cachés'}", ["et", G, E("mort", True)],
                   [["pour", "$p", ["objets", {"tag": t, "visible": not vis}], [["montrer", "$p", vis]]]]))
# Redessin de la clé depuis l'état (forme f, rotation q, couleur c) : motif de la forme (q = 0) écrit en couleur 7, tourné,
# recoloré. Seules règles hors profil (écrire / tourner un motif constant).
for f, m in enumerate(MASQUES):
    px = [[7 if m[dy // 2][dx // 2] == 0 else -1 for dx in range(6)] for dy in range(6)]
    R.append(regle(f"clé : motif de la forme {f} (HORS PROFIL : ecrire)", [*["et"], E("redessin", True), E("f", f)],
                   [["ecrire", "$k", dy, dx, px[dy][dx]] for dy in range(6) for dx in range(6)]))
for q in (1, 2, 3):
    R.append(regle(f"clé : rotation {q} (HORS PROFIL : tourner)", ["et", E("redessin", True), E("q", q)], [["tourner", "$k", q]]))
for c in COULEURS:
    R.append(regle(f"clé : couleur {c}", ["et", E("redessin", True), E("c", c)], [["recolorer", "$k", 7, c]]))

R = atomiser(R)
prog = {"etat": {d: False for d in DRAPEAUX} | {"t": False, "indices": False, "niv": None, "cran": 2, "vies": 3, "jauge": JAUGE, "f": None, "q": None, "c": None},
        "regles": R,
        "notes": [
            "Lois atomiques (CW-113/114) : une précondition → un effet ; règles à plusieurs effets découpées par atomiser.py. Réécriture profil C de regles/ls20.json (CW-112), banc honnête. Tables de niveau (modèle, clé, départ, cran) lues sur "
            "la scène initiale des 4 niveaux de la trace ; niveaux 5-7 (deux modèles, rails) non couverts, comme dans l'original "
            "pour les rails.",
            "Clé : état (forme, rotation, couleur) tenu dans etat ; conformité = égalité avec les attributs posés sur le modèle.",
            "Gabarits déroulés : jauge (2 × 43 valeurs), poussoirs (4 noms × 2 décalages × 10 distances × 2 classes "
            "d'obstacle), parcours d'une classe par marquage temporaire (recharges, portes, modèles)."],
        "primitives_manquantes": [
            {"nom": "poser_motif(o, motif constant) — ou ecrire à constantes", "mecanique": "modificateur de forme et remise "
             "de la clé à la mort : la clé prend le motif 3×3 suivant", "pourquoi": "aucun effet du profil ne change la forme "
             "d'un sprite (recolorer agit couleur par couleur) ; 6 règles hors profil (une par forme et par pixel en lois atomiques : 6 × 36 lois ecrire)"},
            {"nom": "tourner(o, q constant)", "mecanique": "modificateur de rotation de la clé (et rotation du motif redessiné)",
             "pourquoi": "effet à arguments constants mais absent de la liste du profil ; 3 règles hors profil"},
            {"nom": "placer(o, x, y) à constantes", "mecanique": "à la mort, le joueur revient à sa case de départ",
             "pourquoi": "deplacer à constantes ne suffit pas (position courante quelconque) ; placer est permis par le profil "
             "de C (T3.0/profil_c.py) mais pas par celui de A (chrysalide/arc3/profil_c.py) ; 4 règles"},
            {"nom": "compteur : decrementer(n, k) / comparer à une constante", "mecanique": "jauge de 42 qui baisse d'un cran "
             "par pas", "pourquoi": "exprimable en profil strict seulement en déroulant chaque valeur (86 règles) ; pas "
             "d'impossibilité, mais une primitive compteur compresserait"},
            {"nom": "objet_en(classe, case relative) — liaison par position", "mecanique": "agir sur LA recharge, LA porte, LE "
             "modèle de la case du joueur", "pourquoi": "soit ne lie que le premier d'une classe ; contourné par un parcours "
             "déroulé avec marquage de couleur temporaire (exact mais verbeux)"}],
        "mots_manquants": []}
Path(__file__).with_name("ls20.json").write_text(json.dumps(prog, ensure_ascii=False))
print(len(R), "règles")
