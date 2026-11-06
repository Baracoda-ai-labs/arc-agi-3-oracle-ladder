"""[G] CW-403 : SONDE DE RÉDUCTIBILITÉ (aucun réducteur écrit) sur les niveaux sans plan à règles exactes
(`couche6_p0.jsonl`, 60 s : ni macro_g ni couche 6). Pour chaque niveau : largeur depuis le départ (programme exact,
clé `cle_complete`), au plus N états ou S secondes ; sur les états visités :
  1. successeurs identiques : part des coups générés qui ne changent rien ou donnent l'état d'un autre coup du même état ;
  2. domination par la jauge : variables d'état numériques qui décroissent à chaque coup observé = jauge ; part des
     états dont la clé SANS ces variables est déjà vue avec une jauge ≥ (dominés) ;
  3. commutation : sur un échantillon d'états, part des paires de coups effectifs (a, b) avec a·b = b·a (clé) ;
  4. symétrie résiduelle : part des états dont la clé où chaque sprite perd sa position relative à ses jumeaux… (non
     mesurée : `cle_complete` trie déjà les sprites, l'échange de pièces identiques donne déjà la même clé) ;
  5. coût CPU de chaque détection.
Usage : sonde_reductibilite.py [N=3000] [S=40] [processus=4] → experiments/G/sonde_reductibilite.jsonl"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

R = Path(__file__).resolve().parents[2]
UNE = r'''
import json, sys, time, itertools, random
sys.path[:0] = ["experiments/G"]
from banc_p0 import _init
_init()
import plafonds as pf
from mesure_exhaustivite import _resync
from chrysalide.arc3.langage import utilise_canevas
from chrysalide.arc3.logique.plan_langage import cle_complete
from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
gid, k, N, S = "GID", KK, NN, SS
texte = json.loads((pf.REGLES / f"{gid}.json").read_text())
env, fr = pf.env_au_niveau(gid, k)
sc0 = _resync(env, None, utilise_canevas(texte))
prog = ProgrammeCompile(texte)
dispo = [a for a in fr.available_actions if a != 6 and a in pf.NOMS]
coups = [(pf.NOMS[a], None, None) for a in dispo] + ([("CLICK", c[1], c[2]) for c in pf.clics(fr.frame[-1])] if 6 in fr.available_actions else [])
def pas(s, e, a):
    s2, e2 = cloner(s, e); prog.etat = e2
    try:
        prog.step(s2, a)
    except Exception:
        return None
    return s2, prog.etat
T = time.process_time; t0 = T()
k0 = cle_complete(sc0, prog.etat)
vus = {k0}; file = [(sc0, prog.etat)]; i = 0
gen = noop = doublon = 0; etats = []; t_gen = 0.0
deltas = {}
while i < len(file) and len(vus) < N and T() - t0 < S:
    s, e = file[i]; i += 1; etats.append((s, e))
    ks = set(); kk = cle_complete(s, e)
    for a in coups:
        t1 = T(); r = pas(s, e, a); t_gen += T() - t1
        if r is None: continue
        s2, e2 = r; gen += 1
        if s2.issue is not None: continue
        k2 = cle_complete(s2, e2)
        if k2 == kk: noop += 1; continue
        if k2 in ks: doublon += 1; continue
        ks.add(k2)
        for v, x in (e2 or {}).items():
            if isinstance(x, (int, float)) and isinstance((e or {}).get(v), (int, float)):
                deltas.setdefault(v, set()).add(x - e[v])
        if k2 not in vus:
            vus.add(k2); file.append((s2, e2))
jauge = sorted(v for v, d in deltas.items() if d and max(d) < 0)
t1 = T(); vu_sans = {}; domines = 0
for s, e in etats:
    reste = {v: x for v, x in (e or {}).items() if v not in jauge}
    kk = cle_complete(s, reste); j = tuple((e or {}).get(v, 0) for v in jauge)
    if kk in vu_sans and all(a >= b for a, b in zip(vu_sans[kk], j)) and vu_sans[kk] != j: domines += 1
    if kk not in vu_sans or all(a >= b for a, b in zip(j, vu_sans[kk])): vu_sans[kk] = j
t_dom = T() - t1
t1 = T(); random.seed(0); paires = commut = 0
for s, e in random.sample(etats, min(40, len(etats))):
    eff = []
    for a in coups:
        r = pas(s, e, a)
        if r and r[0].issue is None and cle_complete(*r) != cle_complete(s, e): eff.append((a, r))
    for (a, ra), (b, rb) in itertools.combinations(eff, 2):
        rab = pas(*ra, b); rba = pas(*rb, a)
        if rab is None or rba is None: continue
        paires += 1
        if cle_complete(*rab) == cle_complete(*rba): commut += 1
t_com = T() - t1
print("RES", json.dumps({"etats": len(vus), "developpes": i, "coups_par_etat": len(coups), "generes": gen,
    "sans_effet": round(noop / max(gen, 1), 3), "doublons": round(doublon / max(gen, 1), 3),
    "jauge": jauge, "domines_jauge": round(domines / max(len(etats), 1), 3),
    "paires_commutent": round(commut / max(paires, 1), 3), "paires": paires,
    "cpu_generation": round(t_gen, 1), "cpu_domination": round(t_dom, 2), "cpu_commutation": round(t_com, 1),
    "cpu": round(T() - t0, 1)}))
'''


def une(gid, k, n, s):
    code = UNE.replace("GID", gid).replace("KK", str(k)).replace("NN", str(n)).replace("SS", str(s))
    try:
        r = subprocess.run([str(R / ".venv/bin/python"), "-c", code], cwd=R, capture_output=True, text=True,
                           timeout=s * 3 + 60, env={"PYTHONPATH": str(R), "PATH": "/usr/bin:/bin"}, check=False)
        ls = [x for x in r.stdout.splitlines() if x.startswith("RES ")]
        res = json.loads(ls[-1][4:]) if ls else {"erreur": r.stderr[-200:]}
    except subprocess.TimeoutExpired:
        res = {"erreur": "mur"}
    return {"jeu": gid, "niveau": k, **res}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    s = float(sys.argv[2]) if len(sys.argv) > 2 else 40
    proc = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    rs = [json.loads(x) for x in (R / "experiments/G/couche6_p0.jsonl").read_text().splitlines()]
    d = {}
    for r in rs:
        d.setdefault((r["jeu"], r["niveau"]), []).append(r)
    bloques = sorted(k for k, v in d.items() if not any(x.get("gagne") for x in v)
                     and not any(x.get("arret") == "niveau non atteint" for x in v))
    print(json.dumps({"bloques": len(bloques)}), flush=True)
    with ThreadPoolExecutor(proc) as ex, (R / "experiments/G/sonde_reductibilite.jsonl").open("w") as f:
        for r in ex.map(lambda t: une(*t, n, s), bloques):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
