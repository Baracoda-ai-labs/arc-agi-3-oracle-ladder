"""[G] CW-304 étape 1 — audit des arrêts de la recherche P0 `but`. Copie INSTRUMENTÉE de la branche `but` de
`experiments/T3.0/plafonds.p0` (même ordre, même file de priorité, même clé, mêmes coups ; fichier d'origine non modifié),
qui relève en plus : raison exacte de l'arrêt (victoire, plafond de nœuds, plafond de temps, espace épuisé), transitions,
états uniques / transitions, coups qui lèvent une erreur, issues de défaite, profondeur max atteinte, longueur du plan,
et le temps CPU par poste (copie, simulation, clé, heuristique). Contrôle : `--controle` compare nœuds et états à p0.
Variantes (variables d'environnement) : G_HEUR=gradue|regression|dependances (guidage.py) ; G_COMPACT=1 (file sérialisée,
mêmes nœuds et états) ; G_DEPARTAGE=module:fonction (départage à distance égale, pour F).
Usage : PYTHONPATH=. .venv/bin/python experiments/G/audit.py NOEUDS SECONDES PROCESSUS [jeux] [niveaux] [--controle]
→ experiments/G/audit_<noeuds>_<secondes>.json"""
import heapq
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}


def _init():
    import os
    os.chdir(RACINE / "experiments/T3.0")
    sys.path.insert(0, str(RACINE / "experiments/T3.0"))
    sys.path.insert(0, str(RACINE))


