"""T0.4 : déterminisme du générateur et justesse de `expected`, recalculé ici par une voie indépendante (force brute)."""
import itertools
import json
import subprocess
import sys

import pytest

from chrysalide.world.generate import generate_world
from chrysalide.world.surface import load_real, norm

N = 180  # 20 tâches par structure


@pytest.fixture(scope="module")
def world():
    return generate_world(3, N)


def by(world, sid):
    ts = [t for t in world["tasks"] if t["structure_id"] == sid]
    assert len(ts) == N // 9
    return ts


def test_deterministe_meme_graine():
    a = json.dumps(generate_world(7, 45), sort_keys=True)
    b = json.dumps(generate_world(7, 45), sort_keys=True)
    assert a == b
    assert a != json.dumps(generate_world(8, 45), sort_keys=True)


def test_cli_deux_runs_meme_fichier(tmp_path):
    out = []
    for d in ("r1", "r2"):
        subprocess.run([sys.executable, "-m", "chrysalide.world.generate", "--seed", "5", "--n", "27",
                        "--out", str(tmp_path / d)], check=True, capture_output=True)
        out.append((tmp_path / d / "world_s5.json").read_bytes())
    assert out[0] == out[1]


def test_cli_sans_out_refuse():
    r = subprocess.run([sys.executable, "-m", "chrysalide.world.generate", "--seed", "1", "--n", "9"], capture_output=True, check=False)
    assert r.returncode != 0


def test_graine_absente_du_fichier(tmp_path):
    (tmp_path / "g").write_text("987654321")
    subprocess.run([sys.executable, "-m", "chrysalide.world.generate", "--seed-file", str(tmp_path / "g"), "--n", "9",
                    "--out", str(tmp_path), "--name", "w.json"], check=True, capture_output=True)
    assert "987654321" not in (tmp_path / "w.json").read_text()


def test_champs_de_tache(world):
    for t in world["tasks"]:
        assert t["family"] in "ABC" and t["verifier_id"] and t["question"].split("\n")[0] in t["prompt"]
        assert t["trivial"], t["id"]


def test_filtre_anti_reel(world):
    real = load_real()
    for e in world["entities"]:
        assert not any(norm(p) in real for p in e["name"].split()), e["name"]
    # un nom rendu réel est bien rejeté au tirage suivant
    premiers = {norm(p) for e in generate_world(11, 9, real=set())["entities"] for p in e["name"].split()}
    w2 = generate_world(11, 9, real=premiers)
    assert not ({norm(p) for e in w2["entities"] for p in e["name"].split()} & premiers)
    assert w2["meta"]["noms_rejetes"] > 0


def tools(world):
    return {t["id"]: t for t in world["tools"]}


def test_a1(world):
    tl = tools(world)
    for t in by(world, "A1_conversion"):
        p, a = tl[t["inputs"]["tools"][0]]["params"], t["inputs"]["args"]
        assert t["expected"] * p["valeurs"][a["vers"]] == a["montant"] * p["valeurs"][a["de"]] - p["commission"] * p["valeurs"][a["vers"]]


def test_a2(world):
    tl = tools(world)
    for t in by(world, "A2_registre"):
        p, jour = tl[t["inputs"]["tools"][0]]["params"], t["inputs"]["args"]["jour"]
        stock = p["initial"]
        for d in range(1, jour + 1):  # simulation jour par jour
            stock += sum(m["qte"] for m in p["mouvements"] if m["jour"] == d and not m["annule"])
        assert t["expected"] == stock


def test_a3(world):
    for t in by(world, "A3_code"):
        env = {}
        exec(t["inputs"]["solution"], env)  # noqa: S102 — solution de référence du générateur
        f = env[t["expected"]["fonction"]]
        xs = [x for x, _ in t["expected"]["tests"]]
        assert t["inputs"]["spec"]["seuil"] in xs and t["inputs"]["spec"]["seuil"] - 1 in xs
        assert all(f(x) == y for x, y in t["expected"]["tests"])


def test_b1(world):
    names = {e["id"]: e["name"] for e in world["entities"]}
    facts = {f["id"]: f for f in world["facts"]}
    for t in by(world, "B1_fait_date"):
        y = t["inputs"]["annee"]
        hits = [names[facts[i]["object"]] for i in t["requires_facts"]
                if facts[i]["valid_from"] < y and (facts[i]["valid_to"] is None or y < facts[i]["valid_to"])]
        assert hits == [t["expected"]]


def test_b2(world):
    facts = {f["id"]: f for f in world["facts"]}
    rules = {r["id"]: r for r in world["rules"]}
    for t in by(world, "B2_regle_versionnee"):
        y, m = t["inputs"]["annee"], t["inputs"]["montant"]
        lieu = next(facts[i]["object"] for i in t["requires_facts"]
                    if facts[i]["valid_from"] <= y and (facts[i]["valid_to"] is None or y < facts[i]["valid_to"]))
        r = next(rules[i] for i in t["inputs"]["rules"] if rules[i]["valid_from"] <= y and (rules[i]["valid_to"] is None or y < rules[i]["valid_to"]))
        taux = next((e["taux"] for e in r["body"]["exceptions"] if e["si"]["objet"] == lieu), r["body"]["taux"])
        assert t["expected"] == m * taux // 100


def test_b3(world):
    names = {e["id"]: e["name"] for e in world["entities"]}
    facts = {f["id"]: f for f in world["facts"]}
    rang = {"fiable": 3, "instruction": 2, "témoignage": 1}
    for t in by(world, "B3_sources"):
        ok = [facts[i] for i in t["requires_facts"] if facts[i]["source_id"] not in t["inputs"]["revoquees"]]
        best = max(ok, key=lambda f: (rang[f["reliability"]], f["valid_from"]))
        assert t["expected"] == names[best["object"]]


def test_c1(world):
    for t in by(world, "C1_itineraire"):
        i = t["inputs"]
        d1, d2 = i["fermeture"]
        routes = [e for e in i["routes"] if not (e["id"] == i["fermee"] and d1 <= i["jour"] <= d2)]
        w = {}
        for e in routes:
            w[(e["a"], e["b"])] = w[(e["b"], e["a"])] = e["duree"]
        autres = [v for v in i["lieux"] if v not in (i["de"], i["vers"])]
        best = None
        for k in range(len(autres) + 1):  # tous les chemins simples
            for mid in itertools.permutations(autres, k):
                path = [i["de"], *mid, i["vers"]]
                if all((a, b) in w for a, b in itertools.pairwise(path)):
                    c = sum(w[(a, b)] for a, b in itertools.pairwise(path))
                    best = c if best is None else min(best, c)
        assert t["expected"] == best


def test_c2(world):
    for t in by(world, "C2_ordonnancement"):
        dur, pre = t["inputs"]["durees"], t["inputs"]["prerequis"]
        fin, jour = {}, 0
        while len(fin) < len(dur):  # simulation jour par jour, équipes illimitées
            for j in dur:
                if j not in fin and all(p in fin and fin[p] <= jour for p in pre[j]):
                    fin[j] = jour + dur[j]
            jour += 1
        assert t["expected"] == max(fin.values())


def test_c3(world):
    tl = tools(world)
    for t in by(world, "C3_composition"):
        v = t["inputs"]["x"]
        for tid in t["inputs"]["tools"]:
            s = tl[tid]["params"]["spec"]
            v = s["a"] * v + s["b"]
        assert t["expected"] == v
