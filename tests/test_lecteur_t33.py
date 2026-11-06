# SPDX-License-Identifier: MIT-0
"""CW-153 : lecteur tolérant et sauvetage (experiments/T3.3/lecteur.py), sur un vrai programme du langage (sp80)."""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "experiments/T3.3"))
import lecteur as L

_P = json.loads((R / "experiments/T3.1/regles/sp80.json").read_text())  # programme réel, versionné, plusieurs lois
VRAI = {"etat": _P["etat"], "regles": _P["regles"]}
TXT = json.dumps(VRAI, ensure_ascii=False, indent=1)


def test_strict_inchange():
    assert L.lire(TXT) == (VRAI, "complete")


def test_balises_et_texte_autour():
    p, mode = L.lire("Voici :\n```json\n" + TXT + "\n```\nFin.")
    assert p == VRAI and mode == "complete"  # l'ancien lecteur savait déjà retirer balises et texte


def test_virgules_finales():
    abime = TXT.replace("]\n}", "],\n}", 1)
    p, mode = L.lire(abime)
    assert mode == "toleree" and p["regles"] == VRAI["regles"]


def test_guillemets_simples():
    p, mode = L.lire("{'etat': {}, 'regles': [{'nom': 'r', 'quand': true, 'alors': []}]}")
    assert mode == "toleree" and p["regles"][0]["nom"] == "r"


def test_plusieurs_blocs_fusionnes():
    a = {"etat": {"x": 1}, "regles": [{"nom": "a"}]}
    b = {"etat": {"y": 2}, "regles": [{"nom": "b"}]}
    p, mode = L.lire("bloc 1 " + json.dumps(a) + " puis bloc 2 " + json.dumps(b) + " fin")
    assert mode == "toleree" and [r["nom"] for r in p["regles"]] == ["a", "b"] and p["etat"] == {"x": 1, "y": 2}


def test_coupe_garde_les_lois_completes():
    n = len(VRAI["regles"])
    assert n >= 1
    coupe = TXT[: TXT.rfind("}", 0, len(TXT) - 10) - 5]  # coupé au milieu de la dernière loi
    p, mode = L.lire(coupe)
    assert mode == "sauvee" and 1 <= len(p["regles"]) <= n
    assert all(r in VRAI["regles"] for r in p["regles"])  # aucune loi inventée ni modifiée


def test_sauvetage_dans_la_reflexion():
    p, mode = L.lire("", pensee="Je propose : " + TXT[: len(TXT) - 3])
    assert mode == "sauvee" and all(r in VRAI["regles"] for r in p["regles"])


def test_non_extractible():
    assert L.lire("je ne sais pas", pensee="rien") == (None, "non_extractible")
