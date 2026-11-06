"""Famille B — règles et faits temporels."""
from collections import Counter

from chrysalide.world.engine import eval_rule, holds, resolve
from chrysalide.world.schema import RELIABILITY
from chrysalide.world.structures import Ctx, draft


def b1_fait_date(c: Ctx):
    soc = c.entity("societe")
    k = c.rng.randint(4, 6)
    y = c.rng.randint(2030, 2050)
    facts = []
    for i in range(k):
        p = c.entity("personne")
        fin = None if (i == k - 1 and c.rng.random() < 0.5) else y + c.rng.randint(2, 6)
        facts.append(c.fact(soc.id, "dirigeant", p.id, y, fin))
        y = fin if fin is not None else y
    f = c.rng.choice(facts)  # intervalle interrogé, uniforme ; année strictement intérieure (pas d'ambiguïté de bord)
    annee = c.rng.randint(f.valid_from + 1, (f.valid_to - 1) if f.valid_to else f.valid_from + 4)
    expected_id = holds(c.facts, soc.id, "dirigeant", annee)
    names = {e.id: e.name for e in c.entities}
    ordre = facts[:]
    c.rng.shuffle(ordre)
    ctx = []
    for g in ordre:
        n = names[g.object]
        if g.valid_to is None:
            ctx.append(c.rng.choice([f"{n} dirige la société {soc.name} depuis {g.valid_from}.",
                                     f"Depuis {g.valid_from}, la société {soc.name} est dirigée par {n}."]))
        else:
            ctx.append(c.rng.choice([f"De {g.valid_from} à {g.valid_to}, {n} a dirigé la société {soc.name}.",
                                     f"{n} a pris la direction de {soc.name} en {g.valid_from} et l'a quittée en {g.valid_to}."]))
    trivial = {"dernier_vu": names[ordre[-1].object], "premier_vu": names[ordre[0].object],
               "plus_recent": names[max(facts, key=lambda g: g.valid_from).object]}
    return draft("B", "B1_fait_date", {"sujet": soc.id, "predicat": "dirigeant", "annee": annee}, names[expected_id],
                 "json_str", facts, ["fait_date"], "str", ctx, {"societe": soc.name, "annee": annee}, trivial)


