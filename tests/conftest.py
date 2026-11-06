# SPDX-License-Identifier: MIT-0
"""Isolation entre tests (CW-429, B) : 10 tests échouaient selon l'ordre de la suite, parce que d'autres tests laissaient
des drapeaux `CHRYS_*` posés (test_export_theorie : CHRYS_AMODAL ; test_portefeuille : CHRYS_DESOUDER ; test_styles :
CHRYS_PARTIEL_COUPS, CHRYS_CONSENSUS, CHRYS_TEST_BUTS) ou des copies temporaires du paquet dans `sys.path` et
`sys.modules` (test_notebook_S). Après chaque test, on remet les drapeaux et `sys.path`, et on oublie les modules
chargés depuis un dossier temporaire."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = (str(Path(tempfile.gettempdir()).resolve()), "/private/var/folders", "/tmp")


@pytest.fixture(autouse=True)
def _isolation_chrys():
    env = {k: v for k, v in os.environ.items() if k.startswith("CHRYS")}
    chemin = list(sys.path)
    modules = set(sys.modules)
    yield
    for k in [k for k in os.environ if k.startswith("CHRYS") and k not in env]:
        del os.environ[k]
    os.environ.update(env)
    sys.path[:] = chemin
    for nom in set(sys.modules) - modules:
        f = getattr(sys.modules.get(nom), "__file__", None) or ""
        if f.startswith(_TMP):
            del sys.modules[nom]
