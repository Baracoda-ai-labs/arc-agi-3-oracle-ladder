# SPDX-License-Identifier: MIT-0
"""Mémoire générale du moteur (E, CW-406.6 / CW-410) : A PRIORI INTER-JEUX SANS FUITE, lu dans `docs/memoire_generale.json`
(extrait par `experiments/E_franzen/memoire_generale.py` ; aucun identifiant de jeu, garde : tests/test_memoire_generale.py).
Sous le drapeau CHRYS_MEMOIRE=1 (éteint par défaut) : ordre des formes de but par FRÉQUENCE INTER-JEUX de la loi de but
correspondante (au lieu de l'ordre écrit à la main ORDRE_BUTS, qui départage les égalités). Politiques générales
consultables par motif (`politiques`). Rien n'est retiré : l'a priori ordonne, il ne filtre jamais."""
import functools
import json
import os
from pathlib import Path

FICHIER = Path(__file__).resolve().parents[2] / "docs/memoire_generale.json"
# forme de but du moteur (Theorie._vrai) → loi de but de la mémoire
LOI_DE_FORME = {"modele": "faire correspondre un modèle visible", "motif_rel": "faire correspondre un modèle visible",
                "copie": "faire correspondre un modèle visible", "remplir": "remplir les cibles",
                "paires": "remplir les cibles", "marques": "remplir les cibles", "emboite": "remplir les cibles",
                "sortie": "sortie", "centre": "sortie", "ancre": "sortie", "sortie_si": "conditionnel",
                "absent": "réduire la population"}


def actif():
    return os.environ.get("CHRYS_MEMOIRE", "0") == "1"


@functools.lru_cache(maxsize=1)
def charger():
    try:
        return json.loads(FICHIER.read_text())
    except (OSError, ValueError):
        return {"lois": {}, "strategies": []}


def frequence(loi):
    return charger()["lois"].get(loi, {}).get("frequence", 0)


def cle_forme(forme, ordre_main):
    """Clé de tri d'une forme de but : fréquence inter-jeux décroissante, puis l'ordre écrit à la main."""
    return (-frequence(LOI_DE_FORME.get(forme, "")), ordre_main.get(forme, 9), forme)


def politiques(motifs):
    """Politiques générales dont le motif recoupe `motifs` (noms de lois observées)."""
    m = set(motifs)
    return [s for s in charger()["strategies"] if m & set(s["motif"])]
