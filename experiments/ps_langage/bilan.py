# SPDX-License-Identifier: MIT-0
"""CW-241 [session E] : tableau final du banc PuzzleScript. Passage v1 des 177 jeux (`resultats/juge_tous.json`), où les jeux
repassés en v2 (`resultats/juge_<liste>_interpreteur_ps_v2.json`, `objets_dans_boite`, plafond 30 min) remplacent leur ligne.
Classes : exact (tous les coups et toutes les fins justes, jeu complet) ; exact partiel (exact jusqu'au plafond de temps) ;
défaut du moteur de référence (psmoteur lève Refus en plein coup) ; divergent.
Usage : uv run python experiments/ps_langage/bilan.py"""
import json
from pathlib import Path

ICI = Path(__file__).resolve().parent
RES = ICI / "resultats"


def charger():
    v1 = {r["jeu"]: dict(r, version="v1") for r in json.loads((RES / "juge_tous.json").read_text())}
    for f in sorted(RES.glob("juge_*_interpreteur_ps_v2.json")):
        for r in json.loads(f.read_text()):
            v1[r["jeu"]] = dict(r, version="v2")
    return [v1[k] for k in sorted(v1)]


def classe(r):
    if "erreur_juge" in r:
        return "erreur du juge"
    juste = r["exacts"] == r["coups"] and r["fins_justes"] == r["fins_reelles"] and not r["a_tort"] and not r["erreurs"]
    if r.get("refus"):
        return "défaut du moteur de référence"
    if juste:
        return "exact partiel (plafond de temps)" if r.get("trop_lent") else "exact"
    return "divergent"


def main():
    rs = charger()
    t = json.loads((RES / "juge_tous_temoin.json").read_text())
    par = {}
    for r in rs:
        par.setdefault(classe(r), []).append(r)
    tot = lambda xs, k: sum(x.get(k, 0) for x in xs)
    print(f"{len(rs)} jeux ; coups exacts {tot(rs, 'exacts')}/{tot(rs, 'coups')} ; fins justes {tot(rs, 'fins_justes')}/"
          f"{tot(rs, 'fins_reelles')} ; fins à tort {tot(rs, 'a_tort')} ; erreurs {tot(rs, 'erreurs')}")
    print(f"témoin aucune règle : coups {tot(t, 'exacts')}/{tot(t, 'coups')} ; fins {tot(t, 'fins_justes')}/{tot(t, 'fins_reelles')}")
    for c, xs in sorted(par.items(), key=lambda kv: -len(kv[1])):
        print(f"{c:35} {len(xs):4} jeux  " + ("" if c == "exact" else ", ".join(
            f"{x['jeu']} ({x['exacts']}/{x['coups']}, {x['version']})" for x in xs)))
    s = sorted(x["s_p95"] for x in rs if x.get("s_p95") is not None)
    print("latence p95 par coup (médiane des jeux, pire jeu) :", s[len(s) // 2], s[-1],
          "; jeux en v2 :", sum(x["version"] == "v2" for x in rs))
    (RES / "bilan.json").write_text(json.dumps({c: [x["jeu"] for x in xs] for c, xs in par.items()}, indent=1))


if __name__ == "__main__":
    main()
