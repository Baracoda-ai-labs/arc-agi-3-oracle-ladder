"""E1 : le script de décision rend la bonne conclusion sur des résultats fabriqués dont on connaît la réponse."""
import json
import random

from scripts import e1_analyse as A


def fabriquer(run, cond, reg, juste):
    (run / "raw").mkdir(parents=True, exist_ok=True)
    for g in A.GRAINES:
        with (run / "raw" / f"{cond}_s{g}_{reg}.jsonl").open("w") as f:
            for t in A.taches(g).values():
                if cond == "c3" and t["structure_id"] not in A.OUTILS:
                    continue
                ok = juste(g, t)
                f.write(json.dumps({"task": t["id"], "family": t["family"], "structure": t["structure_id"],
                                    "status": "correct" if ok else "incorrect", "output": str(ok)}) + "\n")


def monde(tmp_path, c4):
    b, e = tmp_path / "B", tmp_path / "E"
    rng = random.Random(1)
    moitie = {(g, t): rng.random() < 0.5 for g in A.GRAINES for t in A.taches(g)}
    for reg in ("p", "np"):
        fabriquer(b, "c0", reg, lambda g, t: False)
        fabriquer(b, "c1", reg, lambda g, t: True)
        fabriquer(b, "cT", reg, lambda g, t: False)
        fabriquer(b, "c2", reg, lambda g, t: moitie[(g, t["id"])])
        fabriquer(b, "c3", reg, lambda g, t: moitie[(g, t["id"])])
        fabriquer(e, "c4", reg, lambda g, t: c4(moitie[(g, t["id"])]))
    return b, e


def test_porte_g_ouverte(tmp_path):
    b, _ = monde(tmp_path, lambda m: m)
    assert A.porte_g(b)


def test_poids_utiles(tmp_path):
    b, e = monde(tmp_path, lambda m: True)
    assert A.verdict(b, e, tirages=500) == "POIDS UTILES"


def test_poids_inutiles(tmp_path):
    b, e = monde(tmp_path, lambda m: m)  # le LoRA ne fait ni mieux ni moins bien que la mémoire, tâche par tâche
    assert A.verdict(b, e, tirages=500) == "POIDS INUTILES"