def audit(gid, k, noeuds, secondes):
    """= plafonds.p0(gid, k, noeuds, secondes, "but") sans heuristique apprise ni dominance, instrumentée ; temps CPU."""
    import plafonds as pf
    from mesure_exhaustivite import _resync

    from chrysalide.arc3.langage import Programme, utilise_canevas
    from chrysalide.arc3.logique.plan_langage import distance_but, regle_victoire
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    cle = pf.cle_complete
    T = time.process_time
    t0 = T()
    r = {"jeu": gid, "niveau": k}
    f = pf.REGLES / f"{gid}.json"
    if not f.exists():
        return {**r, "arret": "pas de programme"}
    env, fr = pf.env_au_niveau(gid, k)
    if env is None:
        return {**r, "arret": "niveau non atteint par le préfixe"}
    texte = json.loads(f.read_text())
    sc0 = _resync(env, None, utilise_canevas(texte))
    prog = ProgrammeCompile(texte)
    dispo = [a for a in fr.available_actions if a != 6 and a in pf.NOMS]
    coups = [(a, None, None) for a in dispo] + (pf.clics(fr.frame[-1]) if 6 in fr.available_actions else [])

    def nom(c):
        return ("CLICK", c[1], c[2]) if c[0] == 6 else (pf.NOMS[c[0]], None, None)
    interp, regle = Programme(texte), regle_victoire(texte)
    if regle is None:
        return {**r, "arret": "pas de règle de victoire"}
    import os
    if os.environ.get("G_HEUR") in ("gradue", "regression", "dependances"):  # CW-304 étape 3 : distance graduée lue dans la victoire (guidage.py)
        sys.path.insert(0, str(RACINE / "experiments/G"))
        from guidage import distance_graduee
        dg = distance_graduee(prog, regle, regression=0 if os.environ.get("G_HEUR") == "gradue" else 2)
        etat_p = prog.etat

        def dist(_i, _r, sc, etat):
            v = dg(sc, etat)
            prog.etat = etat  # dg a posé l'état sur prog ; inchangé (même objet)
            return v
        r["heuristique"] = os.environ.get("G_HEUR")
    elif os.environ.get("G_HEUR") == "geom":  # CW-349/350, V1 géométrique (A) : (distance dans le graphe relâché, distance)
        sys.path.insert(0, str(RACINE / "experiments/G"))
        from guidage import table_geometrique
        etat_p = prog.etat
        hg, r["geometrie"] = table_geometrique(prog, sc0, coups, nom, regle)
        prog.etat = etat_p

        def dist(i, rg, sc, etat):
            v = hg(sc)
            return (v if v is not None else 10 ** 6, distance_but(i, rg, sc, etat))
    elif os.environ.get("G_HEUR") == "hmax":  # CW-339 V1 : (h_max relâché sur l'état caché, distance au but) ; ordre seul
        sys.path.insert(0, str(RACINE / "experiments/G"))
        from guidage import hmax_etat
        hm = hmax_etat(texte, regle)
        etat_p = prog.etat
        r["heuristique"] = "hmax" if hm is not None else "hmax (but sans état caché : distance seule)"

        def dist(i, rg, sc, etat):
            d = distance_but(i, rg, sc, etat)
            return (hm(etat), d) if hm is not None else (0, d)
    else:
        dist = distance_but
        etat_p = prog.etat
    prog.etat = etat_p
    emp = None
    if os.environ.get("G_HEUR") == "dependances":  # transitions qui changent ce que lit le but : en tête, à distance égale
        from guidage import empreinte_but
        emp, r["lus_par_le_but"] = empreinte_but(prog, regle)
        prog.etat = etat_p
    h0 = dist(interp, regle, sc0, prog.etat)
    emps = {0: emp(sc0, prog.etat)} if emp else None
    prog.etat = etat_p
    p0_ = (h0, 0) if emp else h0
    if os.environ.get("G_RECHERCHE") == "bfws":
        p0_ = (0, *(p0_ if isinstance(p0_, tuple) else (p0_,)))
    if os.environ.get("G_DEPARTAGE"):
        p0_ = (*(p0_ if isinstance(p0_, tuple) else (p0_,)), 0)
    tas, compteur = [(p0_, 0, 0, sc0, prog.etat, [])], 1
    preferes = 0
    dep = None
    if os.environ.get("G_DEPARTAGE"):  # F (CW-317/318) : « module:fonction », f(scène, état, clé) → nombre ; à distance
        import importlib  # égale, le plus petit d'abord (avant la profondeur et l'ordre d'insertion)
        mod, fn = os.environ["G_DEPARTAGE"].split(":")
        sys.path.insert(0, str(RACINE / "experiments/G"))
        dep = getattr(importlib.import_module(mod), fn)
        r["departage"] = os.environ["G_DEPARTAGE"]
    domin = None
    if os.environ.get("G_DOMINANCE") == "1":  # ressources monotones lues par le but : hors clé, dominance (plus = mieux)
        sys.path.insert(0, str(RACINE / "experiments/G"))
        from guidage import lus_par_le_but, ressources_monotones
        mono = ressources_monotones(sc0, prog, coups, nom)
        prog.etat = etat_p
        filtres, noms_but = lus_par_le_but(texte, regle)
        V = prog._V
        V[0] = sc0
        lus = set()
        for f in filtres:
            try:
                lus |= {id(o) for o in prog.c(["objets", f], {})(V)}
            except Exception:  # noqa: BLE001, S112
                continue
        tous_compteurs = os.environ.get("G_DOMINANCE_ETAT") == "1"  # essai : aussi les compteurs cachés non lus par le but
        champs = [k for k in mono if (k[0] == "etat" and (k[1] in noms_but or tous_compteurs))
                  or (k[0] == "sprite" and id(sc0.sprites[k[1]]) in lus)]
        r["dominance"] = [str(k) for k in champs]
        if champs:
            domin = ({}, champs, {k: mono[k] for k in champs})
            prog.etat = etat_p

    def abstraite(scn, et):
        """(clé sans les ressources, vecteur des ressources orienté « plus = mieux »)."""
        _, ch, sg = domin
        sp = list(scn.sprites)
        e2 = dict(et or {})
        v = []
        for c_ in ch:
            if c_[0] == "sprite":
                o = dict(sp[c_[1]])
                v.append(o[c_[2]] * sg[c_])
                o[c_[2]] = 0
                sp[c_[1]] = o
            else:
                v.append((e2.pop(c_[1], 0) or 0) * sg[c_])
        s2 = type(scn).__new__(type(scn))
        s2.__dict__.update(scn.__dict__)
        s2.sprites = sp
        return cle(s2, e2), tuple(v)
    domines = 0
    bfws = os.environ.get("G_RECHERCHE") == "bfws"  # CW-318 famille 3 : (nouveauté parmi les états de même distance, distance)
    if bfws:
        sys.path.insert(0, str(RACINE / "experiments/G"))
        from guidage import faits, ressources_monotones
        exclus = frozenset((k[0], k[1]) for k in ressources_monotones(sc0, prog, coups, nom))
        prog.etat = etat_p
        r["faits_exclus"] = sorted(map(str, exclus))
        faits0 = faits(sc0, etat_p, exclus)
        largeur2 = os.environ.get("G_LARGEUR", "1") == "2"
        vus_h = {}
        nouveaux = 0
    compact = os.environ.get("G_COMPACT") == "1"  # CW-318 : file d'états sérialisés, chemin par pointeur vers le parent
    if compact:
        import io
        import pickle
        R = {}  # objets partagés de la scène de départ, référencés au lieu d'être recopiés (pixels, tags, modèles, données)
        for o in sc0.sprites:
            for v in (o.get("pixels"), o.get("tags")):
                if v is not None:
                    R[id(v)] = v
        for v in (getattr(sc0, "modeles", None), getattr(sc0, "donnees", None)):
            if v is not None:
                R[id(v)] = v

        class _P(pickle.Pickler):
            def persistent_id(self, o):
                return id(o) if id(o) in R else None

        class _U(pickle.Unpickler):
            def persistent_load(self, pid):
                return R[pid]

        def geler(scn, et):
            scn.__dict__.pop("_index_tags", None)  # index refait à la demande, comme après sim_rapide.cloner
            b = io.BytesIO()
            _P(b, protocol=5).dump((scn, et))
            return b.getvalue()

        def degeler(blob):
            return _U(io.BytesIO(blob)).load()
        parents = [None]  # n° d'ordre → (parent, coup)
        tas = [(tas[0][0], 0, 0, geler(*cloner(sc0, prog.etat)))]
        octets_max = octets = len(tas[0][3])
    vus = {cle(sc0, prog.etat)}
    t_prep = T() - t0
    tc = {"copie": 0.0, "simulation": 0.0, "cle": 0.0, "heuristique": 0.0}
    n = erreurs = defaites = doublons = prof_max = 0
    hmin, plan = (h0[-1] if isinstance(h0, tuple) else h0), None
    while tas and n < noeuds and T() - t0 < secondes:
        if compact:
            _, _g, cpt, blob = heapq.heappop(tas)
            octets -= len(blob)
            sc, etat = degeler(blob)
            chemin = _g  # seule la longueur sert pendant la recherche
        else:
            _, _g, cpt, sc, etat, chemin = heapq.heappop(tas)
        e_par = emps.pop(cpt) if emps is not None else None
        for c in coups:
            n += 1
            a = T()
            sc2, etat2 = cloner(sc, etat)
            b = T()
            prog.etat = etat2
            try:
                prog.step(sc2, nom(c))
            except Exception:  # noqa: BLE001 — comme p0 : branche abandonnée
                erreurs += 1
                tc["copie"] += b - a
                tc["simulation"] += T() - b
                continue
            d = T()
            tc["copie"] += b - a
            tc["simulation"] += d - b
            if sc2.issue in ("niveau", "victoire"):
                if compact:
                    plan, q = [c], cpt
                    while parents[q] is not None:
                        q, cc = parents[q]
                        plan.append(cc)
                    plan.reverse()
                else:
                    plan = [*chemin, c]
                break
            if sc2.issue is not None:
                defaites += 1
                continue
            kk = cle(sc2, prog.etat)
            e = T()
            tc["cle"] += e - d
            if kk in vus:
                doublons += 1
                continue
            vus.add(kk)
            if domin is not None and len(sc2.sprites) == len(sc0.sprites):
                ka, va = abstraite(sc2, prog.etat)
                deja = domin[0].setdefault(ka, [])
                if any(all(x <= y for x, y in zip(va, w, strict=True)) for w in deja):
                    domines += 1
                    continue
                deja.append(va)
            h = dist(interp, regle, sc2, prog.etat)
            if emps is not None:
                e2 = emp(sc2, prog.etat)
                rang = 0 if e2 != e_par else 1
                preferes += rang == 0
                emps[compteur] = e2
                h = (h, rang)
            if dep is not None:
                h = (*(h if isinstance(h, tuple) else (h,)), dep(sc2, prog.etat, kk))
            if bfws:
                h1 = h[0] if isinstance(h, tuple) else h
                fs = faits(sc2, prog.etat, exclus)
                deja_h, deja2_h = vus_h.setdefault(h1, (set(), set()))
                w = 0 if fs - deja_h else 2
                deja_h |= fs
                if largeur2:  # paires de faits qui diffèrent du départ (comme iw2 de plafonds), même distance
                    dyn = sorted(fs - faits0, key=repr)
                    pr = {(dyn[i], dyn[j]) for i in range(len(dyn)) for j in range(i + 1, len(dyn))}
                    if w and pr - deja2_h:
                        w = 1
                    deja2_h |= pr
                nouveaux += w == 0
                h = (w, *(h if isinstance(h, tuple) else (h,)))
            tc["heuristique"] += T() - e
            hh = h[1] if bfws else h
            hh = hh[-1] if os.environ.get("G_HEUR") in ("hmax", "geom") and isinstance(hh, tuple) else hh
            hmin = min(hmin, hh[0] if isinstance(hh, tuple) else hh)
            g2 = (chemin if compact else len(chemin)) + 1
            prof_max = max(prof_max, g2)
            if compact:
                blob = geler(sc2, prog.etat)
                octets += len(blob)
                octets_max = max(octets_max, octets)
                parents.append((cpt, c))
                heapq.heappush(tas, (h, g2, compteur, blob))
            else:
                heapq.heappush(tas, (h, g2, compteur, sc2, prog.etat, [*chemin, c]))
            compteur += 1
        if plan:
            break
    total = T() - t0
    import resource
    r["memoire_max_mo"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20)
    if compact:
        r["file_octets_max_mo"] = round(octets_max / 2 ** 20, 1)
    arret = ("plan" if plan else "plafond de nœuds" if n >= noeuds else "espace épuisé" if not tas else "plafond de temps")
    r.update(arret=arret, noeuds=n, etats=len(vus), uniques_sur_transitions=round(len(vus) / max(n, 1), 3),
             erreurs=erreurs, defaites=defaites, doublons=doublons, profondeur_max=prof_max,
             plan=None if plan is None else len(plan), h0=h0, preferes=preferes, domines=domines, nouveaux=nouveaux if bfws else None, hmin=hmin, actions=len(coups), file_restante=len(tas),
             cpu=round(total, 2), cpu_preparation=round(t_prep, 2), **{f"cpu_{x}": round(v, 2) for x, v in tc.items()})
    if plan:
        env2, _ = pf.env_au_niveau(gid, k)
        fin = None
        for c in plan:
            fin = pf.jouer(env2, c)
            if fin.levels_completed >= k or fin.state.name in ("WIN", "GAME_OVER"):
                break
        r["gagne"] = bool(fin is not None and (fin.levels_completed >= k or fin.state.name == "WIN"))
    return r


