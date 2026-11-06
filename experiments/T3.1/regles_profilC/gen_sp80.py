# SPDX-License-Identifier: MIT-0
"""CW-112 : écrit sp80.json en PROFIL C (gabarits fixes, paramètres finis). Les gabarits répétés (décalages, itérations)
sont déroulés ici ; le JSON produit est la seule chose exécutée. Usage : uv run python experiments/T3.1/regles_profilC/gen_sp80.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atomiser import atomiser

BARRE, COUPE = "plzwjbfyfli", "repwkzbkhxl"
BLOQUEURS = ["bodekplurlf16", "bodekplurlf20", "liolfvkveqg", "repwkzbkhxl", "sowlljgtjvn", "waoewejnqzc"]  # par nom
VEC = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
N_ITER, L_MAX = 5, 7  # pièces d'un niveau, largeur max d'une barre (domaines finis vus)
SEL = ["premier", ["objets", {"tag": BARRE, "couleur": 9, "visible": True}]]
LIBRE8 = ["premier", ["objets", {"tag": BARRE, "couleur": 8, "visible": True}]]


def ex(var, classe, cond=True):
    return ["existe", var, ["objets", classe], cond]


R = []
# 1. orientation du niveau (rotation 180 : cadre 16 et au moins 3 coupes visibles ; cadre 20 et un seul déviateur)
R.append({"nom": "rot par défaut", "alors": [["poser", "rot", 0]], "puis": "continuer"})
C = {"tag": COUPE, "visible": True}
R.append({"nom": "rot 16 : 3 coupes", "quand": ["et", ex("$f", {"nom": "bodekplurlf16"}),
          ex("$a", C, ex("$b", C, ex("$c", C, ["et", ["!=", "$a", "$b"], ["!=", "$a", "$c"], ["!=", "$b", "$c"]])))],
          "alors": [["poser", "rot", 16]], "puis": "continuer"})
D = {"tag": "tuvkdkhdokr", "visible": True}
R.append({"nom": "rot 20 : un seul déviateur", "quand": ["et", ex("$f", {"nom": "bodekplurlf20"}),
          ex("$a", D, ["non", ex("$b", D, ["!=", "$a", "$b"])])], "alors": [["poser", "rot", 20]], "puis": "continuer"})

# 2. flèches : la barre sélectionnée avance d'une case si (a) y reste ≥ 3, (b) sa boîte n'entre pas dans la boîte d'une
#    coupe élargie de 1 (= aucun pixel de coupe dans le voisinage 3×3 de la destination), (c) aucun bloqueur au pixel.
for a, (dx0, dy0) in VEC.items():
    for rot in (0, 1):
        dx, dy = (-dx0, -dy0) if rot else (dx0, dy0)
        q = ["et", ["=", ["action"], a], ["=", ["etat", "rot"], 0] if not rot else ["!=", ["etat", "rot"], 0], ["!=", "$s", None]]
        if dy == -1:
            q.append(["!=", ["y", "$s"], 3])
        q += [["libre", "$s", dx + ex_, dy + ey, {"tag": COUPE}] for ex_ in (-1, 0, 1) for ey in (-1, 0, 1)]
        q += [["libre", "$s", dx, dy, {"nom": n}] for n in BLOQUEURS]
        R.append({"nom": f"{a} {'tourné' if rot else 'droit'}", "soit": {"s": SEL}, "quand": q,
                  "alors": [["deplacer", "$s", dx, dy]]})

# 3. clic : on parcourt les barres non sélectionnées une à une (premier de la classe couleur 8, puis marquée 7) ; la
#    barre dont une case est cliquée est marquée 10 (« choisie »). Marques 7 retirées, puis l'ancienne sélection est
#    relâchée et la choisie devient la sélection.
CHOISIE = ["premier", ["objets", {"tag": BARRE, "couleur": 10}]]
for k in range(N_ITER):
    for rot in (0, 16):
        for i in range(L_MAX):
            if rot == 0:
                case = ["liste", ["x", "$o"] if i == 0 else ["+", ["x", "$o"], i], ["y", "$o"]]
            else:
                case = ["liste", ["-", rot - 1 - i, ["x", "$o"]], ["-", rot - 1, ["y", "$o"]]]
            q = ["et", ["=", ["action"], "CLICK"], ["=", ["etat", "rot"], rot], ["!=", "$o", None],
                 ["non", ex("$n", {"tag": BARRE, "couleur": 10})]] + [["!=", ["largeur", "$o"], w] for w in range(1, i + 1)] + \
                [["=", ["case_clic"], case]]
            R.append({"nom": f"clic it{k} rot{rot} case+{i}", "soit": {"o": LIBRE8}, "quand": q,
                      "alors": [["recolorer", "$o", 8, 10]], "puis": "continuer"})
    R.append({"nom": f"clic it{k} : barre suivante", "soit": {"o": LIBRE8},
              "quand": ["et", ["=", ["action"], "CLICK"], ["!=", "$o", None]],
              "alors": [["recolorer", "$o", 8, 7]], "puis": "continuer"})
R.append({"nom": "clic : marques retirées", "quand": ["=", ["action"], "CLICK"],
          "alors": [["pour", "$p", ["objets", {"tag": BARRE, "couleur": 7}], [["recolorer", "$p", 7, 8]]]], "puis": "continuer"})
R.append({"nom": "clic : la choisie devient la sélection", "soit": {"s": SEL, "n": CHOISIE},
          "quand": ["et", ["=", ["action"], "CLICK"], ["!=", "$n", None]],
          "alors": [["calque", "$s", 0], ["recolorer", "$s", 9, 8], ["calque", "$n", 1], ["recolorer", "$n", 10, 9]]})

# 4. SPACE : écoulement raté (le réussi change de niveau, non mesuré) → l'ancienne sélection est relâchée, puis la barre la
#    plus proche de l'origine (min x²+y², 1re en cas d'égalité) est sélectionnée. Seule règle hors profil (argmin calculé).
R.append({"nom": "versement : relâcher", "soit": {"s": SEL}, "quand": ["=", ["action"], "SPACE"],
          "alors": [["calque", "$s", 0], ["recolorer", "$s", 9, 8]], "puis": "continuer"})
R.append({"nom": "versement : plus proche de l'origine (HORS PROFIL)", "quand": ["=", ["action"], "SPACE"],
          "soit": {"b": ["premier", ["trier", ["objets", {"tag": BARRE, "visible": True}], "$o",
                                     ["+", ["*", ["x", "$o"], ["x", "$o"]], ["*", ["y", "$o"], ["y", "$o"]]]]]},
          "alors": [["calque", "$b", 1], ["recolorer", "$b", 8, 9]]})

R = atomiser(R)
prog = {"etat": {"rot": 0, "t": False}, "regles": R,
        "notes": ["Lois atomiques (CW-113/114) : une précondition → un effet (atomiser.py). Réécriture profil C de regles/sp80.json (CW-112). Déviateurs (tuvkdkhdokr) absents de la trace : seule la "
                  "détection de rotation les lit ; leurs gabarits seraient les mêmes que ceux des barres, par classe.",
                  "Clic : sans liaison par position, la barre cliquée est trouvée par itération déroulée sur la classe "
                  "(premier de la classe couleur 8, marquée 7 ensuite ; la cliquée marquée 10) : N_ITER × largeurs × orientations gabarits."],
        "primitives_manquantes": [
            {"nom": "argmin(classe, clé)", "mecanique": "après un versement raté, sélection de la pièce la plus proche de "
             "l'origine (min x²+y²)", "pourquoi": "demande un tri ou une comparaison d'une quantité calculée (x², <) entre "
             "objets d'une même classe ; aucun atome à paramètres finis ne l'exprime"},
            {"nom": "objet_a(case_clic) ou contient_case(o, case)", "mecanique": "choisir l'objet cliqué parmi plusieurs de "
             "même classe", "pourquoi": "exprimable seulement par itération déroulée + marquage temporaire (gabarits × "
             "itérations × décalages) : exact mais verbeux ; une liaison « objet sous le clic » le rendrait direct"}],
        "mots_manquants": []}
Path(__file__).with_name("sp80.json").write_text(json.dumps(prog, ensure_ascii=False))
print(len(R), "règles")
