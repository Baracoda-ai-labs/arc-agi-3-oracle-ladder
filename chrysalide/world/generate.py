"""Génère un monde et ses tâches, déterministe à graine fixée.

Usage : uv run python -m chrysalide.world.generate (--seed S | --seed-file F) --n N --out DIR [--name FICHIER]
Pas de valeur par défaut pour --out. Le fichier ne contient pas la graine (pour data/final, Cowork passe --seed-file
et --name, afin que la graine n'apparaisse ni dans le nom du fichier ni sur la ligne de commande)."""
import argparse
import json
import pathlib
import random
from collections import Counter

from chrysalide.world.schema import Task, to_dict
from chrysalide.world.structures import Ctx
from chrysalide.world.structures.famille_a import a1_conversion, a2_registre, a3_code
from chrysalide.world.structures.famille_b import b1_fait_date, b2_regle_versionnee, b3_sources
from chrysalide.world.structures.famille_c import c1_itineraire, c2_ordonnancement, c3_composition
from chrysalide.world.surface import FORMAT, QUESTIONS, Namer, load_real

GENERATOR_VERSION = "world-v0.1"
STRUCTURES = [a1_conversion, a2_registre, a3_code, b1_fait_date, b2_regle_versionnee, b3_sources,
              c1_itineraire, c2_ordonnancement, c3_composition]


def generate_world(seed: int, n: int, real: set | None = None) -> dict:
    rng = random.Random(seed)
    namer = Namer(rng, load_real() if real is None else real)
    ctx = Ctx(rng, namer)
    tasks = []
    for i in range(n):
        d = STRUCTURES[i % len(STRUCTURES)](ctx)
        question = rng.choice(QUESTIONS[d["structure_id"]]).format(**d["qparams"])
        fmt = FORMAT[d["answer_type"]]
        prompt = "\n".join(d["context"]) + "\n\n" + question + "\n" + fmt
        tasks.append(Task(f"K{i + 1:05d}", d["family"], d["structure_id"], d["inputs"], d["expected"], d["verifier_id"],
                          d["requires_facts"], d["requires_skills"], d["answer_type"], prompt, question + "\n" + fmt,
                          d["context"], d["trivial"]))
    add_mode(tasks)
    return {"meta": {"generator": GENERATOR_VERSION, "n_tasks": n, "noms_rejetes": namer.rejected},
            "entities": [to_dict(e) for e in ctx.entities], "facts": [to_dict(f) for f in ctx.facts],
            "rules": [to_dict(r) for r in ctx.rules], "tools": [to_dict(t) for t in ctx.tools],
            "tasks": [to_dict(t) for t in tasks]}


def add_mode(tasks):
    """Politique « réponse la plus fréquente » : mode des autres tâches de la même structure (hors code)."""
    for t in tasks:
        if t.answer_type == "code":
            continue
        autres = [json.dumps(u.expected) for u in tasks if u.structure_id == t.structure_id and u.id != t.id]
        if autres:
            c = Counter(autres)
            best = max(sorted(c), key=lambda k: c[k])
            t.trivial["mode"] = json.loads(best)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--seed", type=int)
    g.add_argument("--seed-file", type=pathlib.Path)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--name")
    a = ap.parse_args()
    if a.seed_file and not a.name:
        ap.error("--seed-file exige --name (le nom du fichier ne doit pas révéler la graine)")
    seed = a.seed if a.seed is not None else int(a.seed_file.read_text().strip())
    world = generate_world(seed, a.n)
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / (a.name or f"world_s{a.seed}.json")
    path.write_text(json.dumps(world, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{path} : {a.n} tâches, {len(world['entities'])} entités, {len(world['facts'])} faits, "
          f"{world['meta']['noms_rejetes']} noms rejetés par le filtre anti-réel")


if __name__ == "__main__":
    main()
