# SPDX-License-Identifier: MIT-0
"""Faille 2 du banc (CCM-069-B) [session B] : les `regles/*.json` ne sont jugées que sur les niveaux que R0 a atteints.
On rejoue ici les traces « tous niveaux » de A (BFS dans le vrai moteur, `runs_pod/traces/<jeu>_p0_events.jsonl`,
CCM-106-A) avec la MÊME fonction de mesure honnête que le banc (`mesure_exhaustivite.mesurer`, importée, non modifiée),
sans écrire dans `exhaustivite.json`. Sortie : `au_dela/resultats.json` + une ligne par jeu (niveaux couverts R0 / traces).
Usage : uv run python experiments/T3.1/au_dela/mesure_traces.py [jeux…]"""
import json
import logging
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
R = ICI.parents[2]
sys.path.insert(0, str(ICI.parent))
import mesure_exhaustivite as m


def niveaux(f):
    """Plus haut niveau atteint dans un fichier d'événements (champ `level` des actions)."""
    n = 0
    for ligne in Path(f).read_text().splitlines():
        e = json.loads(ligne)
        if e.get("type") == "action":
            n = max(n, int(e.get("level", 0) or 0))
    return n


def main(jeux):
    logging.disable(logging.CRITICAL)
    arc = m.arcade()
    r0 = {f.name[:4]: f for f in m.fichiers_traces()}
    res = []
    for f in sorted((R / "runs_pod/traces").glob("*_p0_events.jsonl")):
        j = f.name[:4]
        if j in m.TEMOINS or (jeux and j not in jeux):
            continue
        try:
            r = m.mesurer(arc, f)
        except Exception as ex:  # noqa: BLE001 — signalé et compté, jamais caché
            r = {"jeu": j, "erreur": f"{type(ex).__name__}: {str(ex)[:120]}"}
        r["niveau_max_traces"], r["niveau_max_R0"] = niveaux(f), niveaux(r0[j]) if j in r0 else None
        res.append(r)
        print(j, {k: r.get(k) for k in ("exactes_honnetes", "transitions", "a_vide", "niveau_max_R0", "niveau_max_traces",
                                         "premiere_erreur", "erreur")}, flush=True)
    (ICI / "resultats.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
