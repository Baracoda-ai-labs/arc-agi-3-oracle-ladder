# SPDX-License-Identifier: MIT-0
"""F (CW-444) : tableau « valeur de chaque maillon » à partir des sorties de diag4 (N1) et d'oracle_niveau (N2, N3).
Bras : A aucun oracle ; B but exact ; C règles exactes (vrai jeu simulateur) ; D tout exact (P0). Population : les 20
niveaux perdus par P1 (`GEL27_moteur_seul/dev/generique`), échecs et plantages comptés ; non mesuré = noté.
Contrôle positif : D comparé à P0 du pod (`experiments/G/p0_but_1000000_300_pod.json`).
Usage : uv run python experiments/oracle/tableau.py → tableau Markdown sur la sortie standard + tableau.json"""
import json
import re
from pathlib import Path

ICI = Path(__file__).parent
R = ICI.parents[1]
PERDUS = {"bp35": 1, "cd82": 1, "dc22": 1, "ft09": 1, "lf52": 1, "ls20": 1, "re86": 1, "sb26": 1, "sc25": 1, "sk48": 1,
          "sp80": 1, "su15": 1, "tr87": 1, "ar25": 3, "lp85": 2, "m0r0": 2, "r11l": 2, "tn36": 2, "g50t": 8, "ka59": 6}
BRAS = {"A": "aucun oracle", "B": "but exact", "C": "règles exactes (120 s)", "C600": "règles exactes (600 s)",
        "D": "tout exact (P0, 600 s)"}


def charger():
    res = {}
    for f in sorted((ICI / "raw").glob("*.json")):
        if f.name.startswith("essai"):
            continue
        for g, r in json.loads(f.read_text()).items():
            if g in PERDUS and r.get("niveau", 1) == PERDUS[g]:
                res[g] = r
    for f in sorted((ICI / "c600").glob("*.json")):  # bras C relancé au budget de D (CW-445)
        for g, r in json.loads(f.read_text()).items():
            if g in res:
                res[g]["C600"] = r["C600"]
    for r in res.values():  # sans relance (C déjà gagné, ou D en échec) : C600 = C, budget non limitant ou sans objet
        if "C" in r and "C600" not in r:
            r["C600"] = {**r["C"], "raison": (r["C"].get("raison") or "") + " (non relancé)"}
    return res


def cause(x):
    """Cause CW-445 lue dans la raison rendue par le bras : but absent / théorie incompatible / aucun plan / plan faux
    dans le jeu / budget épuisé (ou sans objet quand B n'a pas de démonstration parce que D échoue)."""
    if x.get("gagne"):
        return "**gagné**"
    r = str(x.get("raison") or "")
    if "pas de démonstration" in r or "pas de plan exact" in r:
        return "sans objet (D échoue)"
    if "budget" in r or "épuisé" in r or "arret" in r:
        return "budget épuisé"
    if re.search(r"inexprimable|aucun but|aucun candidat|pas de règle de victoire|pas de programme", r):
        return "but absent"
    if "pas de plan" in r:
        return "aucun plan"
    if x.get("premiere_divergence") is not None:
        return "théorie incompatible"
    if "non gagné" in r or "refusé par le vrai jeu" in r or "joues" in x:
        return "plan faux dans le jeu"
    return r[:30] or "—"


def p0_pod():
    d = json.loads((R / "experiments/G/p0_but_1000000_300_pod.json").read_text())
    it = d if isinstance(d, list) else d.get("resultats", list(d.values()))
    return {(x["jeu"][:4], x["niveau"]): bool(x.get("gagne")) for x in it if isinstance(x, dict) and "jeu" in x}


def main():
    res, p0 = charger(), p0_pod()
    lignes, tot = [], {c: 0 for c in BRAS}
    for g, k in sorted(PERDUS.items(), key=lambda x: (x[1], x[0])):
        r = res.get(g)
        if r is None:
            lignes.append(f"| {g} N{k} | non mesuré (pas de préfixe) | | | | | {p0.get((g, k), '—')} | |")
            continue
        if "plantage" in r:
            lignes.append(f"| {g} N{k} | plantage : {r['plantage'][:60]} | | | | | | |")
            continue
        cel = []
        for c in BRAS:
            x = r.get(c) or {}
            tot[c] += bool(x.get("gagne"))
            cel.append(cause(x))
        bp = (r.get("Bp") or {}).get("classe") or ("ok" if (r.get("Bp") or {}).get("gagne") else "—")
        lignes.append(f"| {g} N{k} | " + " | ".join(cel) + f" | {p0.get((g, k), '—')} | {bp} |")
    n = sum(1 for g in PERDUS if g in res and "plantage" not in res[g])
    print(f"Niveaux perdus par P1 : {len(PERDUS)} ; mesurés : {n}\n")
    print("| niveau | " + " | ".join(f"{c} {v}" for c, v in BRAS.items()) + " | P0 pod | perception (Bp) |")
    print("|---|---|---|---|---|---|---|---|")
    print("\n".join(lignes))
    print("| **total gagnés** | " + " | ".join(f"**{tot[c]}/{n}**" for c in BRAS) + " | | |")
    ecarts = [g for g in res if "plantage" not in res[g] and (g, PERDUS[g]) in p0
              and bool((res[g].get("D") or {}).get("gagne")) != p0[(g, PERDUS[g])]]
    print(f"\nContrôle positif (D = P0 du pod) : {len(ecarts)} écart(s) {ecarts}")
    (ICI / "tableau.json").write_text(json.dumps({"totaux": tot, "mesures": n, "ecarts_p0": ecarts,
                                                  "par_niveau": {g: {c: bool((res.get(g, {}).get(c) or {}).get("gagne"))
                                                                     for c in BRAS} for g in res}}, indent=1))


if __name__ == "__main__":
    main()
