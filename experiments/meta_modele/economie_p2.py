# SPDX-License-Identifier: MIT-0
"""CW-324 P2 (B) : ajoute le BUDGET DE COUPS et sa DÉFAITE aux programmes exacts qui ne l'ont pas (audit CW-321,
`audit.json`, 14 jeux). Valeurs lues dans le code source des jeux (`lecture_*.json`), puis contrôlées dans le vrai jeu
(`budget_reel.py --programme`). Ajout identique partout, en 3 morceaux marqués « CW-324 P2 » :
  section "niveau" : {"<indice 0..>": {"budget_coups": B}} (B = coups comptés jusqu'à la défaite, ce coup compris) ;
  "au_debut" : budget_restant ← param budget_coups (remis au plein à chaque niveau, et à chaque RESET) ;
  1ʳᵉ règle (puis continuer) : une action comptée consomme 1 ; à 0, perdre. Les règles du jeu s'appliquent APRÈS : un
  coup gagnant écrit l'issue « niveau » par-dessus « defaite » (la victoire prime, comme dans les 9 jeux de l'audit).
Ce qui n'est PAS décrit (noté par jeu dans `NOTES`) : coûts différents de 1, coups gratuits par cas, recharges.
Usage : uv run python experiments/meta_modele/economie_p2.py [jeu…] (défaut : les 14) ; idempotent."""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
REG = R / "experiments/T3.1/regles"
MARQUE = "CW-324 P2"
F = ["UP", "DOWN", "LEFT", "RIGHT"]
# jeu : (actions comptées, budgets par niveau 1..n) ; CLIC_OBJET : un clic ne compte que s'il touche un objet
# jeu : (règle APRÈS laquelle décompter, condition) — quand le programme sait déjà si le coup est « réel » (ar25 : la
# règle `fleche` pose but_teste sur un vrai mouvement dans la vue ; `contexte` le remet à faux à chaque coup)
# su15 (source, `axaxyjxqoe`) : un clic ne compte que sur les rangées 10 à 62 de la grille (plateau) ; ailleurs, gratuit
DANS_VUE = {"su15"}
APRES = {"ar25": ("fleche", ["ou", ["=", ["action"], "SPACE"],
                             ["et", ["contient", ["liste", *F], ["action"]], ["etat", "but_teste"]]])}
CLIC_OBJET = {"sb26"}
# ft09 (source, étape du clic) : un clic COÛTE s'il tombe sur une case de jeu (sprite tagué Hkx ou NTi) ou HORS de la
# grille (display_to_grid → None) ; un clic sur une case VIDE de la grille est gratuit (CCM-067-E : (0, 0) gratuit)
QUAND_SPECIAL = {"ft09": ["et", ["=", ["action"], "CLICK"],
                          ["ou", ["=", "$cc", None],
                           ["existe", "$o", ["a", ["elem", "$cc", 0], ["elem", "$cc", 1]],
                            ["ou", ["a_tag", "$o", "Hkx"], ["a_tag", "$o", "NTi"]]]]]}  # su15 : pire (4/12 contre 8/12), décompte simple gardé
SPEC = {
    "re86": (F + ["SPACE"], [100, 100, 200, 200, 250, 200, 300, 400]),
    "ka59": (F + ["CLICK"], [100, 127, 100, 127, 100, 150, 200]),
    "m0r0": (F + ["SPACE", "CLICK", "UNDO"], [151] * 6),
    "tr87": (F, [128] * 5 + [256]),
    "dc22": (F + ["CLICK"], [128, 192, 192, 192, 512, 1024]),
    "sc25": (F, [52, 26, 51, 36, 66, 61]),  # N1 : 52 MESURÉ (la lecture donnait slfh + 1 = 51)
    "su15": (["CLICK"], [32, 32, 48, 48, 32, 32, 32, 48, 48]),
    "sp80": (F + ["SPACE", "CLICK", "UNDO"], [30, 45, 100, 120, 100, 120]),
    "bp35": (["LEFT", "RIGHT", "SPACE", "CLICK", "UNDO"], [64] * 6 + [128] * 3),
    "ar25": (F + ["SPACE"], [64, 64, 128, 128, 128, 320, 320, 320]),
    "ft09": (["CLICK"], [32, 32, 96, 96, 128, 128]),
    "tn36": (["CLICK"], [61] * 5 + [122] * 2),
    "r11l": (F + ["SPACE", "CLICK", "UNDO"], [60] * 6),
    "sb26": (["SPACE", "CLICK"], [64] * 8),
}
NOTES = {
    "dc22": "clic sur un bouton buezna -2, chute -20, prise ratée gratuite : non décrits",
    "sc25": "défaite à used > slfh ; clics de bascule et sorts comptés, recharge +10 (enjehv-pahtoz), coup qui atteint la "
            "sortie gratuit : non décrits",
    "su15": "fusion interdite 2+2×pénalité, annulation gratuite : non décrites",
    "sp80": "décompte seulement en mode 'change' : non décrit",
    "ar25": "décompte après `fleche` (vrai mouvement) ; clic et annulation gratuits",
    "ft09": "clic sur une case vide gratuit : non décrit",
    "tn36": "niveaux 6-7 : 1 px tous les 2 clics ; défaite au coup suivant : à contrôler",
    "sb26": "sélection, désélection gratuites ; défaite en fin d'animation : non décrites",
    "bp35": "RESET remet à 0 (comme le début de niveau)",
}


