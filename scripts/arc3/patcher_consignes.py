# SPDX-License-Identifier: MIT-0 AND Apache-2.0
"""CW-050 c : pose les consignes de B (épinglage, audit, libellés) dans une COPIE du harnais de Franzen (jamais dans tiers/).

usage : python scripts/arc3/patcher_consignes.py <dossier ARC3-Inference copié>
- copie chrysalide/arc3/consignes.py dans <dossier>/inference/chrysalide_arc3/ ;
- dans inference/agent/tool_agent.py (ToolAgent._build_user_prompt), juste après l'initialisation de `lines`, ajoute
      lines.extend(tour(self, current_level, history_entries))
  (CHRYS_EPINGLE, CHRYS_AUDIT, CHRYS_LIBELLES éteints = liste vide et consigne système intacte = Franzen inchangé) ;
- idempotent ; échoue si l'ancre n'est pas trouvée exactement une fois. Compatible avec les autres patchers."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MARQUE = "# CHRYSALIDE-CONSIGNES"
ANCRE = ("            default=current_level,\n"
         "        )\n"
         "        lines: list[str] = []\n")
AJOUT = (f"        {MARQUE} : épinglage, audit, libellés (interrupteurs éteints = Franzen inchangé)\n"
         "        from inference.chrysalide_arc3.consignes import tour as _chrys_consignes_tour\n"
         "        lines.extend(_chrys_consignes_tour(self, current_level, history_entries))\n")


def patcher(dossier):
    dossier = Path(dossier)
    paquet = dossier / "inference" / "chrysalide_arc3"
    paquet.mkdir(exist_ok=True)
    if not (paquet / "__init__.py").exists():
        (paquet / "__init__.py").write_text("")
    (paquet / "consignes.py").write_text((RACINE / "chrysalide/arc3/consignes.py").read_text())
    agent = dossier / "inference" / "agent" / "tool_agent.py"
    s = agent.read_text()
    if MARQUE in s:
        return "déjà patché"
    if s.count(ANCRE) != 1:
        raise SystemExit(f"ancre trouvée {s.count(ANCRE)} fois dans {agent} : version de Franzen inattendue")
    agent.write_text(s.replace(ANCRE, ANCRE + AJOUT))
    return "patché"


if __name__ == "__main__":
    print(patcher(sys.argv[1]))
