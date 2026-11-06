"""Élargissement d'une condition existante par distances mesurées, sans nouveau prédicat."""

import hashlib

from proposeur_petites_regles import regle

from chrysalide.langue import depuis_python, vers_python


def distances(scenes):
    values = set()
    last = None
    for s in scenes:
        actors = [o for o in s.sprites if "controle" in o.get("tags", ())]
        if len(actors) != 1:
            last = None
            continue
        a = actors[0]
        if last is not None:
            values.update(abs(int(a[k] - last[k])) for k in ("x", "y"))
        last = a
    return sorted(v for v in values if 0 < v <= 8)


def etendre(candidats, marges):
    out = []
    for c in candidats:
        if c["relation"] != "proximite_boites":
            continue
        for margin in marges:
            p = regle(c["controle"], c["cible"], c["relation"], c["effet"])
            cond = p["regles"][0]["quand"][3][3]
            for test in cond[1:]:
                test[2] = ["+", test[2], margin]
            code = vers_python(p)
            assert depuis_python(code) == p
            out.append(
                {
                    **c,
                    "id": hashlib.sha256(code.encode()).hexdigest()[:12],
                    "python": code,
                    "marge": margin,
                    "parent": c["id"],
                    "relation": "proximite_boites_elargie",
                    "provenance_parametre": "déplacement interframe observé ; pas rayon de collision connu",
                }
            )
    return out
