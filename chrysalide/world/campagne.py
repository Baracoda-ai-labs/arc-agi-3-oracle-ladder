"""Monde v1 « campagne » (T1.0, étape 0 d'E1) : entités PARTAGÉES par toutes les tâches d'un monde.
Des épisodes d'apprentissage exposent les faits ; des tâches de test, de structure inédite (structure_id disjoints),
les combinent. Réponses calculées par le moteur (engine.py), jamais par un LLM. Le monde v0 (generate.py) est inchangé."""
import json
import random

from chrysalide.world.engine import eval_rule, holds, run_tool, shortest
from chrysalide.world.schema import Fact, Task, to_dict
from chrysalide.world.structures import Ctx
from chrysalide.world.surface import FORMAT, Namer, load_real

VERSION = "campagne-v1"
APPRENTISSAGE = {"A": ["A1L_conversion", "A2L_stock"], "B": ["B1L_dirigeant", "B2L_impot"], "C": ["C1L_trajet", "C3L_composition2"]}
TEST = {"A": ["A4T_conversion_chaine", "A5T_variation_stock"], "B": ["B4T_dirigeant_installation", "B5T_impot_prise_direction"],
        "C": ["C4T_composition3", "C5T_trajet_etape"]}


class Monde:
    def __init__(self, seed, real=None):
        self.rng = random.Random(seed)
        self.c = Ctx(self.rng, Namer(self.rng, load_real() if real is None else real))
        self.lignes = {}  # id de fait -> phrase canonique (ce que l'agent peut apprendre)
        self._construire()

    def _ligne(self, fact_or_id, texte):
        fid = fact_or_id.id if isinstance(fact_or_id, Fact) else fact_or_id
        self.lignes[fid] = texte
        return fid

    # ---------------- état du monde ----------------
    def _construire(self):
        c, r = self.c, self.rng
        # A : bureaux de change (taux propres à chaque bureau) et entrepôts
        self.devises = [c.entity("devise") for _ in range(5)]
        self.bureaux = []
        for _ in range(3):
            lieu = c.entity("lieu")
            val = dict(zip([d.id for d in self.devises], r.sample(range(2, 13), 5), strict=True))
            com = r.randint(1, 9)
            t = c.tool(f"bureau de change de {lieu.name}", "taux_change", {"valeurs": val, "commission": com},
                       "Convertit un montant d'une devise dans une autre via l'unité de compte, puis retire la commission fixe.")
            ids = [self._ligne(c.fact(t.id, "taux", v, source_id=d), f"Au bureau de change de {lieu.name}, une unité de "
                               f"{self._nom(d)} vaut {v} unités de compte.") for d, v in val.items()]
            ids.append(self._ligne(c.fact(t.id, "commission", com), f"Au bureau de change de {lieu.name}, un échange est une "
                                   f"seule opération : la commission fixe de {com} unités de la devise obtenue est retirée une seule fois."))
            self.bureaux.append((lieu, t, ids))
        self.entrepots = []
        for _ in range(5):
            lieu, prod = c.entity("lieu"), c.entity("produit")
            init, stock, mv = r.randint(30, 90), 0, []
            stock = init
            for j in sorted(r.sample(range(1, 40), 6)):
                q = r.randint(3, 25) * r.choice([1, -1])
                q = -q if stock + q < 0 else q
                annule = r.random() < 0.2
                stock += 0 if annule else q
                mv.append({"jour": j, "qte": q, "annule": annule})
            t = c.tool(f"registre de l'entrepôt de {lieu.name}", "registre", {"initial": init, "mouvements": mv},
                       "Renvoie le stock à la fin d'un jour donné : stock initial plus mouvements non annulés jusqu'à ce jour.")
            ids = [self._ligne(c.fact(t.id, "initial", init), f"Registre de l'entrepôt de {lieu.name}, caisses de {prod.name} : "
                               f"stock initial de {init} caisses.")]
            for m in mv:
                sens = "entrée" if m["qte"] > 0 else "sortie"
                ids.append(self._ligne(c.fact(t.id, "mouvement", m["qte"], m["jour"]), f"Entrepôt de {lieu.name}, jour {m['jour']} : "
                                       f"{sens} de {abs(m['qte'])} caisses de {prod.name}" + (" (opération annulée)." if m["annule"] else ".")))
            self.entrepots.append((lieu, prod, t, ids))
        # B : sociétés, dirigeants datés, implantations datées, une règle d'impôt commune (2 versions + exceptions)
        self.lieux_b = [c.entity("lieu") for _ in range(6)]
        self.y_b = 2046
        self.exo = r.sample(self.lieux_b, 3)
        p1, p2, *pe = r.sample(range(5, 30), 5)
        exc = [{"si": {"predicat": "situee_a", "objet": e.id}, "taux": t} for e, t in zip(self.exo, pe, strict=True)]
        self.regles = [c.rule("impot", 1, 2030, self.y_b, {"taux": p1, "exceptions": exc}),
                       c.rule("impot", 2, self.y_b, None, {"taux": p2, "exceptions": exc})]
        self.ids_regles = [self._ligne("R_v1", f"Règle d'impôt, version 1, de 2030 à {self.y_b} : l'impôt vaut {p1} % du chiffre d'affaires."),
                           self._ligne("R_v2", f"Règle d'impôt, version 2, à partir de {self.y_b} : l'impôt vaut {p2} % du chiffre d'affaires."),
                           self._ligne("R_exc", "Exceptions de la règle d'impôt, toutes versions : " + " ; ".join(
                               f"les sociétés installées à {e.name} paient {t} %" for e, t in zip(self.exo, pe, strict=True)) + ".")]
        self.societes = []
        for _ in range(12):
            soc = c.entity("societe")
            y, dirs = r.randint(2030, 2036), []
            for i in range(6):  # 6 mandats courts : le dirigeant change entre deux installations, le dernier arrive tard
                p = c.entity("personne")
                fin = None if i == 5 else y + r.randint(2, 5)
                f = c.fact(soc.id, "dirigeant", p.id, y, fin)
                txt = (f"De {y} à {fin}, {p.name} a dirigé la société {soc.name}." if fin else
                       f"{p.name} dirige la société {soc.name} depuis {y}.")
                dirs.append((f, p, self._ligne(f, txt)))
                if fin is None:
                    break
                y = fin
            # implantation dès la création ; séjours de 5 à 9 ans : on déménage après la fin du premier mandat (2 à 5 ans)
            locs, y = [], dirs[0][0].valid_from + r.randint(0, 2)
            for i, lieu in enumerate(r.sample(self.lieux_b, 3)):
                fin = None if i == 2 else y + (r.randint(5, 9) if i == 0 else r.randint(3, 6))
                f = c.fact(soc.id, "situee_a", lieu.id, y, fin)
                txt = (f"La société {soc.name} est installée à {lieu.name} de {y} à {fin}." if fin else
                       f"La société {soc.name} est installée à {lieu.name} depuis {y}.")
                locs.append((f, lieu, self._ligne(f, txt)))
                y = fin
            self.societes.append((soc, dirs, locs))
        # C : fonctions affines (outils) et un réseau routier
        self.fonctions = []
        for _ in range(8):
            e = c.entity("fonction")
            a, b = r.randint(2, 4), r.randint(-9, 9)
            t = c.tool(e.name, "fonction", {"spec": {"op": "affine", "a": a, "b": b}}, "Fonction affine du monde.")
            txt = f"La fonction {e.name} transforme un nombre x en {a} × x " + (f"+ {b}." if b >= 0 else f"− {-b}.")
            self.fonctions.append((t, self._ligne(c.fact(t.id, "definition", f"{a},{b}"), txt)))
        self.villes = [c.entity("lieu") for _ in range(9)]
        ids = [v.id for v in self.villes]
        self.routes, seen = [], set()
        for i in range(1, 9):  # arbre couvrant, puis 7 raccourcis
            self._route(ids[i], ids[r.randrange(i)], seen)
        while len(self.routes) < 15:
            self._route(*r.sample(ids, 2), seen)

    def _route(self, a, b, seen):
        if frozenset((a, b)) in seen:
            return
        seen.add(frozenset((a, b)))
        e = {"a": a, "b": b, "duree": self.rng.randint(10, 60), "id": len(self.routes)}
        e["fid"] = self._ligne(f"ROUTE{e['id']:02d}", f"La route entre {self._nom(a)} et {self._nom(b)} dure {e['duree']} minutes.")
        self.routes.append(e)

    def _nom(self, eid):
        return next(e.name for e in self.c.entities if e.id == eid)

    def dist(self, a, b):
        return shortest([v.id for v in self.villes], self.routes, a, b)

    # ---------------- épisodes d'apprentissage ----------------
    def episodes(self, n_par_structure):
        r, out = self.rng, []

        def ep(fam, sid, fids, q, rep):
            out.append({"id": f"EP{len(out) + 1:05d}", "family": fam, "structure_id": sid, "fact_ids": fids,
                        "context": [self.lignes[i] for i in fids], "question": q, "answer": rep})
        for k in range(n_par_structure):
            lieu, t, ids = self.bureaux[k % 3]
            d1, d2 = r.sample(self.devises, 2)
            m = r.randint(2, 30) * t.params["valeurs"][d2.id]
            ep("A", "A1L_conversion", ids, f"On échange {m} {d1.name}s contre des {d2.name}s au bureau de change de {lieu.name}. "
               "Combien en obtient-on ?", run_tool(t, {"montant": m, "de": d1.id, "vers": d2.id}, []))
            lieu, prod, t, ids = self.entrepots[k % 5]
            j = r.randint(1, 40)
            ep("A", "A2L_stock", ids, f"Quel est le stock de {prod.name} à l'entrepôt de {lieu.name} à la fin du jour {j} ?",
               run_tool(t, {"jour": j}, []))
            soc, dirs, locs = self.societes[k % 12]
            f, _p, _ = r.choice(dirs)
            an = r.randint(f.valid_from, (f.valid_to or f.valid_from + 5) - 1)
            ep("B", "B1L_dirigeant", [x[2] for x in dirs], f"Qui dirigeait la société {soc.name} en {an} ?",
               self._nom(holds(self.c.facts, soc.id, "dirigeant", an)))
            an, mt = r.randint(2031, 2058), 100 * r.randint(10, 99)
            if holds(self.c.facts, soc.id, "situee_a", an) is not None:
                ep("B", "B2L_impot", [x[2] for x in locs] + self.ids_regles, f"Quel impôt la société {soc.name} doit-elle pour "
                   f"{an}, sur un chiffre d'affaires de {mt} ?", mt * eval_rule(self.regles, self.c.facts, soc.id, an) // 100)
            v1, v2 = r.sample(self.villes, 2)
            ep("C", "C1L_trajet", [e["fid"] for e in self.routes], f"En minutes, combien dure au mieux le trajet de {v1.name} à "
               f"{v2.name} ?", self.dist(v1.id, v2.id))
            (t1, i1), (t2, i2) = self.fonctions[k % 8], self.fonctions[(k + 1 + k // 8) % 8]
            if t1.id != t2.id:
                x = r.randint(1, 20)
                y = run_tool(t2, {"x": run_tool(t1, {"x": x}, [])}, [])
                ep("C", "C3L_composition2", [i1, i2], f"Calcule la valeur obtenue quand on applique {t1.name} à {x}, puis {t2.name} "
                   "au résultat.", y)
        return out

    # ---------------- tâches de test (structures inédites) ----------------
    def tests(self, n_par_structure):
        out = []

        def test(fam, sid, fids, q, expected, answer_type, trivial, inputs):
            fmt = FORMAT[answer_type]
            ctx = [self.lignes[i] for i in fids]
            out.append(Task(f"V{len(out) + 1:05d}", fam, sid, inputs, expected, "json_int" if answer_type == "int" else "json_str",
                            fids, [sid], answer_type, "\n".join(ctx) + "\n\n" + q + "\n" + fmt, q + "\n" + fmt, ctx, trivial))
        for k in range(n_par_structure):  # exactement n par structure : un tirage sans cas non ambigu est retiré
            for f in (self._a4, self._a5, self._b4, self._b5, self._c4, self._c5):
                for _ in range(20):
                    if f(test) is not False:
                        break
        return out

    def _a4(self, test):
        r = self.rng
        (l1, t1, i1), (l2, t2, i2) = r.sample(self.bureaux, 2)
        d1, d2, d3 = r.sample(self.devises, 3)
        v1, v2 = t1.params["valeurs"], t2.params["valeurs"]
        for _ in range(200):  # montant tel que les deux conversions tombent juste
            m = r.randint(2, 40) * v1[d2.id]
            mid = run_tool(t1, {"montant": m, "de": d1.id, "vers": d2.id}, [])
            if mid > 0 and (mid * v2[d2.id]) % v2[d3.id] == 0:
                break
        else:
            return False
        fin = run_tool(t2, {"montant": mid, "de": d2.id, "vers": d3.id}, [])
        triv = {"premiere_etape": mid, "question_echo": m, "sans_commission": (m * v1[d1.id] // v1[d2.id]) * v2[d2.id] // v2[d3.id]}
        test("A", "A4T_conversion_chaine", i1 + i2, f"On change {m} {d1.name}s en {d2.name}s au bureau de change de {l1.name}, puis "
             f"on change tout le résultat en {d3.name}s au bureau de change de {l2.name}. Combien de {d3.name}s obtient-on ?",
             fin, "int", triv, {"etapes": [[t1.id, d1.id, d2.id, m], [t2.id, d2.id, d3.id, mid]], "outils": [t1.id, t2.id]})

    def _a5(self, test):
        r = self.rng
        lieu, prod, t, ids = r.choice(self.entrepots)
        j1, j2 = sorted(r.sample(range(1, 41), 2))
        if not any(j1 < m["jour"] <= j2 and not m["annule"] for m in t.params["mouvements"]):
            return False  # variation nulle par construction : « zéro » suffirait
        s1, s2 = run_tool(t, {"jour": j1}, []), run_tool(t, {"jour": j2}, [])
        triv = {"zero": 0, "stock_final": s2, "stock_initial": t.params["initial"]}
        test("A", "A5T_variation_stock", ids, f"De combien le stock de {prod.name} à l'entrepôt de {lieu.name} a-t-il varié entre la fin "
             f"du jour {j1} et la fin du jour {j2} ? (négatif s'il a baissé)", s2 - s1, "int", triv, {"outil": t.id, "jours": [j1, j2], "outils": [t.id]})

    def _b4(self, test):
        r = self.rng
        for _ in range(100):
            soc, dirs, locs = r.choice(self.societes)
            f, lieu, fid = r.choice(locs[1:])
            an = f.valid_from
            bornes = {d.valid_from for d, _, _ in dirs} | {d.valid_to for d, _, _ in dirs}
            if an not in bornes and holds(self.c.facts, soc.id, "dirigeant", an):
                break
        else:
            return False
        rep = self._nom(holds(self.c.facts, soc.id, "dirigeant", an))
        triv = {"premier": dirs[0][1].name, "dernier": dirs[-1][1].name,
                "a_l_installation_precedente": self._nom(holds(self.c.facts, soc.id, "dirigeant", locs[0][0].valid_from) or dirs[0][1].id)}
        test("B", "B4T_dirigeant_installation", [x[2] for x in dirs] + [fid], f"Qui dirigeait la société {soc.name} l'année où elle "
             f"s'est installée à {lieu.name} ?", rep, "str", triv, {"sujet": soc.id, "annee": an})

    def _b5(self, test):
        r = self.rng
        veut_exo = r.random() < 0.8  # proportion fixée d'abord : 80 % des cas en lieu d'exception
        for _ in range(200):
            soc, dirs, locs = r.choice(self.societes)
            f, p, fid = r.choice(dirs[1:])
            an = f.valid_from
            bornes = {x.valid_from for x, _, _ in locs} | {x.valid_to for x, _, _ in locs} | {self.y_b}
            lieu = holds(self.c.facts, soc.id, "situee_a", an)
            if an not in bornes and lieu and (lieu in [e.id for e in self.exo]) == veut_exo:
                break
        else:
            return False
        mt = 100 * r.randint(10, 99)
        taux = eval_rule(self.regles, self.c.facts, soc.id, an)
        base = self.regles[0].body["taux"] if an < self.y_b else self.regles[1].body["taux"]
        triv = {"sans_exception": mt * base // 100, "version1": mt * self.regles[0].body["taux"] // 100,
                "version2": mt * self.regles[1].body["taux"] // 100}
        test("B", "B5T_impot_prise_direction", [fid] + [x[2] for x in locs] + self.ids_regles, f"Quel impôt la société {soc.name} "
             f"a-t-elle dû, sur un chiffre d'affaires de {mt}, l'année où {p.name} en a pris la direction ?", mt * taux // 100, "int",
             triv, {"sujet": soc.id, "annee": an, "montant": mt})

    def _c4(self, test):
        r = self.rng
        ch = r.sample(self.fonctions, 3)
        x = v = r.randint(1, 20)
        for t, _ in ch:
            v = run_tool(t, {"x": v}, [])
        triv = {"premiere_seule": run_tool(ch[0][0], {"x": x}, []), "question_echo": x,
                "deux_premieres": run_tool(ch[1][0], {"x": run_tool(ch[0][0], {"x": x}, [])}, [])}
        test("C", "C4T_composition3", [i for _, i in ch], f"Calcule la valeur obtenue quand on applique {ch[0][0].name} à {x}, puis "
             f"{ch[1][0].name} au résultat, puis {ch[2][0].name}.", v, "int", triv, {"chaine": [t.id for t, _ in ch], "x": x,
                                                   "outils": [t.id for t, _ in self.fonctions]})

    def _c5(self, test):
        r = self.rng
        for _ in range(100):
            a, w, b = r.sample(self.villes, 3)
            direct, via = self.dist(a.id, b.id), self.dist(a.id, w.id) + self.dist(w.id, b.id)
            if via != direct:  # l'étape impose un détour : ignorer la contrainte ne suffit pas
                break
        else:
            return False
        triv = {"sans_etape": direct, "premier_troncon": self.dist(a.id, w.id), "mode_route": 35}
        test("C", "C5T_trajet_etape", [e["fid"] for e in self.routes], f"En minutes, combien dure au mieux un trajet de {a.name} à "
             f"{b.name} en passant obligatoirement par {w.name} ?", via, "int", triv, {"de": a.id, "par": w.id, "vers": b.id})


def generate_campagne(seed, n_episodes=100, n_tests=50, real=None):
    """n_episodes et n_tests : par structure (les tâches de test d'E1 en retiennent 35 par structure = 70 par famille)."""
    m = Monde(seed, real)
    eps = m.episodes(n_episodes)
    tests = m.tests(n_tests)
    return {"meta": {"generator": VERSION, "n_episodes": len(eps), "n_tests": len(tests), "noms_rejetes": m.c.namer.rejected,
                     "apprentissage": APPRENTISSAGE, "test": TEST},
            "faits": m.lignes, "entities": [to_dict(e) for e in m.c.entities], "facts": [to_dict(f) for f in m.c.facts],
            "rules": [to_dict(x) for x in m.c.rules], "tools": [to_dict(t) for t in m.c.tools],
            "routes": [{k: e[k] for k in ("a", "b", "duree", "id")} for e in m.routes],
            "episodes": eps, "tasks": [to_dict(t) for t in tests]}


def main():
    import argparse
    import pathlib
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    a = ap.parse_args()
    w = generate_campagne(a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    p = a.out / f"campagne_s{a.seed}.json"
    p.write_text(json.dumps(w, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{p} : {len(w['episodes'])} épisodes, {len(w['tasks'])} tâches de test, {len(w['faits'])} faits")


if __name__ == "__main__":
    main()
