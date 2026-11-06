# SPDX-License-Identifier: MIT-0
"""Diagnostic à étages du blocage (CW-163) et actions de la boucle V1 (CW-162), CHRYS_BOUCLE=1 (avec CHRYS_MOTEUR=1).

`diagnostic(contexte) -> (etage, test, details)` teste du bas vers le haut les étages 0 Échelle … 5 Niveau et rend le
PREMIER étage fautif (None, None, details si aucun). Sans oracle : seuls l'historique observé et ce que le moteur expose.
Points d'extension (C et B) :
  - `enregistrer_test(etage, nom, fn, avant=False)` : fn(contexte) -> "sain" | "faute" | "inconnu" ou (statut, details) ;
    une exception ou un statut inconnu = « inconnu », qui ne bloque pas (on passe au test suivant).
  - `enregistrer_action(etage, nom, fn, avant=True)` : fn(contexte) -> None (pas d'action, on essaie la suivante) ou dict :
      {"proposition": (plan, programme) | None, "infos": {...}}  -> jugée par les portes 1 et 2 de branche.py ;
      {"experience": [action de Franzen, …]}                    -> coups d'expérience joués sans modèle (budget de coups) ;
      {"tuto": True}                                              -> mini-tutoriel (si CHRYS_TUTO) ;
    clé `None` = action quand aucun étage n'est fautif.
contexte (dict, construit par branche.py) : moteur, grilles, lots, precedents (niveau courant), raison du blocage,
contre (contre-exemple vu), suivi (théorie vérifiée suivie), dernier (dernier jugement : r_none, porte1, porte2, faible,
plan), infos (dernières infos du moteur), inconnues, tuto (bool), tour, cpu_restant_s, coups_restants, branche."""
import inspect

import numpy as np

SAIN, FAUTE, INCONNU = "sain", "faute", "inconnu"
ETAGES = {0: "echelle", 1: "perception", 2: "regles", 3: "but", 4: "plan", 5: "niveau"}
TESTS = {e: [] for e in ETAGES}
ACTIONS = {**{e: [] for e in ETAGES}, None: []}


def enregistrer_test(etage, nom, fn, avant=False):
    TESTS[etage].insert(0, (nom, fn)) if avant else TESTS[etage].append((nom, fn))


def enregistrer_action(etage, nom, fn, avant=True):
    ACTIONS[etage].insert(0, (nom, fn)) if avant else ACTIONS[etage].append((nom, fn))


def _statut(x):
    s, d = (x if isinstance(x, tuple) else (x, {}))
    return (s, dict(d or {})) if s in (SAIN, FAUTE, INCONNU) else (INCONNU, {"statut_rendu": str(s)[:80]})


def diagnostic(contexte, tests=None):
    """→ (etage, test, details) du premier test « faute », étages 0 → 5 ; details["resultats"] = tous les tests joués."""
    tests = TESTS if tests is None else tests
    res = []
    for e in sorted(tests):
        for nom, fn in tests[e]:
            try:
                s, d = _statut(fn(contexte))
            except Exception as x:  # noqa: BLE001 — un test qui plante ne conclut pas
                s, d = INCONNU, {"erreur": f"{type(x).__name__}: {x}"[:160]}
            res.append({"etage": e, "test": nom, "statut": s})
            if s == FAUTE:
                return e, nom, {**d, "resultats": res}
    return None, None, {"resultats": res}


def agir(etage, contexte, actions=None):
    """→ (nom, résultat) de la 1re action de l'étage qui rend un dict ; (None, None) si aucune."""
    actions = ACTIONS if actions is None else actions
    for nom, fn in actions.get(etage, ()):
        try:
            r = fn(contexte)
        except Exception:  # noqa: BLE001 — action impossible : on essaie la suivante
            r = None
        if isinstance(r, dict):
            return nom, r
    return None, None


# ------------------------------------------------------------ tests par défaut (sans oracle)
def echelle_blocs(ctx):
    """Étage 0 : chaque case (taille s, origine ox, oy) de la dernière image est d'une seule couleur (cases masquées
    exceptées). Lit `moteur.tr` (perception de C) ; inconnu si le moteur n'expose pas d'échelle."""
    tr = getattr(ctx["moteur"], "tr", None)
    if tr is None or not ctx["grilles"]:
        return INCONNU
    g, s, ox, oy = np.asarray(ctx["grilles"][-1]), int(tr.s), int(tr.ox), int(tr.oy)
    w, h = tr.taille
    exclues = set(getattr(tr, "exclues", ()) or ())
    mauvais = 0
    for r in range(h):
        for q in range(w):
            if (r, q) in exclues:
                continue
            b = g[oy + r * s:oy + (r + 1) * s, ox + q * s:ox + (q + 1) * s]
            mauvais += bool(b.size and (b != b.flat[0]).any())
    return (FAUTE if mauvais else SAIN), {"blocs_non_uniformes": mauvais, "s": s, "ox": ox, "oy": oy}


