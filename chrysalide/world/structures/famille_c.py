"""Famille C — composition et planification."""
from chrysalide.world.engine import makespan, run_tool, shortest
from chrysalide.world.structures import Ctx, draft


def c1_itineraire(c: Ctx):
    while True:
        lieux = [c.entity("lieu") for _ in range(c.rng.randint(5, 6))]
        ids = [v.id for v in lieux]
        edges, pairs = [], set()
        for i in range(1, len(ids)):  # arbre couvrant puis arêtes en plus
            pairs.add(tuple(sorted((ids[i], c.rng.choice(ids[:i])))))
        while len(pairs) < len(ids) + c.rng.randint(2, 3):
            pairs.add(tuple(sorted(c.rng.sample(ids, 2))))
        for k, (a, b) in enumerate(sorted(pairs)):
            edges.append({"id": k, "a": a, "b": b, "duree": c.rng.randint(10, 90)})
        de, vers = c.rng.sample(ids, 2)
        base = shortest(ids, edges, de, vers)
        # la route fermée est prise sur un plus court chemin, pour que la fermeture compte
        sur_chemin = [e for e in edges if shortest(ids, edges, de, vers, {e["id"]}) != base]
        ferme = c.rng.choice(sur_chemin or edges)
        d1 = c.rng.randint(1, 20)
        d2 = d1 + c.rng.randint(2, 8)
        jour = c.rng.randint(d1, d2) if c.rng.random() < 0.8 else c.rng.choice([d1 - 1, d2 + 1] if d1 > 1 else [d2 + 1])
        closed = {ferme["id"]} if d1 <= jour <= d2 else set()
        expected = shortest(ids, edges, de, vers, closed)
        if expected is not None:
            break
        c.entities = [e for e in c.entities if e.id not in ids]  # retirage si la fermeture coupe le trajet
    names = {e.id: e.name for e in c.entities}
    ordre = edges[:]
    c.rng.shuffle(ordre)
    ctx = [c.rng.choice([f"La route entre {names[e['a']]} et {names[e['b']]} dure {e['duree']} minutes.",
                         f"Il faut {e['duree']} minutes pour aller de {names[e['a']]} à {names[e['b']]}, ou l'inverse."]) for e in ordre]
    ctx.append(f"La route entre {names[ferme['a']]} et {names[ferme['b']]} est fermée du jour {d1} au jour {d2} inclus.")
    trivial = {"defaut_sans_fermeture": shortest(ids, edges, de, vers), "dernier_vu": ordre[-1]["duree"],
               "premier_vu": ordre[0]["duree"]}
    return draft("C", "C1_itineraire", {"lieux": ids, "routes": edges, "fermee": ferme["id"], "fermeture": [d1, d2],
                                        "de": de, "vers": vers, "jour": jour}, expected, "json_int", [],
                 ["plus_court_chemin", "contrainte_temporelle"], "int", ctx,
                 {"de": names[de], "vers": names[vers], "jour": jour}, trivial)


def c2_ordonnancement(c: Ctx):
    projet = c.entity("societe")
    etapes = [c.entity("etape") for _ in range(c.rng.randint(5, 8))]
    durees = {e.id: c.rng.randint(1, 15) for e in etapes}
    prereqs = {e.id: [p.id for p in etapes[:i] if c.rng.random() < 0.35] for i, e in enumerate(etapes)}
    expected = makespan(durees, prereqs)
    names = {e.id: e.name for e in c.entities}
    ordre = etapes[:]
    c.rng.shuffle(ordre)
    ctx = ["Plusieurs étapes peuvent avancer en même temps dès que leurs prérequis sont terminés."]
    for e in ordre:
        pre = prereqs[e.id]
        s = f"L'étape {e.name} dure {durees[e.id]} jours"
        ctx.append(s + (f" et ne peut commencer qu'après la fin de {', '.join(names[p] for p in pre)}." if pre else "."))
    trivial = {"somme": sum(durees.values()), "max_duree": max(durees.values()), "dernier_vu": durees[ordre[-1].id]}
    return draft("C", "C2_ordonnancement", {"durees": durees, "prerequis": prereqs}, expected, "json_int", [],
                 ["ordonnancement", "chemin_critique"], "int", ctx, {"projet": projet.name}, trivial)


def c3_composition(c: Ctx):
    fns = [c.entity("fonction") for _ in range(4)]
    tools = [c.tool(f.name, "fonction", {"spec": {"op": "affine", "a": c.rng.randint(2, 4), "b": c.rng.randint(-9, 9)}},
                    "Fonction affine du monde.") for f in fns]
    chaine = c.rng.sample(range(4), 3)
    x = c.rng.randint(1, 20)
    journal, v = [], x
    for i in chaine:
        v = run_tool(tools[i], {"x": v}, journal)
    ordre = list(range(4))
    c.rng.shuffle(ordre)

    def txt(s):
        return f"{s['a']} × x + {s['b']}" if s["b"] >= 0 else f"{s['a']} × x − {-s['b']}"
    ctx = [f"La fonction {fns[i].name} transforme un nombre x en {txt(tools[i].params['spec'])}." for i in ordre]
    first = journal[0]["result"]
    trivial = {"question_echo": x, "premiere_seule": first, "dernier_vu": tools[ordre[-1]].params["spec"]["b"]}
    return draft("C", "C3_composition", {"tools": [tools[i].id for i in chaine], "x": x, "journal": journal}, v,
                 "json_int", [], ["composition_fonctions"], "int", ctx,
                 {"x": x, "f1": fns[chaine[0]].name, "f2": fns[chaine[1]].name, "f3": fns[chaine[2]].name}, trivial)
