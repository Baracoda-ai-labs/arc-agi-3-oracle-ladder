"""[G] Micro-mesure de la clé et de la copie seules, sur les états réels des traces (19 jeux) : meilleur de 5 répétitions,
temps CPU, µs par état. Vérifie au passage clé G = clé de référence sur chaque état.
Usage : PYTHONPATH=. .venv/bin/python experiments/G/micro.py [jeux…]"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banc_traces import TEMOINS, charger_traces, regles, scene_de_json

from chrysalide.arc3 import sim_genere as g
from chrysalide.arc3 import sim_rapide as sr
from chrysalide.arc3.logique.plan_langage import cle_complete


def etats(jeu, segs):
    p, out = sr.ProgrammeCompile(regles(jeu)), []
    for seg in segs:
        sc = scene_de_json(seg["scene"])
        for a in seg["coups"]:
            sc, p.etat = sr.cloner(sc, p.etat)
            try:
                p.step(sc, tuple(a))
            except Exception:  # noqa: BLE001, S110
                pass
            out.append((sc, p.etat))
    return out


def chrono(f, E):
    best = 1e9
    for _ in range(5):
        t = time.process_time()
        for sc, et in E:
            f(sc, et)
        best = min(best, time.process_time() - t)
    return best / len(E) * 1e6


def coups(jeu, segs):
    """(scène, état caché, action) AVANT chaque coup des traces."""
    p, out = sr.ProgrammeCompile(regles(jeu)), []
    for seg in segs:
        sc = scene_de_json(seg["scene"])
        for a in seg["coups"]:
            sc, p.etat = sr.cloner(sc, p.etat)
            out.append((*sr.cloner(sc, p.etat), tuple(a)))
            try:
                p.step(sc, tuple(a))
            except Exception:  # noqa: BLE001, S110
                pass
    return out


def chrono_coup(P, jeu, C):
    """Meilleur de 5 : µs par coup, copies faites hors chronomètre."""
    prog, best = P(regles(jeu)), 1e9
    for _ in range(3):
        lot = [(*sr.cloner(sc, et), a) for sc, et, a in C]
        t = time.process_time()
        for sc, et, a in lot:
            prog.etat = et
            try:
                prog.step(sc, a)
            except Exception:  # noqa: BLE001, S110
                pass
        best = min(best, time.process_time() - t)
    return best / len(C) * 1e6


def main_coup(jeux):
    tr = charger_traces()
    tot = [0.0, 0.0]
    for jeu in sorted(tr):
        if jeu in TEMOINS or (jeux and jeu not in jeux):
            continue
        C = coups(jeu, tr[jeu])
        r = gg = 1e9
        for _ in range(4):  # alterné : la charge du Mac touche les deux de la même façon
            r, gg = min(r, chrono_coup(sr.ProgrammeCompile, jeu, C)), min(gg, chrono_coup(g.ProgrammeGenere, jeu, C))
        tot[0], tot[1] = tot[0] + r, tot[1] + gg
        print(jeu, len(C), f"coup_ref {r:.1f} coup_G {gg:.1f} | ×{r / gg:.2f}", flush=True)
    print(f"somme coup_ref {tot[0]:.0f} coup_G {tot[1]:.0f} | ×{tot[0] / tot[1]:.2f}")


def main(jeux):
    tr = charger_traces()
    tot = {"cle_ref": 0, "cle_G": 0, "copie_ref": 0, "copie_G": 0}
    for jeu in sorted(tr):
        if jeu in TEMOINS or (jeux and jeu not in jeux):
            continue
        E = etats(jeu, tr[jeu])
        assert all(g.cle_complete(*e) == cle_complete(*e) for e in E), jeu
        r = {"cle_ref": chrono(cle_complete, E), "cle_G": chrono(g.cle_complete, E),
             "copie_ref": chrono(sr.cloner, E), "copie_G": chrono(g.cloner, E)}
        for k in tot:
            tot[k] += r[k]
        print(jeu, len(E), " ".join(f"{k} {v:.1f}" for k, v in r.items()),
              f"| clé ×{r['cle_ref'] / r['cle_G']:.2f} copie ×{r['copie_ref'] / r['copie_G']:.2f}", flush=True)
    print("somme", " ".join(f"{k} {v:.0f}" for k, v in tot.items()),
          f"| clé ×{tot['cle_ref'] / tot['cle_G']:.2f} copie ×{tot['copie_ref'] / tot['copie_G']:.2f}")


if __name__ == "__main__":
    main_coup(sys.argv[2:]) if sys.argv[1:2] == ["coup"] else main(sys.argv[1:])
