# SPDX-License-Identifier: MIT-0 AND Apache-2.0
"""V2' : pose les outils de navigation (chrysalide/arc3/outils_repl.py) dans une COPIE du harnais de Franzen.

usage : python scripts/arc3/patcher_outils.py <dossier ARC3-Inference copié>
Dans inference/agent/tool_agent.py, deux ancres (CHRYS_OUTILS éteint = Franzen inchangé) :
  1. ToolAgent._retained_sources : nos 4 fonctions sont ajoutées EN TÊTE des fonctions retenues du modèle (le modèle peut
     les redéfinir : la sienne l'emporte, règle de Franzen « la dernière définition gagne ») ;
  2. ToolAgent._retained_function_context : une phrase qui décrit les outils est ajoutée au message de tour.
Nécessite ARC3_PERSISTENT_FUNCTIONS=1 (c'est le réglage du notebook v3). Idempotent ; échoue si une ancre n'est pas
trouvée exactement une fois. Indépendant de patcher_franzen.py et patcher_perception.py."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MARQUE = "# CHRYSALIDE-OUTILS"
ANCRES = {
    "            return list(self._kept_functions.values())\n":
        f"            {MARQUE} : outils V2' (CHRYS_OUTILS éteint = Franzen inchangé)\n"
        "            if os.environ.get(\"CHRYS_OUTILS\", \"0\") == \"1\":\n"
        "                from inference.chrysalide_arc3.outils_repl import SOURCES as _chrys_sources, outils_actifs as _chrys_actifs\n"
        "                if _chrys_actifs(self):  # et, si CHRYS_OUTILS_APRES=N, seulement après N coups au niveau\n"
        "                    return list(_chrys_sources) + list(self._kept_functions.values())\n"
        "            return list(self._kept_functions.values())\n",
    "            self._retained_clear_notice = \"\"\n            return \"\\n\\n\" + \"\\n\".join(parts) if parts else \"\"\n":
        f"            self._retained_clear_notice = \"\"\n            {MARQUE}\n"
        "            if any(os.environ.get(f\"CHRYS_{_n}\", \"0\") == \"1\" for _n in (\"OUTILS\", \"BUDGET\", \"MOTEUR\")):\n"
        "                from inference.chrysalide_arc3.outils_repl import ligne_tour as _chrys_ligne_tour\n"
        "                parts.extend(_chrys_ligne_tour(self))\n"
        "            return \"\\n\\n\" + \"\\n\".join(parts) if parts else \"\"\n",
}


def patcher(dossier):
    dossier = Path(dossier)
    paquet = dossier / "inference" / "chrysalide_arc3"
    paquet.mkdir(exist_ok=True)
    if not (paquet / "__init__.py").exists():
        (paquet / "__init__.py").write_text("")
    (paquet / "outils_repl.py").write_text((RACINE / "chrysalide/arc3/outils_repl.py").read_text())
    agent = dossier / "inference" / "agent" / "tool_agent.py"
    s = agent.read_text()
    if MARQUE in s:
        return "déjà patché"
    if "\nimport os\n" not in s:
        raise SystemExit("tool_agent.py n'importe pas os : version de Franzen inattendue")
    for ancre, remplace in ANCRES.items():
        if s.count(ancre) != 1:
            raise SystemExit(f"ancre trouvée {s.count(ancre)} fois dans {agent} : version de Franzen inattendue")
        s = s.replace(ancre, remplace)
    agent.write_text(s)
    return "patché"


if __name__ == "__main__":
    print(patcher(sys.argv[1]))
