# SPDX-License-Identifier: MIT-0
"""CW-321 / CW-322 [session B] : colonnes « (b) décrit dans notre programme exact » (20 jeux publics, T3.1/regles) et
« T4 » (104 jeux générés, CONFIG et code) de l'audit du méta-modèle. Lecture seule, témoins exclus avant toute ouverture.
Usage : uv run python experiments/meta_modele/audit_programmes.py → audit_programmes.json"""
import collections
import glob
import json
import os
import re
from pathlib import Path

R = Path(__file__).resolve().parents[2]
TEM = {"vc33", "tu93", "wa30", "s5i5", "cn04"}


def ops(x, c):
    if isinstance(x, list):
        if x and isinstance(x[0], str):
            c[x[0]] += 1
        for y in x:
            ops(y, c)
    elif isinstance(x, dict):
        for y in x.values():
            ops(y, c)
    return c


def compteurs_de_defaite(d):
    """Variables d'état lues par la condition (ou le si_alors) d'une défaite ET modifiées par + ou − quelque part : c'est
    un budget décrit autrement que par `consommer` (cd82 : poser coups = coups + 1 ; puis perdre si coups >= 100)."""
    txt = json.dumps(d, ensure_ascii=False)
    lues = set()
    for r in d.get("regles", []):
        sr = json.dumps(r, ensure_ascii=False)
        if '"perdre"' in sr:
            lues |= set(re.findall(r'\["etat", "([^"]+)"\]', sr))
    return sorted(v for v in lues if re.search(r'\["poser", "%s", \["[+-]"' % re.escape(v), txt)
                  or re.search(r'\["consommer", "%s"' % re.escape(v), txt))


def programme(jeu):
    p = R / "experiments/T3.1/regles" / f"{jeu}.json"
    if not p.exists():
        return {"programme": False}
    d = json.loads(p.read_text())
    c = ops(d.get("regles", []), collections.Counter())
    ops(d.get("mots", {}), c)
    ops(d.get("au_debut", []), c)
    notes = (d.get("notes") or "") + " " + json.dumps(d.get("mots_manquants", []), ensure_ascii=False)
    return {"programme": True,
            "defaite": c["perdre"], "budget_consommer": c["consommer"] + c["epuise"],
            "compteurs_de_defaite": compteurs_de_defaite(d),  # CCM-067-E : budget décrit sans le mot consommer
            "victoire": c["niveau_suivant"] + c["gagner"],
            "etat_initial": sorted((d.get("etat") or {}).keys()),
            "variables_etat": c["etat"] > 0,
            "dessin_interface": c["montrer"] + c["masque"],
            "notes_jauge_vies": sorted(set(re.findall(r"jauge|vie[s]?\b|budget|compteur|pastille|énergie|energie", notes, re.IGNORECASE))),
            "mots_manquants": d.get("mots_manquants", []),
            "contournements": len(d.get("contournements_restants", []) or [])}


def t4():
    out, cles = [], collections.Counter()
    for f in sorted(glob.glob(str(R / "experiments/T4/jeux/t4/environment_files/*/*/*.py"))):
        src = Path(f).read_text()
        m = re.search(r"CONFIG\s*=\s*(\{.*?\n\})", src, re.DOTALL)
        conf = m.group(1) if m else ""
        k = {x: bool(re.search(r"['\"]" + x + r"['\"]", conf)) for x in
             ("jauge_plein", "jauge_vide", "jauge_cote", "pip_plein", "pip_vide", "recharge")}
        r = {"jeu": os.path.basename(os.path.dirname(os.path.dirname(f))), **k,
             "classe_jauge": bool(re.search(r"class\s+Jauge\s*\(", src)), "lose": len(re.findall(r"\.lose\(\)", src))}
        cles.update(x for x, v in k.items() if v)
        out.append(r)
    return out, dict(cles)


def main():
    jeux = [g for g in sorted(os.listdir(R / "experiments/arc3/environment_files")) if g not in TEM]
    prog = {g: programme(g) for g in jeux}
    t, cles = t4()
    res = {"programmes": prog, "t4": {"n": len(t), "jeux_avec": cles, "classe_jauge": sum(r["classe_jauge"] for r in t),
                                      "lose_moyen": round(sum(r["lose"] for r in t) / max(len(t), 1), 2), "detail": t}}
    (Path(__file__).parent / "audit_programmes.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for g, p in prog.items():
        print(g, {k: p[k] for k in ("defaite", "budget_consommer", "victoire", "variables_etat", "dessin_interface",
                                    "notes_jauge_vies", "contournements")})
    print("T4", res["t4"]["n"], cles, "classe Jauge", res["t4"]["classe_jauge"], "lose moyen", res["t4"]["lose_moyen"])


if __name__ == "__main__":
    main()
