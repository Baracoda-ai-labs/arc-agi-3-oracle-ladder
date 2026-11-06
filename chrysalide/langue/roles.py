# SPDX-License-Identifier: MIT-0
"""Rôles de l'ontologie (B, gardien de `docs/ONTOLOGIE.md` ; `docs/LANGUE_PYTHON.md` § 6). La liste fermée est le bloc
`ROLES_ONTOLOGIE = {…}` de l'ontologie, lu par `ast.literal_eval` (jamais exécuté) : c'est la SEULE source.
`verifier_roles(roles)` accepte `{"controle": "confirme", ("modificateur", "couleur", 3): "compatible", …}` : un rôle sans
paramètre s'écrit par son nom ; un rôle à paramètres par un tuple (nom, valeurs…) dont le nombre suit la liste fermée ; le
statut est obligatoire et pris parmi ceux du § 7. Toute autre forme lève `RoleRefuse`."""
import ast
import functools
import re
from pathlib import Path

ONTOLOGIE = Path(__file__).resolve().parents[2] / "docs/ONTOLOGIE.md"
STATUTS = ("propose", "compatible", "confirme", "victoire_observee", "refute")


class RoleRefuse(ValueError):
    pass


@functools.lru_cache(maxsize=1)
def roles_ontologie(chemin=ONTOLOGIE):
    m = re.search(r"```python\n(ROLES_ONTOLOGIE\s*=\s*\{.*?\n\})\n```", Path(chemin).read_text(), re.DOTALL)
    if m is None:
        raise RoleRefuse(f"bloc ROLES_ONTOLOGIE absent de {chemin}")
    return {k: tuple(v) for k, v in ast.literal_eval(m.group(1).split("=", 1)[1].strip()).items()}


@functools.lru_cache(maxsize=1)
def descriptions_roles(chemin=ONTOLOGIE):
    m = re.search(r"```python\n(ROLES_DESCRIPTIONS\s*=\s*\{.*?\n\})\n```", Path(chemin).read_text(), re.DOTALL)
    if m is None:
        raise RoleRefuse(f"bloc ROLES_DESCRIPTIONS absent de {chemin}")
    return ast.literal_eval(m.group(1).split("=", 1)[1].strip())


def menu_roles(seulement=None):
    """Menu des rôles pour une consigne (CW-360) : nom, paramètres, ce qu'on voit, le coup qui départage. Jamais de nom
    interne de champ. `seulement` restreint aux rôles compatibles (fiche remplie d'abord)."""
    r, d = roles_ontologie(), descriptions_roles()
    lignes = []
    for nom in (seulement or r):
        vu, coup = d[nom]
        par = f"({', '.join(r[nom])})" if r[nom] else ""
        lignes.append(f"- {nom}{par} : {vu}. Test : {coup}.")
    return "\n".join(lignes)


def verifier_roles(roles):
    connus = roles_ontologie()
    if not isinstance(roles, dict):
        raise RoleRefuse("roles : un dictionnaire {rôle: statut}")
    for cle, statut in roles.items():
        nom, params = (cle, ()) if isinstance(cle, str) else (cle[0], tuple(cle[1:])) if isinstance(cle, tuple) and cle \
            else (None, ())
        if nom not in connus:
            raise RoleRefuse(f"rôle inconnu de l'ontologie : {cle!r} (liste fermée : {sorted(connus)})")
        if len(params) != len(connus[nom]):
            raise RoleRefuse(f"{nom} attend {len(connus[nom])} paramètre(s) {connus[nom]}, reçu {len(params)}")
        if statut not in STATUTS:
            raise RoleRefuse(f"statut {statut!r} pour {nom} : un de {STATUTS}")
    return True
