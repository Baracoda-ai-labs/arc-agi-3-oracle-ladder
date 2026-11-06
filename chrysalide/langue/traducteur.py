# SPDX-License-Identifier: MIT-0
"""Langue unique (docs/LANGUE_PYTHON.md, CW-348) : forme interne (JSON du langage) ⇄ sous-ensemble Python.
`vers_python(prog) -> str` ; `depuis_python(texte) -> prog` (lève `Refus` avec ligne, colonne, raison). Le texte n'est JAMAIS
exécuté : `ast.parse` puis liste blanche. Contexte fixé par la position : expression (terme), liste d'effets, données."""
import ast
import json
import keyword

from chrysalide.arc3.langage import EFFETS_NATIFS, TERMES_NATIFS

MOTS = set(TERMES_NATIFS) | set(EFFETS_NATIFS)
BOOL = {"et": ast.And, "ou": ast.Or}
BIN = {"+": ast.Add, "-": ast.Sub, "*": ast.Mult, "//": ast.FloorDiv, "%": ast.Mod}
CMP = {"=": ast.Eq, "!=": ast.NotEq, "<": ast.Lt, "<=": ast.LtE, ">": ast.Gt, ">=": ast.GtE}
SYMB = {**{k: k for k in BIN}, **{k: k for k in CMP}}
# appel de repli quand l'arité n'est pas 2 (mot non identifiant Python) ; réversible
ALIAS = {"+": "plus", "-": "moins", "*": "fois", "//": "div_entiere", "%": "modulo", "=": "egal", "!=": "different",
         "<": "inf", "<=": "inf_egal", ">": "sup", ">=": "sup_egal"}
DE_ALIAS = {v: k for k, v in ALIAS.items()}
GENERATEURS = {"existe", "tous", "filtrer", "premier_tel_que"}
# positions (0 = 1er argument) qui portent une LISTE D'EFFETS
POS_EFFETS = {"pour": {2}, "soit_creer": {4}, "si_alors": {1, 2}, "tant_que": {1}}
CLES_PROGRAMME_EFFETS = {"au_debut"}
CLES_REGLE = ("nom", "soit", "quand", "alors", "puis", "phase", "poids")


class Refus(ValueError):
    def __init__(self, noeud, raison):
        self.ligne, self.colonne = getattr(noeud, "lineno", 0), getattr(noeud, "col_offset", 0)
        super().__init__(f"ligne {self.ligne}, colonne {self.colonne} : {type(noeud).__name__} — {raison}")


# ------------------------------------------------------------------ forme interne → Python
def _ident(s):
    return s.isidentifier() and not keyword.iskeyword(s)


def _donnee(v):
    return json.dumps(v, ensure_ascii=False) if isinstance(v, str) else repr(v) if not isinstance(v, (list, dict)) else (
        "[" + ", ".join(_donnee(x) for x in v) + "]" if isinstance(v, list)
        else "{" + ", ".join(f"{_donnee(k)}: {_donnee(x)}" for k, x in v.items()) + "}")


def _p(t):
    """Terme entre parenthèses s'il n'est pas atomique."""
    s = _terme(t)
    atomique = not isinstance(t, list) or (t and isinstance(t[0], str) and t[0] not in BOOL and t[0] not in SYMB
                                           and t[0] not in ("non", "si", "contient"))
    return s if atomique else f"({s})"


def _effets(L):
    return "[" + ", ".join(_terme(e) for e in L) + "]"


