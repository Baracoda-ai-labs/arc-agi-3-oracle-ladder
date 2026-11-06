# SPDX-License-Identifier: MIT-0 AND Apache-2.0
"""Bloc P : pose la perception adaptative dans une COPIE du harnais de Franzen (jamais dans tiers/).

usage : python scripts/arc3/patcher_perception.py <dossier ARC3-Inference copié>
- copie chrysalide/arc3/{perception,perception_franzen,graphe,duck}.py dans <dossier>/inference/chrysalide_arc3/ ;
- dans inference/agent/tool_agent.py (ToolAgent._build_user_message), remplace
      image_part = current_grid_image_part(current_frame)
  par l'appel à perception_franzen.image_tour (CHRYS_PERCEPTION éteint = même résultat que Franzen) ;
- idempotent ; échoue si l'ancre n'est pas trouvée exactement une fois. Indépendant de patcher_franzen.py (les deux
  peuvent s'appliquer à la même copie, dans n'importe quel ordre)."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MARQUE = "# CHRYSALIDE-PERCEPTION"
FICHIERS = ("perception.py", "perception_franzen.py", "graphe.py", "duck.py")
ANCRE = "        image_part = current_grid_image_part(current_frame)\n"
REMPLACE = (f"        {MARQUE} : bloc P (CHRYS_PERCEPTION éteint = Franzen inchangé)\n"
            "        from inference.chrysalide_arc3.perception_franzen import image_tour as _chrys_image_tour\n"
            "        image_part = _chrys_image_tour(self, current_frame, current_grid_image_part)\n")


def patcher(dossier):
    dossier = Path(dossier)
    paquet = dossier / "inference" / "chrysalide_arc3"
    paquet.mkdir(exist_ok=True)
    if not (paquet / "__init__.py").exists():
        (paquet / "__init__.py").write_text("")
    for nom in FICHIERS:
        t = (RACINE / "chrysalide/arc3" / nom).read_text()
        (paquet / nom).write_text(t.replace("from chrysalide.arc3.", "from inference.chrysalide_arc3."))
    agent = dossier / "inference" / "agent" / "tool_agent.py"
    s = agent.read_text()
    if MARQUE in s:
        return "déjà patché"
    if s.count(ANCRE) != 1:
        raise SystemExit(f"ancre trouvée {s.count(ANCRE)} fois dans {agent} : version de Franzen inattendue")
    agent.write_text(s.replace(ANCRE, REMPLACE))
    return "patché"


if __name__ == "__main__":
    print(patcher(sys.argv[1]))
