# SPDX-License-Identifier: MIT-0
"""D (CW-357, fusion moteur ↔ Franzen, côté Franzen) : ce que le moteur SAIT, offert à Franzen dans son outil Python,
VERSIONNÉ sur l'état. CHRYS_INSPECT=1 (éteint = Franzen inchangé). Franzen garde la main : il lit, il décide.
- `etat_pour_franzen(branche)` : dictionnaire posé sur l'agent (`analyzer._chrys_inspect`) à chaque tour de Franzen :
  version (= nombre d'entrées d'historique du harnais au moment du calcul), niveau, règles vérifiées, but, réserve,
  options (plans courts que le moteur a trouvés et vérifiés en simulation, NON joués).
- Le patch (`scripts/arc3/patcher_inspect.py`) ajoute la clé « chrysalide » à l'état du REPL et la pose en globale
  `chrysalide_etat` ; les deux fonctions ci-dessous (SOURCES) sont des fonctions retenues du REPL (mécanisme
  ARC3_PERSISTENT_FUNCTIONS), qui ne lisent que les globales du REPL, PAR LEUR NOM : le contrôle de rétention de Franzen
  rejette `globals()` (absent de ses fonctions intégrées), d'où « not defined » au passage I1 du 22/10.
- `ligne_tour(agent)` : une phrase courte au message de tour quand une option FRAÎCHE existe (« une option est
  disponible »), rien sinon."""

INSPECT_MODEL = '''def inspect_model():
    """What the Chrysalide engine knows about this level (CPU, verified rules only). `stale` = computed on an older
    state than the current one: treat it as a hint, not a fact."""
    e = chrysalide_etat or {}
    if not e:
        return {"available": False}
    return {"available": True, "stale": e.get("version") != len(history), "level": e.get("niveau"),
            "rules": e.get("regles"), "goal": e.get("but"), "goal_status": e.get("statut_but"),
            "budget_left": e.get("reserve"), "status": e.get("statut")}
'''

INSPECT_OPTIONS = '''def inspect_options():
    """Short plans the Chrysalide engine found and verified in its simulator for the CURRENT state (not played).
    Each option: actions (names), length, reaches: "goal" (win condition seen in an earlier win), "guessed_goal" (the
    engine GUESSED the win condition: the plan reaches its guess, which is often wrong) or "progress"; when the move
    budget is known, also cost
    (budget units spent, winning move free), budget_left_after and fits. Empty if none, or if computed on an older
    state (stale): replaying a stale plan is unsafe."""
    e = chrysalide_etat or {}
    if not e or e.get("version") != len(history):
        return []
    return list(e.get("options") or [])
'''

SOURCES = (INSPECT_MODEL, INSPECT_OPTIONS)
SUPPOSES = ("but_suppose", "partiel_but_suppose", "dynamique_exacte")  # origines d'un but deviné (moteur.py)
VUS = ("planifier", "plan_langage")  # but de la théorie, induit des victoires observées (moteur.py, CCM-369-A)
NOTE = ("Engine option available: inspect_options() lists a short plan the engine verified in simulation for the "
        "current state (not played); check its `reaches` field (a guessed goal may be wrong). inspect_model() shows its "
        "verified rules and goal. You decide.")


def _nom(a):
    if isinstance(a, dict):
        if str(a.get("action")).upper() in ("MOUSE", "ACTION6"):
            return f"ACTION6(x={a.get('col')}, y={a.get('row')})"
        return str(a.get("action"))
    return str(a)


def etat_pour_franzen(b):
    """Dictionnaire versionné de ce que sait le moteur (branche b), pour l'outil Python de Franzen."""
    infos = dict(getattr(b, "infos_m", None) or {})
    version = len(getattr(b.s, "history_entries", None) or [])
    options = []
    origine = infos.get("origine")
    vu = not infos.get("but_suppose") and (bool(infos.get("but")) or origine in VUS)
    suppose = not vu  # CCM-369-A : origine non tracée → deviné, par prudence
    opt = getattr(b, "option", None)
    if opt and opt.get("version") == version:
        # CW-412 (1), CCM-356-A : la simulation vérifie les règles, PAS le but ; un but supposé n'est jamais « goal »
        o = {"actions": [_nom(a) for a in opt["actions"]], "length": len(opt["actions"]),
             "reaches": ("guessed_goal" if suppose else "goal") if opt.get("but") else "progress"}
        from chrysalide.arc3.logique.economie_plan import bilan_plan  # F (CW-410) : coût au barème, réserve restante
        o.update(bilan_plan(opt["actions"], infos.get("reserve_plan")) or {})
        options.append(o)
    return {"version": version, "niveau": len(getattr(b, "precedents", []) or []) + 1,
            "regles": (infos.get("theorie") or "")[:1500] or None, "but": infos.get("but") or infos.get("but_suppose"),
            "statut_but": ("seen" if vu else "guessed") if (opt or infos.get("but") or infos.get("but_suppose")) else None,
            "reserve": infos.get("reserve_plan"), "statut": infos.get("refus") or ("plan" if options else None),
            "options": options}


def ligne_tour(agent):
    """CW-412 (2) : la phrase n'est dite que si une option NON VIDE existe pour l'état courant (jamais pour une liste vide)."""
    e = getattr(agent, "_chrys_inspect", None) or {}
    return [NOTE] if any(o.get("actions") for o in e.get("options") or []) else []