def _terme(t):
    if isinstance(t, str):
        if t.startswith("$"):
            if not _ident(t[1:]):
                return f"var({json.dumps(t[1:], ensure_ascii=False)})"
            return t[1:]
        return json.dumps(t, ensure_ascii=False)
    if t is None or isinstance(t, (bool, int, float)):
        return repr(t)
    if isinstance(t, dict):
        return _donnee(t)
    if not t or not isinstance(t[0], str):  # liste brute hors position d'effets
        return f"donnees({_donnee(t)})"
    op, a = t[0], t[1:]
    if op in BOOL and len(a) >= 2:
        return f" {'and' if op == 'et' else 'or'} ".join(_p(x) for x in a)
    if op == "non" and len(a) == 1:
        return f"not {_p(a[0])}"
    if op in SYMB and len(a) == 2:
        sym = "==" if op == "=" else op
        return f"{_p(a[0])} {sym} {_p(a[1])}"
    if op in ALIAS:
        return f"{ALIAS[op]}({', '.join(_terme(x) for x in a)})"
    if op == "si" and len(a) == 3:
        return f"{_p(a[1])} if {_p(a[0])} else {_p(a[2])}"
    if op == "liste":
        return "[" + ", ".join(_terme(x) for x in a) + "]"
    if op == "contient" and len(a) == 2:
        return f"{_p(a[1])} in {_p(a[0])}"
    if op in GENERATEURS and len(a) == 3 and isinstance(a[0], str) and a[0].startswith("$") and _ident(a[0][1:]):
        v = a[0][1:]
        if op in ("existe", "tous"):
            return f"{op}({_p(a[2])} for {v} in {_p(a[1])})"
        return f"{op}({v} for {v} in {_p(a[1])} if {_p(a[2])})"
    if not _ident(op):
        return f"mot({json.dumps(op, ensure_ascii=False)}{''.join(', ' + _terme(x) for x in a)})"
    pos = POS_EFFETS.get(op, set())
    return f"{op}({', '.join(_effets(x) if i in pos and isinstance(x, list) else _terme(x) for i, x in enumerate(a))})"


def _regle(r):
    parts = [_donnee(r["nom"])] if "nom" in r else []
    if "soit" in r:
        parts.append("soit={" + ", ".join(f"{_donnee(k)}: {_terme(v)}" for k, v in r["soit"].items()) + "}")
    if "quand" in r:
        parts.append(f"quand={_terme(r['quand'])}")
    if "alors" in r:
        parts.append("alors=" + _effets(r["alors"]))
    for k in ("puis", "phase", "poids"):
        if k in r:
            parts.append(f"{k}={_donnee(r[k])}")
    autres = {k: v for k, v in r.items() if k not in CLES_REGLE}
    if autres:
        parts.append(f"autres={_donnee(autres)}")
    return "Regle(" + ",\n          ".join(parts) + ")"


def _mot(m):
    sorte = m.get("sorte", "terme")
    corps = _effets(m["corps"]) if sorte == "effet" and isinstance(m["corps"], list) and (
        not m["corps"] or isinstance(m["corps"][0], list)) else _terme(m["corps"])
    autres = {k: v for k, v in m.items() if k not in ("params", "corps", "sorte")}
    return (f"Mot(params={_donnee(m.get('params', []))}, corps={corps}"
            + (f", sorte={_donnee(m['sorte'])}" if "sorte" in m else "")
            + (f", autres={_donnee(autres)}" if autres else "") + ")")


def vers_python(prog):
    lignes = ['"""Programme dans la langue unique (docs/LANGUE_PYTHON.md) ; produit par chrysalide.langue."""',
              "from chrysalide_langue import *", "", "PROGRAMME = Programme("]
    for k, v in prog.items():
        if k == "regles":
            s = "[\n        " + ",\n        ".join(_regle(r) for r in v) + "]"
        elif k in CLES_PROGRAMME_EFFETS:
            s = _effets(v)
        elif k == "mots":
            s = "{" + ", ".join(f"{_donnee(n)}: {_mot(m)}" for n, m in v.items()) + "}"
        else:
            s = _donnee(v)
        lignes.append(f"    {k}={s}," if _ident(k) else f"    **{{{_donnee(k)}: {s}}},")
    lignes.append(")")
    return "\n".join(lignes) + "\n"