def relecture_pixel(ctx):
    """Étage 1 (a) : la scène perçue par le moteur sur chaque image du niveau, redessinée, redonne-t-elle l'image ?"""
    m = ctx["moteur"]
    if not ctx["grilles"] or not all(hasattr(m, k) for k in ("scene", "rendu", "vue")):
        return INCONNU
    faux = []
    for i, g in enumerate(ctx["grilles"]):
        try:
            ok = np.array_equal(m.rendu(m.scene(g)), m.vue(g))
        except Exception:  # noqa: BLE001 — perception non exposée pour cette image : on ne conclut pas
            return INCONNU, {"image": i}
        if not ok:
            faux.append(i)
    return (FAUTE if faux else SAIN), {"images_fausses": faux[:10], "n_images": len(ctx["grilles"])}


def porte1_refusee(ctx):
    """Étage 2 : (perception saine, testée avant) la théorie ne rejoue pas le niveau (porte 1 refusée, contre-exemple)."""
    d = ctx.get("dernier") or {}
    if d.get("porte1") is False or ctx.get("contre"):
        return FAUTE, {"porte1": d.get("porte1"), "contre": bool(ctx.get("contre"))}
    return SAIN if d.get("porte1") is True or ctx.get("suivi") else INCONNU


def porte2_refusee(ctx):
    """Étage 3 : porte 1 passée mais aucun plan gagnant en simulation (porte 2 refusée, ou sans_but)."""
    d = ctx.get("dernier") or {}
    if (d.get("porte1") is True and d.get("porte2") is False) or ctx.get("raison") == "sans_but" \
            or (ctx.get("infos") or {}).get("sans_but"):
        return FAUTE, {"porte2": d.get("porte2")}
    return SAIN if d.get("porte2") is True else INCONNU


def sans_plan(ctx):
    """Étage 4 : le moteur n'a pas trouvé de plan dans son budget."""
    d, refus = ctx.get("dernier") or {}, str((ctx.get("infos") or {}).get("refus") or "")
    if ctx.get("raison") == "sans_plan" or (d.get("r_none") and ("pas de plan" in refus or "budget" in refus)):
        return FAUTE, {"refus": refus[:120]}
    return SAIN if d.get("plan") else INCONNU


def classes_inconnues(ctx):
    """Étage 5 : classes de la 1re image du niveau que la théorie des niveaux réussis ignore."""
    if not ctx.get("precedents"):
        return INCONNU
    inc = ctx.get("inconnues") or set()
    return (FAUTE, {"classes": sorted(int(c) for c in inc)}) if inc else SAIN


# ------------------------------------------------------------ actions par défaut
def _accepte(fn, nom):
    try:
        p = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return nom in p or any(x.kind is inspect.Parameter.VAR_KEYWORD for x in p.values())


def reproposer(ctx, etage=None):
    """Réappelle `moteur.proposer` sur l'historique du niveau, budget CPU doublé à chaque tour (si le moteur a un attribut
    `budget`, borné par le CPU restant de la boucle) et option `etage=` si sa signature l'accepte."""
    from chrysalide.arc3.moteur import budget_s
    m = ctx["moteur"]
    kw = {"etage": etage} if etage is not None and _accepte(m.proposer, "etage") else {}
    a_budget = hasattr(m, "budget")
    ancien = getattr(m, "budget", None)
    if a_budget:
        base = ancien if ancien is not None else budget_s()
        m.budget = max(0.2, min(base * 2 ** (int(ctx.get("tour", 1))), float(ctx.get("cpu_restant_s", base))))
    try:
        r = m.proposer({"grilles": list(ctx["grilles"]), "lots": list(ctx["lots"]),
                        "precedents": list(ctx["precedents"])}, **kw)
    finally:
        if a_budget:
            m.budget = ancien
    return {"proposition": r, "infos": dict(getattr(m, "infos", {}) or {}), "budget": getattr(m, "budget", None)}


def tutoriel(ctx):
    """Étage 5 : mini-tutoriel (B) s'il est allumé ; sinon rien (l'action suivante est essayée)."""
    return {"tuto": True} if ctx.get("tuto") else None


for _e, _n, _f in ((0, "echelle_blocs", echelle_blocs), (1, "relecture_pixel", relecture_pixel),
                   (2, "porte1_refusee", porte1_refusee), (3, "porte2_refusee", porte2_refusee),
                   (4, "sans_plan", sans_plan), (5, "classes_inconnues", classes_inconnues)):
    enregistrer_test(_e, _n, _f)
for _e in ACTIONS:
    enregistrer_action(_e, "reproposer", lambda c, _e=_e: reproposer(c, _e), avant=False)
enregistrer_action(5, "tutoriel", tutoriel)
