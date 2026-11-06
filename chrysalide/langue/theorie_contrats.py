# SPDX-License-Identifier: MIT-0
"""Correspondance théorie de C (`Theorie`) ⇄ contrats de la langue unique (`ontologie_formelle.MECANISMES` de B) — CW-388.
Table écrite à la main, une ligne par champ : contrat de B, noms des paramètres, forme du champ. Chaque élément d'un champ devient
UNE instance de contrat (`{"contrat", "champ", "params"}`) ; la relecture reconstruit le champ à l'identique. Un champ actif sans
ligne est REFUSÉ et listé (`non_exprimes`), jamais traduit approximativement. Les champs qui ne sont pas des mécanismes (but,
défaite, perception) vont dans les sections du protocole ou de la perception de l'ontologie. Rien n'est exécuté ni appris."""
import dataclasses

from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.langue.ontologie_formelle import MECANISMES

# champ : (section, contrat ou rubrique, forme, noms des paramètres de la clé, noms des paramètres de la valeur)
# forme : "dict" (une instance par clé), "ensemble" (une par élément), "suite" (une par élément, ordre gardé), "valeur" (une seule)
TABLE = {
    "moves": ("mecanisme", "deplacement", "dict", ("classe", "action"), ("dx", "dy")),
    "moves_supposes": ("hypothese", "deplacement", "dict", ("classe", "action"), ("hypothese",)),
    "solides": ("mecanisme", "blocage", "ensemble", ("obstacle",), ()),
    "murs_supposes": ("hypothese", "blocage", "ensemble", ("obstacle",), ()),
    "fond_solide": ("mecanisme", "blocage", "valeur", (), ("fond_bloque",)),
    "portes_cases": ("mecanisme", "blocage", "suite", ("obstacle", "cases"), ()),
    "poussables": ("mecanisme", "poussee", "ensemble", ("classe",), ()),
    "glisse": ("mecanisme", "glissement", "decoupe", (), ()),  # découpé par DECOUPES (CCM-300-C)
    "consomme": ("mecanisme", "ramassage", "ensemble", ("recouvre", "retire"), ()),
    "lie": ("mecanisme", "ramassage", "ensemble", ("retire", "declencheur_epuise"), ()),
    "transforme": ("mecanisme", "transformation", "ensemble", ("atterrissage", "classe", "devient"), ()),
    "bascule": ("mecanisme", "transformation", "dict", ("de",), ("vers",)),
    "motif": ("mecanisme", "transformation", "ensemble", ("dx", "dy"), ()),
    "motif_formes": ("mecanisme", "transformation", "suite", ("forme", "voisinage"), ()),
    "formes_bascule": ("mecanisme", "transformation", "ensemble", ("forme",), ()),
    "zone": ("mecanisme", "transformation", "valeur", (), ("zone",)),
    "exclusif": ("mecanisme", "selection_clic", "valeur", (), ("exclusif",)),
    "desel": ("mecanisme", "selection_clic", "dict", ("selectionne",), ("repos",)),
    "selection_clic": ("mecanisme", "selection_clic", "valeur", (), ("classe", "x", "y")),
    "marqueur_sel": ("mecanisme", "selection_clic", "valeur", (), ("marqueur",)),
    "clic_configs": ("mecanisme", "bouton", "suite", ("configuration",), ()),
    "tenue": ("mecanisme", "bouton", "suite", ("porte", "dalle"), ()),
    "tenue_cases": ("mecanisme", "bouton", "suite", ("porte", "part", "arrive", "dalle"), ()),
    "autonomes": ("mecanisme", "autonome", "dict", ("classe",), ("poursuit",)),
    "teleports": ("mecanisme", "teleportation", "dict", ("declencheur",), ("decalage",)),
    "teleports_cases": ("mecanisme", "teleportation", "dict", ("case",), ("decalage",)),
    "retour": ("mecanisme", "memoire_fantome", "suite", ("pilote", "declencheur", "x", "y"), ()),
    "fantome": ("mecanisme", "memoire_fantome", "valeur", (), ("pilote", "declencheur", "fantome", "x0", "y0")),
    "peint_contact": ("mecanisme", "transformation", "ensemble", ("modificateur", "forme"), ()),  # attribut = couleur
    "porteur": ("mecanisme", "selection_marqueur", "valeur", (), ("marqueur", "action")),
    "hotes": ("mecanisme", "selection_marqueur", "ensemble", ("hote", "forme"), ()),
    "saut_sel": ("mecanisme", "selection_marqueur", "suite", ("depart", "arrivee", "decalage"), ()),
    "jauge": ("economie", "jauge", "valeur", (), ("reste", "rythme")),
    "but": ("protocole", "but", "valeur", (), ("but",)),
    "mort": ("protocole", "defaite", "valeur", (), ("defaite",)),
    "hors_jeu": ("perception", "hud", "ensemble", ("ligne", "colonne"), ()),
    "formes": ("perception", "formes", "dict", ("classe",), ("cases",)),
    "obligations": ("protocole", "obligations_but", "dict", ("but",), ("obligation",)),
    "buts_compatibles": ("protocole", "buts_candidats", "suite", ("but",), ()),
    "buts_motifs": ("protocole", "buts_candidats", "suite", ("but",), ()),
}
# glisse = (distance max, traversées, poussées, distance par famille, prolongeantes) : chaque morceau → son contrat
DECOUPES = {"glisse": (("glissement", (0, 1, 2, 3), ("jusqu_a", "traverse", "mobiles", "jusqu_a_par_classe")),
                       ("prolongation", (4,), ("surface",)))}
