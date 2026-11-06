# SPDX-License-Identifier: MIT-0 AND Apache-2.0
"""D (CW-357) : pose inspect_model() / inspect_options() (chrysalide/arc3/inspect_franzen.py) dans une COPIE du harnais.

usage : python scripts/arc3/patcher_inspect.py <dossier ARC3-Inference copié>
CHRYS_INSPECT éteint = Franzen inchangé. Trois ancres dans inference/agent/tool_agent.py, une dans python_tool_sandbox.py :
  1. ToolAgent._retained_sources : renommée _retained_sources_franzen ; la nouvelle met nos 2 fonctions EN TÊTE ;
  2. message de tour : la phrase « une option est disponible », seulement quand une option fraîche existe ;
  3. état sérialisé du REPL : clé « chrysalide » = analyzer._chrys_inspect (posé par la branche) ;
  4. bac à sable : globale `chrysalide_etat` = cette clé.
Nécessite ARC3_PERSISTENT_FUNCTIONS=1 (réglage du notebook v3). Compatible avec patcher_outils.py (avant ou après).
Idempotent ; échoue si une ancre n'est pas trouvée exactement une fois."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MARQUE = "# CHRYSALIDE-INSPECT"
AGENT = {
    # 1. sources : la méthode de Franzen est renommée, la nôtre ajoute nos fonctions DEVANT ce qu'elle rend (compatible
    #    avec patcher_outils, qui patche l'intérieur de la méthode renommée)
    "    def _retained_sources(self):\n":
        f"    def _retained_sources(self):  {MARQUE}\n"
        "        base = self._retained_sources_franzen()\n"
        "        if base is not None and os.environ.get(\"CHRYS_INSPECT\", \"0\") == \"1\":\n"
        "            from inference.chrysalide_arc3.inspect_franzen import SOURCES as _chrys_inspect_sources\n"
        "            return list(_chrys_inspect_sources) + list(base)\n"
        "        return base\n\n"
        "    def _retained_sources_franzen(self):\n",
    # 2. phrase du tour, après le dernier parts.append (hors de la paire de lignes qu'utilise patcher_outils)
    "\"correct; revise them if new evidence contradicts their assumptions.\"\n                )\n":
        "\"correct; revise them if new evidence contradicts their assumptions.\"\n                )\n"
        f"            if os.environ.get(\"CHRYS_INSPECT\", \"0\") == \"1\":  {MARQUE}\n"
        "                from inference.chrysalide_arc3.inspect_franzen import ligne_tour as _chrys_inspect_ligne\n"
        "                parts.extend(_chrys_inspect_ligne(self))\n",
    # 3. état sérialisé du REPL
    "                \"current_frame\": current_frame_payload,\n":
        f"                \"chrysalide\": getattr(self, \"_chrys_inspect\", None),  {MARQUE}\n"
        "                \"current_frame\": current_frame_payload,\n",
}
BAC = {
    "            runtime_globals[\"death_ledger\"] = state_payload.get(\"death_ledger\") or {\"attempts\": []}\n":
        "            runtime_globals[\"death_ledger\"] = state_payload.get(\"death_ledger\") or {\"attempts\": []}\n"
        f"            runtime_globals[\"chrysalide_etat\"] = state_payload.get(\"chrysalide\")  {MARQUE}\n",
}


def _appliquer(fichier, ancres):
    s = fichier.read_text()
    if MARQUE in s:
        return False
    for ancre, remplace in ancres.items():
        if s.count(ancre) != 1:
            raise SystemExit(f"ancre trouvée {s.count(ancre)} fois dans {fichier} : version de Franzen inattendue")
        s = s.replace(ancre, remplace)
    fichier.write_text(s)
    return True


def patcher(dossier):
    dossier = Path(dossier)
    paquet = dossier / "inference" / "chrysalide_arc3"
    paquet.mkdir(exist_ok=True)
    if not (paquet / "__init__.py").exists():
        (paquet / "__init__.py").write_text("")
    # imports réécrits comme patcher_franzen.py : la copie brute laissait « from chrysalide.arc3.logique… » (bilan de F), introuvable
    # dans le harnais → ModuleNotFoundError à chaque tour où une option existe, et repli Franzen (J1, 22/10, A)
    t = (RACINE / "chrysalide/arc3/inspect_franzen.py").read_text()
    (paquet / "inspect_franzen.py").write_text(t.replace("from chrysalide.arc3.", "from inference.chrysalide_arc3.")
                                               .replace("from chrysalide.arc3 import", "from inference.chrysalide_arc3 import"))
    agent = dossier / "inference" / "agent" / "tool_agent.py"
    if "\nimport os\n" not in agent.read_text():
        raise SystemExit("tool_agent.py n'importe pas os : version de Franzen inattendue")
    a = _appliquer(agent, AGENT)
    b = _appliquer(dossier / "inference" / "agent" / "python_tool_sandbox.py", BAC)
    return "patché" if a or b else "déjà patché"


if __name__ == "__main__":
    print(patcher(sys.argv[1]))
