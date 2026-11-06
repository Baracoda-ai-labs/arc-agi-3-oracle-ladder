"""[G] CW-388 (contrôle positif, règles EXACTES) : `strategies.planifier` de la couche 6 (agent cloud,
`experiments/defi_llm/couche6/strategies/`) contre `macro_g` (gel 2), niveau par niveau sur P0 (20 jeux publics hors
témoins × N1-3, programmes exacts `T3.1/regles`), MUR DUR par niveau (processus tué à la limite). Même départ (moteur au
début du niveau, `_resync`), mêmes coups (actions du niveau + clics de `plafonds.clics` sur l'image de départ).
Contrat couche 6 : état hachable (clé `cle_complete`), `pas` → état | None (défaite), `atteint` = issue « niveau ».
`signaux=None` (famille « inconnue » : recherche_guidee IW(1) → IW(2) → A*/BFWS) : la mémoire globale n'est pas lue.
Plans rejoués dans le vrai jeu. Prédiction (avant mesure) : macro_g ≈ 14/60 à 60 s, couche 6 ≤ macro_g.
Usage : banc_couche6.py [secondes=60] [processus=4] → experiments/G/couche6_p0.jsonl"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

R = Path(__file__).resolve().parents[2]
TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}

UNE = r'''
import json, sys, time
sys.path[:0] = ["experiments/G", "experiments/defi_llm/couche6"]
from banc_p0 import _init
_init()
import plafonds as pf
from mesure_exhaustivite import _resync
from chrysalide.arc3.langage import utilise_canevas
from chrysalide.arc3.logique.plan_langage import cle_complete
from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
gid, k, meth, sec = "GID", KK, "METH", SEC
t0 = time.process_time()
if meth == "macro_g":
    import macro_g
    r = macro_g.chercher(gid, k, 10**6, sec)
    print("RES", json.dumps({"plan": r.get("plan"), "gagne": r.get("gagne"), "arret": r.get("arret"), "cpu": r.get("cpu")}))
    raise SystemExit
from strategies import planifier
texte = json.loads((pf.REGLES / f"{gid}.json").read_text())
env, fr = pf.env_au_niveau(gid, k)
if env is None:
    print("RES", json.dumps({"plan": None, "arret": "niveau non atteint"})); raise SystemExit
sc0 = _resync(env, None, utilise_canevas(texte))
prog = ProgrammeCompile(texte)
dispo = [a for a in fr.available_actions if a != 6 and a in pf.NOMS]
coups = [(pf.NOMS[a], None, None) for a in dispo] + ([("CLICK", c[1], c[2]) for c in pf.clics(fr.frame[-1])] if 6 in fr.available_actions else [])
class E:
    __slots__ = ("s", "e", "k", "g")
    def __init__(self, s, e, g=False):
        self.s, self.e, self.g = s, e, g
        self.k = cle_complete(s, e)
    def __hash__(self): return hash(self.k)
    def __eq__(self, o): return self.k == o.k
def pas(x, a):
    s2, e2 = cloner(x.s, x.e)
    prog.etat = e2
    try:
        prog.step(s2, a)
    except Exception:
        return None
    if s2.issue in ("niveau", "victoire"):
        return E(s2, prog.etat, True)
    if s2.issue is not None:
        return None
    return E(s2, prog.etat)
import os
import numpy as np
def _cible(sc, y, x):
    top = None
    for i, o in enumerate(sc.sprites):
        if not o.get("visible", True): continue
        px = np.asarray(o["pixels"]); yy, xx = y - o["y"], x - o["x"]
        if 0 <= yy < px.shape[0] and 0 <= xx < px.shape[1] and px[yy, xx] >= 0: top = i
    if top is None or (np.asarray(sc.sprites[top]["pixels"]) >= 0).sum() > 64 * 64 // 16:
        return ("seul", y, x)
    return top
def coups_groupes(x):  # CW-403 : un clic par petit objet visé (vérifié sûr sur 12 niveaux, 0 faux)
    vus, out = set(), []
    for c in coups:
        if c[0] == "CLICK":
            g = _cible(x.s, c[1], c[2])
            if g in vus: continue
            vus.add(g)
        out.append(c)
    return out
r = planifier(E(sc0, prog.etat), pas, coups_groupes if os.environ.get("G_GROUPES") == "1" else coups, lambda x: x.g,
              signaux=None, max_noeuds=10**7)
plan = r.get("plan")
gagne = None
if plan:
    env2, f0 = pf.env_au_niveau(gid, k)
    fin = None
    for a in plan:
        fin = pf.jouer(env2, (6, a[1], a[2]) if a[0] == "CLICK" else ({v: c for c, v in pf.NOMS.items()}[a[0]], None, None))
        if fin.levels_completed >= k or fin.state.name in ("WIN", "GAME_OVER"):
            break
    gagne = bool(fin is not None and (fin.levels_completed >= k or fin.state.name == "WIN"))
print("RES", json.dumps({"plan": None if not plan else len(plan), "gagne": gagne, "methode": r.get("methode"),
                         "cpu": round(time.process_time() - t0, 1)}))
'''


def une(gid, k, meth, sec):
    t0 = time.monotonic()
    code = UNE.replace("GID", gid).replace("KK", str(k)).replace("METH", meth).replace("SEC", str(sec * 0.9))
    try:
        r = subprocess.run([str(R / ".venv/bin/python"), "-c", code], cwd=R, capture_output=True, text=True,
                           timeout=sec, env={"PYTHONPATH": str(R), "PATH": "/usr/bin:/bin", "G_GROUPES": os.environ.get("G_GROUPES", "")}, check=False)
        ls = [x for x in r.stdout.splitlines() if x.startswith("RES ")]
        res = json.loads(ls[-1][4:]) if ls else {"erreur": r.stderr[-200:]}
    except subprocess.TimeoutExpired:
        res = {"plan": None, "arret": "mur"}
    return {"jeu": gid, "niveau": k, "methode_banc": meth, "mur": round(time.monotonic() - t0, 1), **res}


def main():
    sec = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    proc = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    jeux = [p.stem for p in sorted((R / "experiments/T3.1/regles").glob("*.json")) if "_" not in p.stem and p.stem not in TEMOINS]
    meths = ("couche6",) if os.environ.get("G_GROUPES") == "1" else ("macro_g", "couche6")
    taches = [(j, k, m) for j in jeux for k in (1, 2, 3) for m in meths]
    sortie = R / f"experiments/G/couche6_p0{'_' + str(int(sec)) + 's' if sec != 60 else ''}{'_groupes' if os.environ.get('G_GROUPES') == '1' else ''}.jsonl"
    with ThreadPoolExecutor(proc) as ex, sortie.open("w") as f:
        for r in ex.map(lambda t: une(*t, sec), taches):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