def b2_regle_versionnee(c: Ctx):
    """Trois implantations successives, dont deux sous exception (taux distincts), et une règle en deux versions."""
    soc = c.entity("societe")
    lieux = [c.entity("lieu") for _ in range(3)]
    y0 = c.rng.randint(2030, 2045)
    bornes = [y0, y0 + c.rng.randint(3, 6)]
    bornes.append(bornes[1] + c.rng.randint(3, 6))
    loc = [c.fact(soc.id, "situee_a", lieux[i].id, bornes[i], bornes[i + 1] if i < 2 else None) for i in range(3)]
    fin = bornes[2] + 4
    y_b = c.rng.randint(y0 + 2, fin - 2)  # changement de version de la règle
    p1, p2, px, py = c.rng.sample(range(1, 30), 4)
    exo = c.rng.sample(lieux, 2)
    exc = [{"si": {"predicat": "situee_a", "objet": exo[0].id}, "taux": px},
           {"si": {"predicat": "situee_a", "objet": exo[1].id}, "taux": py}]
    r1 = c.rule("impot", 1, y0, y_b, {"taux": p1, "exceptions": exc})
    r2 = c.rule("impot", 2, y_b, None, {"taux": p2, "exceptions": exc})
    annee = c.rng.choice([t for t in range(y0 + 1, fin) if t not in (*bornes, y_b)])
    montant = 100 * c.rng.randint(10, 99)
    taux = eval_rule([r1, r2], c.facts, soc.id, annee)
    expected = montant * taux // 100
    ctx = [(f"La société {soc.name} est installée à {lieux[0].name} de {bornes[0]} à {bornes[1]}, à {lieux[1].name} de "
            f"{bornes[1]} à {bornes[2]}, puis à {lieux[2].name} depuis {bornes[2]}."),
           f"Règle d'impôt, version 1, à partir de {y0} : l'impôt vaut {p1} % du chiffre d'affaires.",
           f"Règle d'impôt, version 2, à partir de {y_b} (remplace la version 1) : l'impôt vaut {p2} % du chiffre d'affaires.",
           (f"Exceptions, valables pour toutes les versions, pendant la durée de l'installation : les sociétés installées à "
            f"{exo[0].name} paient {px} % ; celles installées à {exo[1].name} paient {py} %.")]
    active_sans_exc = p1 if annee < y_b else p2
    trivial = {"defaut": montant * p1 // 100, "sans_exception": montant * active_sans_exc // 100,
               "plus_recent": montant * p2 // 100, "dernier_vu": montant * py // 100}
    return draft("B", "B2_regle_versionnee", {"sujet": soc.id, "annee": annee, "montant": montant, "rules": [r1.id, r2.id]},
                 expected, "json_int", loc, ["regle_versionnee", "fait_date", "exception"], "int", ctx,
                 {"societe": soc.name, "annee": annee, "montant": montant}, trivial)


def b3_sources(c: Ctx):
    soc = c.entity("societe")
    lieux = [c.entity("lieu") for _ in range(3)]
    n = c.rng.randint(4, 6)
    dates = sorted(c.rng.sample(range(2030, 2060), n))
    rels = [c.rng.choices(RELIABILITY, weights=[1, 2, 3])[0] for _ in range(n)]
    vals = [c.rng.choice(lieux).id for _ in range(n)]
    conflit = c.rng.random() < 0.75
    if conflit:  # une déclaration fiable, une instruction de repli, et des témoignages concordants sur un leurre
        top, second = c.rng.sample(range(n), 2)
        v_top, v_second, leurre = [v.id for v in c.rng.sample(lieux, 3)]
        for i in range(n):
            rels[i], vals[i] = "témoignage", leurre
        rels[top], vals[top] = "fiable", v_top
        rels[second], vals[second] = "instruction", v_second
    stmts, sources = [], []
    for d, rel, v in zip(dates, rels, vals, strict=True):
        src = c.entity("source", fiabilite=rel)
        sources.append(src)
        stmts.append(c.fact(soc.id, "siege", v, d, None, src.id, rel))
    revoked, u = set(), c.rng.random()
    if conflit and u < 0.4:  # retrait de la source fiable : l'instruction de repli l'emporte
        revoked = {sources[top].id}
    elif conflit and u < 0.6:  # retrait de l'instruction : sans effet sur la réponse
        revoked = {sources[second].id}
    elif not conflit and u < 0.5:
        revoked = {c.rng.choice(sources).id}
    if all(s.source_id in revoked for s in stmts):
        revoked = set()
    names = {e.id: e.name for e in c.entities}
    expected = names[resolve(stmts, revoked)]
    ordre = stmts[:]
    c.rng.shuffle(ordre)
    ctx = [("Règle d'arbitrage : les déclarations d'une source retirée sont ignorées ; une déclaration fiable l'emporte sur "
            "une instruction, qui l'emporte sur un témoignage ; à fiabilité égale, la déclaration la plus récente l'emporte.")]
    for s in ordre:
        ctx.append(f"En {s.valid_from}, la source {names[s.source_id]} ({s.reliability}) déclare que le siège de "
                   f"{soc.name} est à {names[s.object]}.")
    ctx += [f"La source {names[r]} a été retirée : ses déclarations ne comptent plus." for r in sorted(revoked)]
    maj = Counter(names[s.object] for s in ordre).most_common(1)[0][0]
    trivial = {"dernier_vu": names[ordre[-1].object], "majorite": maj,
               "plus_recent": names[max(stmts, key=lambda s: s.valid_from).object]}
    return draft("B", "B3_sources", {"sujet": soc.id, "predicat": "siege", "revoquees": sorted(revoked)}, expected,
                 "json_str", stmts, ["arbitrage_sources", "revocation"], "str", ctx, {"societe": soc.name}, trivial)
