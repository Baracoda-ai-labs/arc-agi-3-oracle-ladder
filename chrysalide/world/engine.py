"""Exécution déterministe des faits, règles et outils. Les réponses attendues sortent d'ici, jamais d'un LLM."""
import heapq

from chrysalide.world.schema import RELIABILITY, Fact, Rule, Tool


def active(valid_from, valid_to, t):
    return (valid_from is None or valid_from <= t) and (valid_to is None or t < valid_to)


def holds(facts: list[Fact], subject, predicate, t):
    """Objet du fait (subject, predicate) valide à la date t ; None si aucun."""
    hits = [f.object for f in facts if f.subject == subject and f.predicate == predicate and active(f.valid_from, f.valid_to, t)]
    assert len(hits) <= 1, f"faits contradictoires pour {subject}/{predicate} à {t}"
    return hits[0] if hits else None


def eval_fn(spec: dict, x: int) -> int:
    """Mini-langage des fonctions : affine (a*x+b) ou seuil (sous/sur)."""
    if spec["op"] == "affine":
        return spec["a"] * x + spec["b"]
    if spec["op"] == "seuil":
        return eval_fn(spec["sous"] if x < spec["seuil"] else spec["sur"], x)
    raise ValueError(spec["op"])


def to_python(spec: dict, name: str) -> str:
    def expr(s):
        return f"{s['a']} * x + {s['b']}" if s["b"] >= 0 else f"{s['a']} * x - {-s['b']}"
    if spec["op"] == "affine":
        return f"def {name}(x):\n    return {expr(spec)}\n"
    return f"def {name}(x):\n    if x < {spec['seuil']}:\n        return {expr(spec['sous'])}\n    return {expr(spec['sur'])}\n"


def run_tool(tool: Tool, args: dict, journal: list):
    """Exécute un outil du monde et consigne l'appel."""
    p = tool.params
    if tool.kind == "taux_change":
        brut = args["montant"] * p["valeurs"][args["de"]]
        assert brut % p["valeurs"][args["vers"]] == 0
        res = brut // p["valeurs"][args["vers"]] - p["commission"]
    elif tool.kind == "registre":
        res = p["initial"] + sum(m["qte"] for m in p["mouvements"] if m["jour"] <= args["jour"] and not m["annule"])
    elif tool.kind == "fonction":
        res = eval_fn(p["spec"], args["x"])
    else:
        raise ValueError(tool.kind)
    journal.append({"tool": tool.id, "args": args, "result": res})
    return res


def eval_rule(rules: list[Rule], facts: list[Fact], subject, t):
    """Règle versionnée : version active à t, puis première exception dont la condition tient à t."""
    act = [r for r in rules if active(r.valid_from, r.valid_to, t)]
    assert len(act) == 1, f"{len(act)} versions actives à {t}"
    body = act[0].body
    for exc in body.get("exceptions", []):
        if holds(facts, subject, exc["si"]["predicat"], t) == exc["si"]["objet"]:
            return exc["taux"]
    return body["taux"]


def resolve(statements: list[Fact], revoked: set):
    """Arbitrage des sources : sources retirées ignorées, fiabilité la plus haute, puis déclaration la plus récente."""
    ok = [s for s in statements if s.source_id not in revoked]
    rank = {r: i for i, r in enumerate(RELIABILITY)}
    return min(ok, key=lambda s: (rank[s.reliability], -s.valid_from)).object


def shortest(n_nodes: list, edges: list[dict], src, dst, closed=frozenset()):
    """Dijkstra ; edges = [{"a","b","duree","id"}], closed = ids d'arêtes fermées."""
    adj = {v: [] for v in n_nodes}
    for e in edges:
        if e["id"] not in closed:
            adj[e["a"]].append((e["b"], e["duree"]))
            adj[e["b"]].append((e["a"], e["duree"]))
    dist, heap = {src: 0}, [(0, src)]
    while heap:
        d, v = heapq.heappop(heap)
        if v == dst:
            return d
        if d > dist[v]:
            continue
        for w, c in adj[v]:
            if d + c < dist.get(w, 1 << 60):
                dist[w] = d + c
                heapq.heappush(heap, (d + c, w))
    return None


def makespan(durees: dict, prereqs: dict) -> int:
    """Durée minimale d'un projet à équipes illimitées = plus long chemin du graphe de précédence."""
    fin = {}

    def f(j):
        if j not in fin:
            fin[j] = max((f(p) for p in prereqs[j]), default=0) + durees[j]
        return fin[j]
    return max(f(j) for j in durees)