# ------------------------------------------------------------------ Python → forme interne (liste blanche)
class _Lecteur:
    def __init__(self):
        self.consts = {}

    def donnee(self, n):
        if isinstance(n, ast.Constant) and (n.value is None or isinstance(n.value, (bool, int, float, str))):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and isinstance(n.operand, ast.Constant) \
                and isinstance(n.operand.value, (int, float)) and not isinstance(n.operand.value, bool):
            return -n.operand.value
        if isinstance(n, ast.List):
            return [self.donnee(x) for x in n.elts]
        if isinstance(n, ast.Dict):
            if any(k is None for k in n.keys):
                raise Refus(n, "dépliage ** interdit dans une donnée")
            return {self.donnee(k): self.donnee(v) for k, v in zip(n.keys, n.values, strict=True)}
        if isinstance(n, ast.Name) and n.id in self.consts:
            return self.consts[n.id]
        raise Refus(n, "donnée attendue (constante, liste, dictionnaire)")

    def effets(self, n):
        if not isinstance(n, ast.List):
            raise Refus(n, "liste d'effets attendue : [effet, …]")
        return [self.terme(x) for x in n.elts]

    def terme(self, n):
        if isinstance(n, ast.Constant) or (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub)
                                           and isinstance(n.operand, ast.Constant)):
            return self.donnee(n)
        if isinstance(n, ast.Name):
            if n.id in self.consts:
                return self.consts[n.id]
            return "$" + n.id
        if isinstance(n, ast.Dict):
            return self.donnee(n)
        if isinstance(n, ast.List):
            return ["liste", *[self.terme(x) for x in n.elts]]
        if isinstance(n, ast.BoolOp):
            return ["et" if isinstance(n.op, ast.And) else "ou", *[self.terme(x) for x in n.values]]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return ["non", self.terme(n.operand)]
        if isinstance(n, ast.BinOp):
            op = next((k for k, c in BIN.items() if isinstance(n.op, c)), None)
            if op is None:
                raise Refus(n, f"opérateur {type(n.op).__name__} interdit (permis : + - * // %)")
            return [op, self.terme(n.left), self.terme(n.right)]
        if isinstance(n, ast.Compare):
            if len(n.ops) != 1:
                raise Refus(n, "comparaison chaînée interdite : écrire (a < b) and (b < c)")
            o, g, d = n.ops[0], self.terme(n.left), self.terme(n.comparators[0])
            if isinstance(o, ast.In):
                return ["contient", d, g]
            op = next((k for k, c in CMP.items() if isinstance(o, c)), None)
            if op is None:
                raise Refus(n, f"comparaison {type(o).__name__} interdite (permis : == != < <= > >= in)")
            return [op, g, d]
        if isinstance(n, ast.IfExp):
            return ["si", self.terme(n.test), self.terme(n.body), self.terme(n.orelse)]
        if isinstance(n, ast.Call):
            return self.appel(n)
        raise Refus(n, "construction hors liste blanche (docs/LANGUE_PYTHON.md § 3)")

    def appel(self, n):
        if not isinstance(n.func, ast.Name):
            raise Refus(n, "seuls les appels de mots par leur nom sont permis (pas d'attribut)")
        f = n.func.id
        if f == "var" and len(n.args) == 1:
            return "$" + self.donnee(n.args[0])
        if f == "donnees" and len(n.args) == 1:
            return self.donnee(n.args[0])
        if f == "mot" and n.args:
            return [self.donnee(n.args[0]), *[self.terme(x) for x in n.args[1:]]]
        if n.keywords and f != "objets":
            raise Refus(n, f"arguments nommés interdits pour « {f} »")
        if f in GENERATEURS and len(n.args) == 1 and isinstance(n.args[0], ast.GeneratorExp):
            g = n.args[0]
            if len(g.generators) != 1 or not isinstance(g.generators[0].target, ast.Name) or g.generators[0].is_async:
                raise Refus(g, "générateur à une seule boucle sur un nom")
            gen = g.generators[0]
            v, L = "$" + gen.target.id, self.terme(gen.iter)
            if f in ("existe", "tous"):
                if gen.ifs:
                    raise Refus(g, f"« {f}(c for v in L) » sans if")
                return [f, v, L, self.terme(g.elt)]
            if len(gen.ifs) != 1 or not (isinstance(g.elt, ast.Name) and g.elt.id == gen.target.id):
                raise Refus(g, f"« {f}(v for v in L if c) » attendu")
            return [f, v, L, self.terme(gen.ifs[0])]
        op = DE_ALIAS.get(f, f)
        if op not in MOTS and op not in self.mots:
            raise Refus(n, f"mot inconnu « {f} » (ni natif, ni défini dans mots=)")
        if f == "objets" and n.keywords:
            if n.args:
                raise Refus(n, "objets(...) : soit un filtre nommé, soit une constante Classe")
            return ["objets", {k.arg: self.donnee(k.value) for k in n.keywords}]
        pos = POS_EFFETS.get(op, set())
        return [op, *[self.effets(x) if i in pos else self.terme(x) for i, x in enumerate(n.args)]]

    def regle(self, n):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Regle"):
            raise Refus(n, "Regle(...) attendue dans regles=[...]")
        r = {}
        if len(n.args) > 1:
            raise Refus(n, "Regle : un seul argument positionnel (le nom)")
        if n.args:
            r["nom"] = self.donnee(n.args[0])
        for k in n.keywords:
            if k.arg == "soit":
                if not isinstance(k.value, ast.Dict):
                    raise Refus(k.value, "soit={\"v\": terme, …}")
                r["soit"] = {self.donnee(a): self.terme(b) for a, b in zip(k.value.keys, k.value.values, strict=True)}
            elif k.arg == "quand":
                r["quand"] = self.terme(k.value)
            elif k.arg == "alors":
                r["alors"] = self.effets(k.value)
            elif k.arg in ("puis", "phase", "poids"):
                r[k.arg] = self.donnee(k.value)
            elif k.arg == "autres":
                r.update(self.donnee(k.value))
            else:
                raise Refus(k.value, f"argument « {k.arg} » inconnu de Regle")
        return r

    def mot(self, n):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Mot"):
            raise Refus(n, "Mot(params=…, corps=…, sorte=…) attendu")
        kw = {k.arg: k.value for k in n.keywords}
        sorte = self.donnee(kw["sorte"]) if "sorte" in kw else "terme"
        m = {"params": self.donnee(kw["params"])}
        m["corps"] = self.effets(kw["corps"]) if sorte == "effet" and isinstance(kw["corps"], ast.List) else self.terme(kw["corps"])
        if "sorte" in kw:
            m["sorte"] = sorte
        if "autres" in kw:
            m.update(self.donnee(kw["autres"]))
        return m


