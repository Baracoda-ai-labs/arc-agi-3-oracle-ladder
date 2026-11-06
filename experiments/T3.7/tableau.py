# SPDX-License-Identifier: MIT-0
"""CW-203 [session B] : tableau « mécanique T4 → décrite au pixel près ? » depuis juge_<famille>.json (programme) et
juge_<famille>_temoin.json (aucune règle). Une mécanique est décrite si TOUS les jeux qui la contiennent sont exacts
(coups non terminaux exacts, fins de niveau justes, aucune fin à tort, défaites justes, aucune erreur).
Usage : uv run python experiments/T3.7/tableau.py"""
import json
from collections import defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent


def exact(r):
    return ("erreur_juge" not in r and r["exacts"] == r["coups"] and r["fins_justes"] == r["fins_reelles"]
            and r["a_tort"] == 0 and r["defaites_justes"] == r["defaites"] and r["erreurs"] == 0)


def main():
    lignes, par_meca = [], defaultdict(list)
    for fam in ("dedale", "tuiles"):
        res = json.loads((ICI / f"juge_{fam}.json").read_text())
        tem = {r["jeu"]: r for r in json.loads((ICI / f"juge_{fam}_temoin.json").read_text())}
        t = {k: sum(r.get(k, 0) for r in res) for k in ("coups", "exacts", "fins_reelles", "fins_justes", "a_tort",
                                                        "defaites", "defaites_justes", "erreurs")}
        tv = sum(r.get("exacts", 0) for r in tem.values())
        lignes.append(f"| {fam} | {len(res)} | {sum(map(exact, res))} | {t['exacts']}/{t['coups']} | {tv}/{t['coups']} | "
                      f"{t['fins_justes']}/{t['fins_reelles']} | {t['a_tort']} | {t['defaites_justes']}/{t['defaites']} | {t['erreurs']} |")
        for r in res:
            for mc in ["base", *r.get("mecaniques", [])]:
                par_meca[(fam, mc)].append(r)
    print("| famille | jeux | jeux exacts | coups exacts | témoin vide | fins justes | fins à tort | défaites justes | erreurs |")
    print("|---|---|---|---|---|---|---|---|---|")
    print("\n".join(lignes))
    print("\n| mécanique | famille | jeux | jeux exacts | coups exacts | décrite au pixel près |")
    print("|---|---|---|---|---|---|")
    for (fam, mc), rs in sorted(par_meca.items(), key=lambda x: (-len(x[1]), x[0])):
        ok = sum(map(exact, rs))
        print(f"| {mc} | {fam} | {len(rs)} | {ok} | {sum(r['exacts'] for r in rs)}/{sum(r['coups'] for r in rs)} | "
              f"{'oui' if ok == len(rs) else 'non'} |")


if __name__ == "__main__":
    main()