def patcher(jeu):
    f = REG / f"{jeu}.json"
    brut = f.read_text()
    t = json.loads(brut)
    if MARQUE in brut:  # refait : l'ajout précédent est retiré d'abord (idempotent)
        t["regles"] = [r for r in t["regles"] if MARQUE not in r.get("nom", "")]
        t["au_debut"] = [e for e in t.get("au_debut", []) if e != ["poser", "budget_restant", ["param", "budget_coups"]]]
        t["contournements_restants"] = [c for c in t.get("contournements_restants", []) if MARQUE not in c.get("quoi", "")]
    acts, budgets = SPEC[jeu]
    sec = t.setdefault("niveau", {})
    for i, b in enumerate(budgets):
        sec.setdefault(str(i), {})["budget_coups"] = b
    sec.setdefault("*", {}).setdefault("budget_coups", budgets[-1])  # niveau au-delà de la liste : dernier budget
    t.setdefault("etat", {})["budget_restant"] = budgets[0]
    t["au_debut"] = [["poser", "budget_restant", ["param", "budget_coups"]]] + list(t.get("au_debut", []))
    regle = {"nom": f"budget de coups ({MARQUE}) : une action comptée consomme 1 ; à 0, perdu (la victoire, "
                           "testée ensuite, prime)",
                    "soit": {"cc": ["case_clic"]},
                    "quand": (["ou", ["contient", ["liste", *[x for x in acts if x != "CLICK"]], ["action"]],
                               ["et", ["=", ["action"], "CLICK"], ["!=", "$cc", None],
                                ["non", ["vide", ["a", ["elem", "$cc", 0], ["elem", "$cc", 1]]]]]]
                              if jeu in CLIC_OBJET else ["contient", ["liste", *acts], ["action"]]),
                    "alors": [["consommer", "budget_restant", 1],
                              ["si_alors", ["<=", ["etat", "budget_restant"], 0], [["perdre"]]]],
                    "puis": "continuer"}
    if jeu in QUAND_SPECIAL:
        regle["quand"] = QUAND_SPECIAL[jeu]
    if jeu in DANS_VUE:
        regle["quand"] = ["et", ["=", ["action"], "CLICK"], ["!=", "$cc", None],
                          ["<=", 10, ["elem", "$cc", 1]], ["<", ["elem", "$cc", 1], 63]]
    if jeu in APRES:
        nom, cond = APRES[jeu]
        regle["quand"] = cond
        i = next(k for k, r in enumerate(t["regles"]) if r.get("nom") == nom) + 1
        t["regles"] = t["regles"][:i] + [regle] + t["regles"][i:]
    else:
        t["regles"] = [regle] + t["regles"]
    if jeu in NOTES:
        t.setdefault("contournements_restants", []).append({"quoi": f"{MARQUE} : budget simplifié",
                                                            "pourquoi": NOTES[jeu]})
    compact = "\n" not in brut.strip()
    f.write_text(json.dumps(t, ensure_ascii=False) if compact else json.dumps(t, ensure_ascii=False, indent=1) + "\n")
    return "ajouté"


if __name__ == "__main__":
    for j in sys.argv[1:] or SPEC:
        print(j, patcher(j))