def depuis_python(texte):
    arbre = ast.parse(texte)
    lec = _Lecteur()
    lec.mots = set()
    prog = None
    for i, st in enumerate(arbre.body):
        if i == 0 and isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        if isinstance(st, ast.ImportFrom) and st.module == "chrysalide_langue" and [a.name for a in st.names] == ["*"]:
            continue
        if not (isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name)):
            raise Refus(st, "seules les affectations « NOM = … » sont permises au niveau du fichier")
        nom, v = st.targets[0].id, st.value
        if nom == "PROGRAMME":
            prog = lec_programme(lec, v)
        elif isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "Classe":
            d = {k.arg: lec.donnee(k.value) for k in v.keywords}
            if "roles" in d:  # § 6 : rôles de l'ontologie seulement, statut obligatoire (liste fermée de B)
                from chrysalide.langue.roles import RoleRefuse, verifier_roles
                try:
                    verifier_roles(d["roles"])
                except RoleRefuse as ex:
                    raise Refus(v, f"rôle refusé : {ex}") from ex
            lec.consts[nom] = {k: x for k, x in d.items() if k != "roles"}
        else:
            lec.consts[nom] = lec.donnee(v)
    if prog is None:
        raise Refus(arbre, "PROGRAMME = Programme(...) absent")
    if prog.get("origine") == "induit" and '"tag"' in json.dumps(prog):
        raise Refus(arbre, "programme induit : identité par couleur et forme seulement, « tag » interdit (§ 6)")
    return prog


