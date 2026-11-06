# SPDX-License-Identifier: MIT-0
"""CW-367.1 (B) : `docs/memoire_globale.json` est une vérité de diagnostic sur les jeux publics. Le candidat (`chrysalide/`)
ne doit jamais la lire : aucun fichier du paquet ne la cite."""
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]


def test_marquee_verite_de_diagnostic():
    assert json.loads((R / "docs/memoire_globale.json").read_text())["statut"].startswith("VÉRITÉ DE DIAGNOSTIC")


def test_jamais_lue_par_le_candidat():
    lecteurs = [p for p in (R / "chrysalide").rglob("*.py") if "memoire_globale" in p.read_text()]
    assert not lecteurs, f"le candidat lit la vérité de diagnostic : {lecteurs}"
