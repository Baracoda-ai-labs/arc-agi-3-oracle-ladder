"""T1.0 : monde v1 « campagne ». Réponses recalculées par une voie indépendante (force brute), couverture et disjonction."""
import itertools
import json
from collections import defaultdict

import pytest

from chrysalide.world.campagne import APPRENTISSAGE, TEST, generate_campagne


@pytest.fixture(scope="module")
def w():
    return generate_campagne(11)


def test_deterministe():
    assert json.dumps(generate_campagne(5, 10, 5), sort_keys=True) == json.dumps(generate_campagne(5, 10, 5), sort_keys=True)
    assert json.dumps(generate_campagne(5, 10, 5), sort_keys=True) != json.dumps(generate_campagne(6, 10, 5), sort_keys=True)


def test_structures_disjointes_et_effectifs(w):
    app = {e["structure_id"] for e in w["episodes"]}
    tst = {t["structure_id"] for t in w["tasks"]}
    assert app == {s for v in APPRENTISSAGE.values() for s in v} and tst == {s for v in TEST.values() for s in v}
    assert not app & tst
    n = defaultdict(int)
    for t in w["tasks"]:
        n[t["structure_id"]] += 1
    assert min(n.values()) >= 45  # 50 visées ; quelques tirages sans cas non ambigu sont écartés


def test_couverture_des_faits(w):
    """Chaque fait nécessaire à une tâche de test figure dans au moins un épisode d'apprentissage."""
    vus = {f for e in w["episodes"] for f in e["fact_ids"]}
    manquants = {f for t in w["tasks"] for f in t["requires_facts"]} - vus
    assert not manquants, manquants


def test_expected_force_brute(w):
    tools = {t["id"]: t for t in w["tools"]}
    facts = w["facts"]
    for t in w["tasks"]:
        s, i = t["structure_id"], t["inputs"]
        if s == "A4T_conversion_chaine":
            v = None
            for tid, de, vers, m in i["etapes"]:
                p = tools[tid]["params"]
                m = v if v is not None else m
                v = m * p["valeurs"][de] // p["valeurs"][vers] - p["commission"]
            assert v == t["expected"]
        elif s == "A5T_variation_stock":
            p = tools[i["outil"]]["params"]
            stock = [p["initial"]]
            for d in range(1, 41):  # simulation jour par jour
                stock.append(stock[-1] + sum(m["qte"] for m in p["mouvements"] if m["jour"] == d and not m["annule"]))
            assert stock[i["jours"][1]] - stock[i["jours"][0]] == t["expected"]
        elif s in ("B4T_dirigeant_installation", "B5T_impot_prise_direction"):
            an = i["annee"]
            def en(pred, i=i, an=an):
                hits = [f["object"] for f in facts if f["subject"] == i["sujet"] and f["predicate"] == pred
                        and f["valid_from"] <= an and (f["valid_to"] is None or an < f["valid_to"])]
                assert len(hits) == 1
                return hits[0]
            if s.startswith("B4"):
                assert next(e["name"] for e in w["entities"] if e["id"] == en("dirigeant")) == t["expected"]
            else:
                lieu = en("situee_a")
                regle = [r for r in w["rules"] if r["valid_from"] <= an and (r["valid_to"] is None or an < r["valid_to"])]
                assert len(regle) == 1
                taux = next((e["taux"] for e in regle[0]["body"]["exceptions"] if e["si"]["objet"] == lieu), regle[0]["body"]["taux"])
                assert i["montant"] * taux // 100 == t["expected"]
        elif s == "C4T_composition3":
            v = i["x"]
            for tid in i["chaine"]:
                sp = tools[tid]["params"]["spec"]
                v = sp["a"] * v + sp["b"]
            assert v == t["expected"]
        elif s == "C5T_trajet_etape":
            nodes = sorted({r["a"] for r in w["routes"]} | {r["b"] for r in w["routes"]})
            d = {(a, b): (0 if a == b else 10**9) for a in nodes for b in nodes}
            for r in w["routes"]:
                d[r["a"], r["b"]] = d[r["b"], r["a"]] = min(d[r["a"], r["b"]], r["duree"])
            for k, a, b in itertools.product(nodes, nodes, nodes):  # Floyd–Warshall (k en tête)
                d[a, b] = min(d[a, b], d[a, k] + d[k, b])
            assert d[i["de"], i["par"]] + d[i["par"], i["vers"]] == t["expected"]
            assert d[i["de"], i["vers"]] != t["expected"]


def test_triviales_basses(w):
    par = defaultdict(lambda: defaultdict(int)); n = defaultdict(int)
    for t in w["tasks"]:
        n[t["structure_id"]] += 1
        for pol, v in t["trivial"].items():
            par[t["structure_id"]][pol] += v == t["expected"]
    pires = {s: max(p.values()) / n[s] for s, p in par.items()}
    assert max(pires.values()) <= 0.30, pires


def test_test_sans_contexte_ne_contient_pas_les_faits(w):
    for t in w["tasks"]:
        assert not any(line in t["question"] for line in t["context"])


def test_variantes_par_outil(w):
    """Bras sans pensée : rejouer les bons appels par la boucle d'outils redonne la réponse attendue."""
    from chrysalide.eval.boucle import executer, prompt_outil
    noms = {e["id"]: e["name"] for e in w["entities"]}
    tools = {t["id"]: t for t in w["tools"]}
    for t in w["tasks"]:
        s, i = t["structure_id"], t["inputs"]
        if s not in ("A4T_conversion_chaine", "A5T_variation_stock", "C4T_composition3"):
            continue
        texte, off = prompt_outil(t, w, 6)
        assert "vaut" not in texte.split("Outils disponibles")[1]  # aucune donnée dans l'énoncé
        if s == "A4T_conversion_chaine":
            v = None
            for tid, de, vers, m in i["etapes"]:
                v, err = executer({"outil": tools[tid]["name"], "args": {"montant": v or m, "de": noms[de], "vers": noms[vers]}}, off, w)
                assert err is None
        elif s == "A5T_variation_stock":
            nom = tools[i["outil"]]["name"]
            a, b = (executer({"outil": nom, "args": {"jour": j}}, off, w)[0] for j in i["jours"])
            v = b - a
        else:
            assert len(off) == 8
            v = i["x"]
            for tid in i["chaine"]:
                v = executer({"outil": tools[tid]["name"], "args": {"x": v}}, off, w)[0]
        assert v == t["expected"]