def lec_programme(lec, n):
    if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Programme") or n.args:
        raise Refus(n, "Programme(clé=valeur, …) attendu")
    kws = []
    for k in n.keywords:
        if k.arg is None:  # **{"clé non identifiant": valeur}
            if not isinstance(k.value, ast.Dict) or len(k.value.keys) != 1:
                raise Refus(k.value, "**{…} : une seule clé")
            kws.append((lec.donnee(k.value.keys[0]), k.value.values[0]))
        else:
            kws.append((k.arg, k.value))
    mots = next((v for c, v in kws if c == "mots"), None)
    if mots is not None:
        if not isinstance(mots, ast.Dict):
            raise Refus(mots, "mots={…} attendu")
        lec.mots = {lec.donnee(k) for k in mots.keys}
    prog = {}
    for c, v in kws:
        if c == "regles":
            if not isinstance(v, ast.List):
                raise Refus(v, "regles=[Regle(...), …]")
            prog[c] = [lec.regle(x) for x in v.elts]
        elif c in CLES_PROGRAMME_EFFETS:
            prog[c] = lec.effets(v)
        elif c == "mots":
            prog[c] = {lec.donnee(a): lec.mot(b) for a, b in zip(v.keys, v.values, strict=True)}
        else:
            prog[c] = lec.donnee(v)
    return prog


# ------------------------------------------------------------------ réponse d'un proposeur (§ 8)
def lire_reponse(texte, mots=()):
    """`REPONSE = Reponse(patch=Patch(ajoute=[Regle…], retire=["nom"]), hypotheses=[…], explique=[…], incertitudes=[…])` ou
    `REPONSE = Abstention(raison="…")` → {"abstention": raison} | {"patch": {"ajoute": [règles], "retire": [noms]}, …}.
    `mots` : mots définis du programme visé (un patch peut s'en servir). Lève `Refus` hors liste blanche."""
    arbre = ast.parse(texte)
    lec = _Lecteur()
    lec.mots = set(mots)
    rep = None
    for i, st in enumerate(arbre.body):
        if i == 0 and isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        if isinstance(st, ast.ImportFrom) and st.module == "chrysalide_langue" and [a.name for a in st.names] == ["*"]:
            continue
        if not (isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name)):
            raise Refus(st, "seules les affectations « NOM = … » sont permises au niveau du fichier")
        nom, v = st.targets[0].id, st.value
        if nom != "REPONSE":
            lec.consts[nom] = ({k.arg: lec.donnee(k.value) for k in v.keywords if k.arg != "roles"}
                               if isinstance(v, ast.Call) and getattr(v.func, "id", "") == "Classe" else lec.donnee(v))
            continue
        if not (isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id in ("Reponse", "Abstention")):
            raise Refus(v, "REPONSE = Reponse(...) ou Abstention(...)")
        kw = {k.arg: k.value for k in v.keywords}
        if v.func.id == "Abstention":
            rep = {"abstention": lec.donnee(kw["raison"]) if "raison" in kw else ""}
            continue
        p = kw.get("patch")
        if not (isinstance(p, ast.Call) and getattr(p.func, "id", "") == "Patch"):
            raise Refus(v, "Reponse(patch=Patch(ajoute=[…], retire=[…]), …)")
        pk = {k.arg: k.value for k in p.keywords}
        inconnus = set(pk) - {"ajoute", "retire"}
        if inconnus:
            raise Refus(p, f"Patch : arguments inconnus {sorted(inconnus)}")
        ajoute = pk.get("ajoute")
        if ajoute is not None and not isinstance(ajoute, ast.List):
            raise Refus(ajoute, "ajoute=[Regle(...), …]")
        rep = {"patch": {"ajoute": [lec.regle(x) for x in (ajoute.elts if ajoute is not None else [])],
                         "retire": lec.donnee(pk["retire"]) if "retire" in pk else []}}
        for c in ("hypotheses", "explique", "incertitudes"):
            if c in kw:
                rep[c] = lec.donnee(kw[c])
    if rep is None:
        raise Refus(arbre, "REPONSE = … absent")
    return rep


def appliquer_patch(prog, patch):
    """Copie du programme : règles nommées retirées, puis règles ajoutées EN FIN (mode « lois » : leur phase décide de l'ordre)."""
    q = json.loads(json.dumps(prog))
    retire = set(patch.get("retire", []))
    q["regles"] = [r for r in q.get("regles", []) if r.get("nom") not in retire] + list(patch.get("ajoute", []))
    return q