# Contrats PROPOSÉS par H, absents de l'ontologie de B : comptés à part, jamais présentés comme des contrats de B.
PROPOSES = {}  # `selection_marqueur` adopté par B (CCM-293-B, rôle `selectionnable`) : il est dans MECANISMES
INTERNES = {"_dalles", "_cache"}  # caches de calcul, pas de la connaissance


def _defauts():
    return {f.name: (f.default if f.default is not dataclasses.MISSING else f.default_factory())
            for f in dataclasses.fields(Theorie)}


def actifs(th):
    d = _defauts()
    return {k for k in d if k not in INTERNES and getattr(th, k) != d[k]}


def vers_contrats(th, proposes=True):
    """→ {"instances": [{"section", "contrat", "champ", "params"}], "non_exprimes": [champs refusés],
    "proposes": [champs exprimés seulement par un contrat de PROPOSES]}. `proposes=False` : contrats de B seuls."""
    for c in TABLE.values():
        if c[0] == "mecanisme":
            assert c[1] in MECANISMES or c[1] in PROPOSES, f"contrat {c[1]} inconnu"
    inst, refus, prop = [], [], []
    for champ in sorted(actifs(th)):
        if champ not in TABLE or (TABLE[champ][1] in PROPOSES and not proposes):
            refus.append(champ)
            continue
        section, contrat, forme, ncle, nval = TABLE[champ]
        if contrat in PROPOSES:
            prop.append(champ)
        v = getattr(th, champ)
        if forme == "decoupe":
            for c, idx, noms in DECOUPES[champ]:
                morceau = tuple(v[i] for i in idx if i < len(v))
                if c != contrat and not any(morceau):
                    continue  # morceau vide (ex. pas de prolongeante) : pas d'instance
                inst.append({"section": section, "contrat": c, "champ": champ, "forme": forme,
                             "params": {"_brut": {"indices": idx[:len(morceau)], "valeur": morceau},
                                        **dict(zip(noms, morceau))}})
            continue
        if forme == "dict":
            elems = [{"cle": k, "valeur": x} for k, x in v.items()]
        elif forme == "ensemble":
            elems = [{"element": e} for e in sorted(v, key=repr)]
        elif forme == "suite":
            elems = [{"element": e} for e in v]
        else:
            elems = [{"valeur": v}]
        for e in elems:
            inst.append({"section": section, "contrat": contrat, "champ": champ, "forme": forme,
                         "params": _nommer(e, ncle, nval)})
    return {"instances": inst, "non_exprimes": refus, "proposes": prop}


def _nommer(e, ncle, nval):
    """Paramètres lisibles (noms de la table) ; la valeur brute reste dans `_brut` pour la relecture exacte."""
    p = {"_brut": e}
    for noms, cle in ((ncle, "cle"), (ncle, "element"), (nval, "valeur")):
        if cle in e and noms:
            x = e[cle]
            if len(noms) == 1:
                p[noms[0]] = x
            elif isinstance(x, tuple) and len(x) == len(noms):
                p.update(dict(zip(noms, x, strict=True)))
    return p


def depuis_contrats(trad, base=None):
    """Instances de contrats → Theorie (champs non cités : valeurs par défaut, ou celles de `base`)."""
    th = dataclasses.replace(base) if base is not None else Theorie()
    d = _defauts()
    champs, morceaux = {}, {}
    for i in trad["instances"]:
        e, f = i["params"]["_brut"], i["forme"]
        if f == "decoupe":
            morceaux.setdefault(i["champ"], {}).update(zip(e["indices"], e["valeur"]))
        elif f == "dict":
            champs.setdefault(i["champ"], {})[e["cle"]] = e["valeur"]
        elif f == "ensemble":
            champs.setdefault(i["champ"], set()).add(e["element"])
        elif f == "suite":
            champs.setdefault(i["champ"], []).append(e["element"])
        else:
            champs[i["champ"]] = e["valeur"]
    for k, m in morceaux.items():
        n = max(m) + 1
        champs[k] = tuple(m.get(i, ()) for i in range(n))
    for k, v in champs.items():
        defaut = d[k]
        if isinstance(defaut, frozenset):
            v = frozenset(v)
        elif isinstance(defaut, tuple) and isinstance(v, list):
            v = tuple(v)
        setattr(th, k, v)
    return th
