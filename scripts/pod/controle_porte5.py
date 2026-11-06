# SPDX-License-Identifier: MIT-0
"""SUR LE POD : contrôle court du vrai harnais avant l'ABBA porte v5. Code 0 si la porte a joué sans panne de protocole et si
les coups du moteur reviennent au LLM marqués « (auto) » sans répétition du même lot. Usage : controle_porte5.py <dossier>"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

PANNES = ("enfant", "reponse", "paquet", "protocole", "proposition")
d = Path(sys.argv[1])
fins, coups = [], 0
for f in d.rglob("*_trace.jsonl"):
    for ligne in f.read_text(errors="replace").splitlines():
        x = json.loads(ligne)
        if x.get("source") == "porte_v5" and "fin" in x:
            fins.append(x["fin"])
        coups += x.get("source") == "moteur"
reprises = Counter()
for f in d.rglob("*requests.jsonl*"):
    with (gzip.open if f.suffix == ".gz" else open)(f, "rt", errors="replace") as flux:
        for ligne in flux:
            try:
                r = json.loads(ligne)
            except ValueError:
                continue
            u = [m for m in r.get("messages") or [] if isinstance(m, dict) and m.get("role") == "user"]
            texte = json.dumps(u[-1].get("content")) if u else ""
            if r.get("event") == "request" and "(auto)" in texte:
                reprises[(f.name, hash(texte))] += 1
pannes = [f for f in fins if str(f.get("raison")).startswith(PANNES)]
v = {"ouvertures": len(fins), "coups_moteur": coups, "raisons": dict(Counter(str(f.get("raison")) for f in fins)),
     "pannes": len(pannes), "requetes_avec_auto": sum(reprises.values())}
print(json.dumps(v, ensure_ascii=False))
sys.exit(0 if fins and coups and not pannes and (reprises or not coups) else 1)
