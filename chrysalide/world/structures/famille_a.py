"""Famille A — outils et code exécutable."""
from chrysalide.world.engine import eval_fn, run_tool, to_python
from chrysalide.world.structures import Ctx, draft, last_number


def a1_conversion(c: Ctx):
    lieu = c.entity("lieu")
    devs = [c.entity("devise") for _ in range(3)]
    valeurs = dict(zip([d.id for d in devs], c.rng.sample(range(2, 13), 3), strict=True))  # taux distincts
    de, vers = c.rng.sample(devs, 2)
    commission = c.rng.randint(1, 9)
    tool = c.tool(f"bureau de change de {lieu.name}", "taux_change", {"valeurs": valeurs, "commission": commission},
                  "Convertit un montant d'une devise dans une autre via l'unité de compte, puis retire la commission fixe.")
    k = c.rng.randint(2, 30)
    montant = k * valeurs[vers.id]
    journal = []
    expected = run_tool(tool, {"de": de.id, "vers": vers.id, "montant": montant}, journal)
    ordre = devs[:]
    c.rng.shuffle(ordre)
    ctx = [f"Au bureau de change de {lieu.name}, une unité de {d.name} vaut {valeurs[d.id]} unités de compte." for d in ordre]
    # v0.1 (T0.6) : « à chaque conversion » laissait croire à deux commissions (aller vers l'unité de compte, puis retour).
    ctx.append(f"Un échange d'une devise contre une autre est une seule opération : le bureau calcule la valeur en unités "
               f"de compte, la convertit dans la devise demandée, puis retire une seule fois une commission fixe de "
               f"{commission} unités de la devise obtenue.")
    trivial = {"question_echo": montant, "sans_commission": k * valeurs[de.id], "dernier_vu": last_number(ctx)}
    return draft("A", "A1_conversion", {"tools": [tool.id], "args": journal[0]["args"], "journal": journal}, expected,
                 "json_int", [], ["lecture_outil", "arithmetique"], "int", ctx,
                 {"lieu": lieu.name, "montant": montant, "de": de.name + "s", "vers": vers.name + "s"}, trivial)


def a2_registre(c: Ctx):
    lieu, produit = c.entity("lieu"), c.entity("produit")
    stock = initial = c.rng.randint(20, 80)
    jours = sorted(c.rng.sample(range(1, 40), c.rng.randint(5, 7)))
    mouvements = []
    for j in jours:
        q = c.rng.randint(3, 25) * c.rng.choice([1, -1])
        if stock + q < 0:
            q = -q
        annule = c.rng.random() < 0.25
        stock += 0 if annule else q
        mouvements.append({"jour": j, "qte": q, "annule": annule})
    tool = c.tool(f"registre de l'entrepôt de {lieu.name}", "registre", {"initial": initial, "mouvements": mouvements},
                  "Renvoie le stock à la fin d'un jour donné : stock initial plus mouvements non annulés jusqu'à ce jour.")
    i = c.rng.randint(1, len(jours) - 1)
    jour = c.rng.randint(jours[i - 1], jours[i] - 1)
    journal = []
    expected = run_tool(tool, {"jour": jour}, journal)
    ctx = [f"Registre de l'entrepôt de {lieu.name}, caisses de {produit.name} : stock initial de {initial} caisses."]
    for m in mouvements:
        sens = "entrée" if m["qte"] > 0 else "sortie"
        ctx.append(f"Jour {m['jour']} : {sens} de {abs(m['qte'])} caisses" + (" (opération annulée)." if m["annule"] else "."))
    trivial = {"defaut_initial": initial, "tout_le_registre": initial + sum(m["qte"] for m in mouvements),
               "dernier_vu": abs(mouvements[-1]["qte"])}
    return draft("A", "A2_registre", {"tools": [tool.id], "args": {"jour": jour}, "journal": journal}, expected,
                 "json_int", [], ["lecture_outil", "filtrage_temporel"], "int", ctx,
                 {"lieu": lieu.name, "produit": produit.name, "jour": jour}, trivial)


def _affine(c, lo_a, hi_a, lo_b, hi_b):
    return {"op": "affine", "a": c.rng.randint(lo_a, hi_a), "b": c.rng.randint(lo_b, hi_b)}


def a3_code(c: Ctx):
    soc, fn = c.entity("societe"), c.entity("fonction")
    spec = {"op": "seuil", "seuil": c.rng.randint(10, 50), "sous": _affine(c, 2, 5, 0, 9), "sur": _affine(c, 1, 4, -20, 20)}
    s = spec["seuil"]
    xs = sorted({0, 1, s - 1, s, s + 1, *c.rng.sample(range(2, 120), 5)})
    tests = [[x, eval_fn(spec, x)] for x in xs]

    def txt(a):
        return f"{a['a']} × x + {a['b']}" if a["b"] >= 0 else f"{a['a']} × x − {-a['b']}"
    ctx = [(f"Chez {soc.name}, le tarif {fn.name} d'une commande de x pièces se calcule ainsi : "
            f"si x est strictement inférieur à {s}, le tarif vaut {txt(spec['sous'])} ; sinon il vaut {txt(spec['sur'])}.")]
    trivial = {"identite": f"def {fn.name}(x):\n    return x\n",
               "defaut_premiere_branche": to_python(spec["sous"], fn.name)}
    return draft("A", "A3_code", {"spec": spec, "solution": to_python(spec, fn.name)},
                 {"fonction": fn.name, "tests": tests}, "pytest_fn", [], ["ecriture_code", "regle_a_seuil"], "code", ctx,
                 {"fonction": fn.name, "societe": soc.name}, trivial)
