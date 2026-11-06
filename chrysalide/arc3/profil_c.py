# SPDX-License-Identifier: MIT-0
"""« Profil C » du langage (CCM-015-C, approuvé CW-111) : le sous-ensemble à gabarits fixes et paramètres en domaine fini que
l'induction ASP de C sait produire. Un fichier en profil C s'exécute TEL QUEL par l'interpréteur de référence (langage.py) :
le profil restreint, il n'ajoute rien. `hors_profil(regle)` rend la liste des raisons (vide = dans le profil)."""

CLASSE = {"tag", "couleur", "forme", "nom", "visible"}
OBJ = {"x", "y", "largeur", "hauteur"}
EFFETS = {"deplacer", "placer", "tourner", "poser_motif", "recolorer", "retirer", "poser", "poser_attr", "gagner", "perdre", "niveau_suivant", "depiler",
          "refleter", "montrer", "calque", "consommer", "recharger"}
EFFETS_CANEVAS = {"ecrire_case", "remplir", "deplacer_bloc", "poser_geometrie"}  # CW-141/142 : arguments constants


def _const(t):
    return not isinstance(t, list) and not (isinstance(t, str) and t.startswith("$"))


def _param(t):
    """["param", clé constante] : paramètre du niveau (étage 2), une constante par niveau : admis comme une constante."""
    return isinstance(t, list) and len(t) == 2 and t[0] == "param" and _const(t[1])


def _cst(t):
    return _const(t) or _param(t)


def _var(t):
    return isinstance(t, str) and t.startswith("$")


def _canevas(t, r):
    """Canevas désigné par une variable, ["canevas"] ou ["canevas", nom constant]."""
    if not (_var(t) or (isinstance(t, list) and t[:1] == ["canevas"] and len(t) <= 2 and all(_const(u) for u in t[1:]))):
        r.append(f"canevas calculé : {str(t)[:60]}")


def _classe(t, r):
    """["objets", {classe}] ou ["premier", ["objets", {classe}]]."""
    if isinstance(t, list) and t and t[0] == "premier" and len(t) == 2:
        t = t[1]
    if not (isinstance(t, list) and len(t) == 2 and t[0] == "objets" and isinstance(t[1], dict) and set(t[1]) <= CLASSE):
        r.append(f"liaison hors classe : {str(t)[:60]}")


def _valeur(t, r):
    """Valeur d'un atome : constante, variable, action, case_clic, etat(n), attr(o, n), x/y(o), ou ± constante."""
    if _cst(t) or _var(t):
        return
    op = t[0] if isinstance(t, list) and t else None
    if op in ("action", "case_clic", "pixel_clic") and len(t) == 1:
        return
    if op == "case_canevas" and len(t) == 4:  # ["case_canevas", canevas, x, y] : case d'un canevas, coordonnées atomiques
        _canevas(t[1], r)
        _valeur(t[2], r), _valeur(t[3], r)
        return
    if op == "etat" and _const(t[1]):
        return
    if op == "attr" and _var(t[1]) and _const(t[2]):
        return
    if op in OBJ and _var(t[1]):
        return
    if op == "liste":
        for u in t[1:]:
            _valeur(u, r)
        return
    if op in ("+", "-") and len(t) == 3 and (_const(t[1]) or _const(t[2])):
        _valeur(t[1], r), _valeur(t[2], r)
        return
    r.append(f"valeur hors profil : {str(t)[:60]}")


def _quand(t, r):
    if t is True or t is None:
        return
    op = t[0] if isinstance(t, list) and t else None
    if op == "et":
        for u in t[1:]:
            _quand(u, r)
    elif op == "non":
        _quand(t[1], r)
    elif op in ("=", "!="):
        _valeur(t[1], r), _valeur(t[2], r)
    elif op == "contient" and isinstance(t[1], list) and t[1][:1] == ["liste"] and all(_const(u) for u in t[1][1:]):
        _valeur(t[2], r)  # action ∈ {constantes} : disjonction finie
    elif op == "libre":
        if not (_const(t[2]) and _const(t[3]) and isinstance(t[4], dict) and set(t[4]) <= CLASSE):
            r.append(f"libre à décalage ou filtre non constant : {str(t)[:60]}")
    elif op in ("chevauche", "correspond"):
        for u in t[1:]:
            if not _var(u):
                _classe(u, r)
    elif op == "existe":
        _classe(t[2], r), _quand(t[3], r)
    elif op == "vide":
        _classe(t[1], r)
    elif op == "debut_niveau":
        pass
    elif op == "epuise":
        if not all(_cst(u) for u in t[1:]):
            r.append(f"epuise à seuil calculé : {str(t)[:60]}")
    elif op == "utilise":
        if not _var(t[1]):
            _classe(t[1], r)
    else:
        r.append(f"condition hors profil : {op}")


def _effet(e, r, dans_pour=False):
    op = e[0] if isinstance(e, list) and e else None
    if op == "pour":
        if dans_pour:
            r.append("pour imbriqué")
        _classe(e[2], r)
        for f in e[3]:
            _effet(f, r, True)
    elif op in EFFETS_CANEVAS:
        if len(e) < 2:
            r.append(f"{op} sans canevas")
            return
        _canevas(e[1], r)
        if not all(_cst(u) for u in e[2:]):
            r.append(f"{op} à argument calculé : {str(e)[:60]}")
    elif op in EFFETS:
        if op == "refleter":
            _classe(e[1], r)
            args = e[3:]
        else:
            args = e[2:] if len(e) > 1 and (_var(e[1]) or op in ("poser", "depiler")) else e[1:]
        if op == "poser_attr":
            args = e[2:]
        if op == "recharger":  # ["recharger", n, valeur, o] : n et valeur constants, o variable ou classe
            args = e[1:3]
            if not _var(e[3]):
                _classe(e[3], r)
        if not all(_cst(u) for u in args):
            r.append(f"{op} à argument calculé : {str(e)[:60]}")
    else:
        r.append(f"effet hors profil : {op}")


def hors_profil(regle):
    r = []
    for v in (regle.get("soit") or {}).values():
        _classe(v, r)
    _quand(regle.get("quand", True), r)
    for e in regle.get("alors", []):
        _effet(e, r)
    return r


def bilan(programme):
    """(règles dans le profil, total, raisons par règle hors profil)."""
    regles = programme.get("regles", [])
    hors = {g.get("nom", str(i)): h for i, g in enumerate(regles) if (h := hors_profil(g))}
    return len(regles) - len(hors), len(regles), hors