def _tache(t):
    gid, k, noeuds, secondes, controle = t
    try:
        r = audit(gid, k, noeuds, secondes)
        if controle and r.get("noeuds"):
            import plafonds as pf
            q = pf.p0(gid, k, noeuds, 10 ** 9, "but")  # plafond de nœuds seul : comparaison exacte
            r["controle_p0"] = [q.get("noeuds"), q.get("etats")] == [r["noeuds"], r["etats"]]
        return r
    except Exception as e:  # noqa: BLE001 — échec compté (C74)
        return {"jeu": gid, "niveau": k, "arret": f"erreur {type(e).__name__}: {e}"[:160]}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    controle = "--controle" in sys.argv
    noeuds, secondes, proc = int(args[0]), float(args[1]), int(args[2])
    regles = RACINE / "experiments/T3.1/regles"
    jeux = args[3].split(",") if len(args) > 3 and args[3] != "tous" and ":" not in args[3] else \
        sorted(p.stem for p in regles.glob("*.json") if "_" not in p.stem)
    jeux = [j for j in jeux if j not in TEMOINS]
    niveaux = [int(x) for x in (args[4] if len(args) > 4 else "1,2,3").split(",")]
    if len(args) > 3 and ":" in args[3]:  # liste jeu:niveau (frontières)
        paires = [(x.split(":")[0], int(x.split(":")[1])) for x in args[3].split(",")]
    else:
        paires = [(j, k) for j in jeux for k in niveaux]
    paires = [(j, k) for j, k in paires if j not in TEMOINS]
    taches = [(j, k, noeuds, secondes if not controle else 10 ** 9, controle) for j, k in paires]
    with Pool(proc, initializer=_init) as pool:
        res = []
        for r in pool.imap_unordered(_tache, taches, chunksize=1):
            res.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
    nom = "frontieres_" if len(args) > 3 and ":" in args[3] else ""
    import os
    nom += f"{os.environ['G_HEUR']}_" if os.environ.get("G_HEUR") else ""
    out = RACINE / f"experiments/G/audit_{nom}{noeuds}_{int(secondes)}{'_controle' if controle else ''}.json"
    out.write_text(json.dumps(sorted(res, key=lambda x: (x["jeu"], x["niveau"])), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
