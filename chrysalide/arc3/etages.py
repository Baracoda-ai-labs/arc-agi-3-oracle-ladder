# SPDX-License-Identifier: MIT-0
"""Trois étages d'un programme du langage (CW-132) : 1 = `regles` (lois communes à tous les niveaux), 2 = section `niveau`
(paramètres propres au niveau, lus par ["param", clé]), 3 = stratégies. Règle d'honnêteté (CW-121) : une donnée propre à un
niveau écrite dans les lois est une échappatoire. `echappatoires_niveau(programme)` les détecte dans `regles`, `au_debut`
et les corps de `mots` : comparaison de ["niveau"] à une constante, table / elem / appartenance indexés par ["niveau"],
si / si_alors dont la condition est ["niveau"] nu. Contrôle syntaxique : il ne voit pas un indice de niveau caché dans l'état."""

_COMPAR = ("=", "!=", "<", "<=", ">", ">=")
_ARITH = ("+", "-", "*", "//", "%")


def _const(t):
    """Littéral (nombre, chaîne non variable, dict) ou ["liste", constantes…]."""
    if isinstance(t, list):
        return bool(t) and t[0] == "liste" and all(_const(u) for u in t[1:])
    return not (isinstance(t, str) and t.startswith("$"))


def _liste_const(t):
    """Liste de données littérale ([a, b, …] sans tête de mot) ou ["liste", constantes…]."""
    if isinstance(t, list) and t and t[0] == "liste":
        return _const(t)
    return isinstance(t, list) and not (t and isinstance(t[0], str))


def _de_niveau(t):
    """["niveau"], ou arithmétique de ["niveau"] avec des constantes (["+", ["niveau"], 1]…)."""
    if t == ["niveau"]:
        return True
    return (isinstance(t, list) and len(t) == 3 and t[0] in _ARITH and any(_de_niveau(u) for u in t[1:])
            and all(_de_niveau(u) or _const(u) for u in t[1:]))


def _motif(t):
    op, a = t[0], t[1:]
    if op in _COMPAR and len(a) == 2 and ((_de_niveau(a[0]) and _const(a[1])) or (_de_niveau(a[1]) and _const(a[0]))):
        return f"comparaison {op} de niveau à une constante"
    if op == "table" and len(a) >= 2 and _de_niveau(a[1]):
        return "table indexée par niveau"
    if op == "elem" and len(a) == 2 and _de_niveau(a[1]) and _liste_const(a[0]):
        return "liste de constantes indexée par niveau"
    if op in ("contient", "indice") and len(a) == 2 and _de_niveau(a[1]) and _liste_const(a[0]):
        return f"{op} de niveau dans une liste de constantes"
    if op in ("si", "si_alors") and a and (_de_niveau(a[0]) or a[0] == ["non", ["niveau"]]):
        return f"{op} conditionné par niveau nu"
    return None


def _parcours(t, out, ou):
    if isinstance(t, dict):
        for v in t.values():
            _parcours(v, out, ou)
    elif isinstance(t, list):
        if t and isinstance(t[0], str) and (m := _motif(t)):
            out.append((ou, m))
        for u in t:
            _parcours(u, out, ou)


def echappatoires_niveau(programme):
    """Liste (règle, motif) des données propres à un niveau écrites dans les lois (vide = aucune)."""
    out = []
    for i, r in enumerate(programme.get("regles", [])):
        nom = r.get("nom") if isinstance(r, dict) else None
        _parcours(r, out, nom or f"regles[{i}]")
    for i, e in enumerate(programme.get("au_debut", [])):
        _parcours(e, out, f"au_debut[{i}]")
    for nom, d in (programme.get("mots") or {}).items():
        _parcours(d.get("corps") if isinstance(d, dict) else None, out, f"mot {nom}")
    return out
