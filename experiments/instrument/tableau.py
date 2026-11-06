# SPDX-License-Identifier: MIT-0
"""Tableau unique de l'instrument (CW-228.3 a) : diagnostic 4 configurations (6 niveaux figés), moteur seul (20 jeux publics
non témoins, une ou plusieurs variantes), T4 (banc_export.py). Une section datée est AJOUTÉE à experiments/instrument/tableau_nuit.md.
Usage : python experiments/instrument/tableau.py <dossier_nuit> [étiquette]
  <dossier_nuit>/diag4.json ; <dossier_nuit>/moteur_seul/<variante>_<jeu>.json ; <dossier_nuit>/t4_<variante>.json"""
import collections
import glob
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def diag(d):
    f = d / "diag4.json"
    if not f.exists():
        return ["(diagnostic absent)"]
    r = json.loads(f.read_text())
    out = ["| jeu | amorce rejouée | A | B | C | D |", "| --- | --- | --- | --- | --- | --- |"]
    tot = collections.Counter()
    for g, x in r.items():
        if "plantage" in x:
            out.append(f"| {g} | plantage : {x['plantage'][:60]} | | | | |")
            continue
        cel = []
        for c in "ABCD":
            y = x.get(c, {})
            tot[c] += bool(y.get("gagne")) and not y.get("note")  # (C) victoire croisée par la recherche ≠ but inféré juste
            cel.append(("gagné (victoire croisée)" if y.get("note") else "**gagné**") if y.get("gagne") else (y.get("raison") or f"diverge au pas {y.get('premiere_divergence')}")[:40])
        out.append(f"| {g} | {x.get('rejeu_amorce')} | " + " | ".join(cel) + " |")
    out.append(f"| **total** | | {tot['A']} | {tot['B']} | {tot['C']} | {tot['D']} |")
    return out


def moteur(d):
    fs = glob.glob(str(d / "moteur_seul" / "*_*.json"))
    par = collections.defaultdict(dict)
    for f in fs:
        r = json.loads(Path(f).read_text())
        par[r.get("condition", Path(f).stem.split("_")[0])][r["jeu"]] = r
    out = ["| variante | jeux | plantages | jeux où le moteur joue | coups (effet) | plans | divergences | niveaux du moteur | niveaux tous joueurs |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for v, D in sorted(par.items()):
        b = [r.get("bilan", {}) for r in D.values()]
        out.append(f"| {v} | {len(D)} | {sum(1 for r in D.values() if r.get('plantage'))} | "
                   f"{sum(1 for r in D.values() if r.get('coups', {}).get('moteur'))} | "
                   f"{sum(r.get('coups', {}).get('moteur', 0) for r in D.values())} "
                   f"({sum(r.get('coups', {}).get('moteur_effet', 0) for r in D.values())}) | "
                   f"{sum(x.get('moteur_plans', 0) or 0 for x in b)} | {sum(x.get('moteur_divergences', 0) or 0 for x in b)} | "
                   f"**{sum(r.get('niveaux_coup_final_moteur', 0) for r in D.values())}** | {sum(r.get('niveaux', 0) for r in D.values())} |")
    return out


def t4(d):
    out = ["| variante T4 | niveaux | porte 1 | gagnés |", "| --- | --- | --- | --- |"]
    for f in sorted(glob.glob(str(d / "t4_*.json"))):
        r = json.loads(Path(f).read_text()).get("resume", {})
        out.append(f"| {Path(f).stem[3:]} | {r.get('niveaux')} | {r.get('porte1')} | **{r.get('gagne_apres_portes')}** |")
    return out


def main(dossier, etiquette=""):
    d = Path(dossier)
    lignes = [f"\n## {time.strftime('%Y-%m-%d %H:%M')} {etiquette}", "", "### Diagnostic 4 configurations (sélection figée)", *diag(d),
              "", "### Moteur seul, 20 jeux publics non témoins", *moteur(d), "", "### T4", *t4(d), ""]
    sortie = RACINE / "experiments/instrument/tableau_nuit.md"
    if not sortie.exists():
        sortie.write_text("# Instrument : tableau de chaque nuit (CW-228.3 a), population entière, échecs comptés\n")
    with sortie.open("a") as fh:
        fh.write("\n".join(lignes))
    print("\n".join(lignes))


if __name__ == "__main__":
    main(*sys.argv[1:])
