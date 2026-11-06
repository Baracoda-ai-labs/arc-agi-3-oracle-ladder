"""[G] g50t N1 : la nouveauté (iw1, iw2 de plafonds.p0) trouve-t-elle le plan de 17 coups avec un gros budget ? Temps CPU."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banc_p0 import _init  # noqa: E402

_init()
import plafonds  # noqa: E402

for rech in sys.argv[1].split(","):
    r = plafonds.p0("g50t", 1, int(sys.argv[2]), float(sys.argv[3]), rech)
    print(json.dumps({x: r.get(x) for x in ("recherche", "noeuds", "etats", "plan", "gagne", "secondes", "raison")}), flush=True)
