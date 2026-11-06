# SPDX-License-Identifier: MIT-0 AND Apache-2.0
"""D (CW-422.3 / 422.4) : branche chrysalide/arc3/conseils.py dans une COPIE du harnais de Franzen.

usage : python scripts/arc3/patcher_conseils.py <dossier ARC3-Inference copié>
Une ancre dans inference/agent/tool_agent.py : `_build_user_message` ajoute `conseils.contexte(self)` après les fonctions
retenues. Variables éteintes = '' ajouté = Franzen inchangé. Compatible avec patcher_franzen, patcher_garde, patcher_inspect
(ancres distinctes). Idempotent ; échoue si l'ancre n'est pas trouvée exactement une fois."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MARQUE = "# CHRYSALIDE-CONSEILS"
ANCRE = "        user_prompt += self._retained_function_context()\n"
AJOUT = (ANCRE + f"        try:  {MARQUE}\n"
         "            from inference.chrysalide_arc3.conseils import contexte as _chrys_contexte\n"
         "            user_prompt += _chrys_contexte(self)\n"
         "        except Exception:\n"
         "            pass\n")


def patcher(dossier):
    dossier = Path(dossier)
    paquet = dossier / "inference" / "chrysalide_arc3"
    paquet.mkdir(exist_ok=True)
    if not (paquet / "__init__.py").exists():
        (paquet / "__init__.py").write_text("")
    (paquet / "conseils.py").write_text((RACINE / "chrysalide/arc3/conseils.py").read_text())
    agent = dossier / "inference" / "agent" / "tool_agent.py"
    s = agent.read_text()
    if MARQUE in s:
        return "déjà patché"
    if s.count(ANCRE) != 1:
        raise SystemExit(f"ancre trouvée {s.count(ANCRE)} fois dans {agent} : version de Franzen inattendue")
    agent.write_text(s.replace(ANCRE, AJOUT))
    return "patché"


if __name__ == "__main__":
    print(patcher(sys.argv[1]))
