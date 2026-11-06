# SPDX-License-Identifier: MIT-0
"""CW-410 (E) : la mémoire générale lue par le moteur est SANS FUITE (aucun identifiant de jeu public ni témoin), et le
drapeau CHRYS_MEMOIRE éteint laisse l'ordre des buts identique ; allumé, il ordonne par fréquence sans rien retirer."""
import json
import re
from pathlib import Path

R = Path(__file__).resolve().parents[1]


def test_extrait_sans_identifiant_de_jeu():
    jeux = {p.name for p in (R / "experiments/arc3/environment_files").iterdir() if p.is_dir()}
    jeux |= {"cn04", "s5i5", "tu93", "vc33", "wa30"}
    texte = (R / "docs/memoire_generale.json").read_text()
    assert not re.search(r"\b(" + "|".join(sorted(jeux)) + r")\b", texte)
    d = json.loads(texte)
    assert "classes" not in d and "parametres" not in d
    assert all("jeux" not in v for v in d["lois"].values())


def _ordre(monkeypatch, valeur):
    from chrysalide.arc3 import moteur
    monkeypatch.setenv("CHRYS_MEMOIRE", valeur)
    formes = ["sortie", "remplir", "modele", "absent", "ancre", "motif_rel", "paires", "centre"]
    from chrysalide.arc3 import memoire
    cle = (lambda k: memoire.cle_forme(k, moteur.ORDRE_BUTS)) if memoire.actif() else \
        (lambda k: (moteur.ORDRE_BUTS.get(k, 9), k))
    return sorted(formes, key=cle)


def test_eteint_identique_et_allume_reordonne(monkeypatch):
    from chrysalide.arc3 import moteur
    eteint = _ordre(monkeypatch, "0")
    assert eteint == sorted(eteint, key=lambda k: (moteur.ORDRE_BUTS.get(k, 9), k))
    allume = _ordre(monkeypatch, "1")
    assert sorted(allume) == sorted(eteint)  # rien retiré
    assert allume.index("modele") < allume.index("remplir") < allume.index("sortie")  # fréquences 7 > 6 > 5


def test_candidats_buts_eteint_inchange(monkeypatch):
    """Le branchement dans _candidats_buts : drapeau éteint = même liste qu'avant (contrôle « brique débranchée »)."""
    from chrysalide.arc3 import moteur

    from chrysalide.arc3.logique.theorie import Theorie

    class Tr:  # trois classes immobiles : candidats de but génériques (remplir, sortie, ancre…)
        etats = [((1, ((0, 0),), 0, 0), (2, ((0, 0),), 3, 3), (3, ((0, 0),), 5, 5))]
        taille = (8, 8)
    th = Theorie()
    th.moves = {(1, 4): (1, 0)}  # la classe 1 est pilotée : buts « sortie », « remplir », « ancre » pour elle
    monkeypatch.setenv("CHRYS_MEMOIRE", "0")
    a = moteur._candidats_buts(th, Tr())
    monkeypatch.setenv("CHRYS_MEMOIRE", "1")
    b = moteur._candidats_buts(th, Tr())
    assert a  # le contrôle porte bien sur une liste non vide
    assert sorted(map(str, a)) == sorted(map(str, b))  # mêmes buts, seul l'ordre peut changer
