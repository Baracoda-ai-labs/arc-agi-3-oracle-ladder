# SPDX-License-Identifier: MIT-0
"""C (CW-404, avec B ; relève après victoire, CW-401) : SÉPARER ce qui se garde d'un niveau au suivant (sémantique du
mécanisme : classes, actions, pas, conditions, invariants) de ce qui se RECALCULE sur la scène neuve (positions de départ,
coordonnées de cases, liaisons dalle–porte, but, paramètres de scène). L'erreur la plus coûteuse : transférer une valeur
codée en dur (arXiv 2610.11450). Chaque champ de `Theorie` est classé ; un champ AJOUTÉ à `Theorie` et absent de la table
fait échouer `tests/test_separation.py` (même garde que CHAMPS_CONNUS de l'export)."""
import dataclasses

from chrysalide.arc3.logique.theorie import Theorie

# garde : la loi telle quelle ; recalcule : paramètre de scène, recalculé sur l'état neuf quand c'est possible (sinon
# vidé) ; observe : à rétablir par observation au niveau suivant (vidé, hypothèse listée) ; meta : métadonnées
TABLE = {
    "moves": "garde", "solides": "garde", "murs_supposes": "garde", "moves_supposes": "garde", "poussables": "garde",
    "consomme": "garde", "lie": "garde", "autonomes": "garde", "motif": "garde", "bascule": "garde", "zone": "garde",
    "derives": "garde", "teleports": "garde", "saut": "garde", "transforme": "garde", "formes": "garde",
    "annule": "garde", "hotes": "garde", "motif_formes": "garde", "formes_bascule": "garde", "debordent": "garde",
    "porteur": "garde", "ordre_sel": "garde", "saut_sel": "garde", "peint_sel": "garde", "glisse": "garde",
    "peint_contact": "garde", "marqueur_sel": "garde", "fond_solide": "garde", "desel": "garde", "exclusif": "garde",
    "mort": "garde", "tenue": "garde",
    # paramètres de scène recalculables depuis l'état neuf
    "retour": "recalcule", "fantome": "recalcule", "selection_clic": "recalcule", "selection": "recalcule",
    "enroule": "recalcule", "jauge": "recalcule", "hors_jeu": "recalcule",
    # liaisons et coordonnées propres à la scène : à ré-observer
    "teleports_cases": "observe", "clic_configs": "observe", "portes_cases": "observe", "tenue_cases": "observe",
    "_dalles": "observe", "sans_effet": "observe", "but": "observe", "buts_compatibles": "observe",
    "buts_motifs": "observe", "obligations": "observe",
}
HYPOTHESES = {  # ce que le niveau suivant doit rétablir, par champ « observe » non vide
    "tenue_cases": "porte tenue : quelle dalle commande quelle porte (cases de dalle, cases de porte ouverte / fermée)",
    "portes_cases": "cases de porte qui bloquent",
    "clic_configs": "boutons : quelle case cliquée donne quelle configuration",
    "teleports_cases": "téléports par case : entrées et sorties",
    "sans_effet": "coups vus sans effet (positions de l'ancienne scène)",
    "but": "forme du but (la forme est une hypothèse de départ, ses paramètres sont à relire)",
}


def separer(th):
    """→ {"garde": {champ: valeur}, "recalcule": [champs], "observe": [champs non vides], "inconnus": [champs]}."""
    out = {"garde": {}, "recalcule": [], "observe": [], "inconnus": []}
    for f in dataclasses.fields(Theorie):
        v = getattr(th, f.name)
        cat = TABLE.get(f.name)
        if cat is None:
            out["inconnus"].append(f.name)
        elif cat == "garde":
            out["garde"][f.name] = v
        elif cat == "recalcule":
            out["recalcule"].append(f.name)
        elif cat == "observe" and v:
            out["observe"].append(f.name)
    return out


def _pilote(th, etat):
    """Le piloté sur la scène neuve : même classe si elle existe, sinon même COULEUR et même FORME (`th.formes`) : sur
    une première image, la perception ne connaît pas encore la classe de forme apprise (281 = couleur 9 + sa forme)."""
    cs = sorted({c for c, _a in th.moves})
    o = next((o for c in cs for o in etat if o[0] == c), None)
    if o is not None:
        return o
    for c in cs:
        f = th.formes.get(c)
        coul = c % 16 if c >= 16 else c
        cand = [q for q in etat if (q[0] % 16 if q[0] >= 16 else q[0]) == coul and len(q[1]) > 1]
        exact = [q for q in cand if f is not None and q[1] == f]
        if not exact and f is not None:  # même couleur, taille la plus proche à 25 % près (bord perçu à une case près)
            proches = sorted((abs(len(q[1]) - len(f)), q) for q in cand if abs(len(q[1]) - len(f)) <= 0.25 * len(f))
            exact = [proches[0][1]] if proches else []
        if exact:
            q = exact[0]
            return (c, q[1], q[2], q[3])
    return None


def _agrandir(forme, k):
    """Forme vue à l'échelle s devenue s / k : chaque case devient un carré k × k."""
    return frozenset((x * k + i, y * k + j) for x, y in forme for i in range(k) for j in range(k))


def _changer_echelle(neuve, k):
    """Les lois écrites en CASES suivent l'échelle (g50t : N1 à l'échelle 2, N2 à 1 ; k = 2) : pas des flèches, sauts,
    distance de glissade, formes connues. k entier ≥ 2 seulement (sinon on ne touche à rien et on le dit)."""
    neuve.moves = {ca: (v[0] * k, v[1] * k) for ca, v in neuve.moves.items()}
    neuve.saut = {ca: (v[0] * k, v[1] * k) for ca, v in neuve.saut.items()}
    if neuve.glisse:
        neuve.glisse = (neuve.glisse[0] * k, *neuve.glisse[1:])
    neuve.formes = {c: _agrandir(f, k) for c, f in neuve.formes.items()}


def pour_niveau_suivant(th, etat, ech_avant=None, ech_apres=None):
    """Théorie de départ du niveau suivant : les lois gardées ; les paramètres de scène RECALCULÉS sur `etat` (1ʳᵉ image
    du niveau neuf) quand c'est possible ; tout le reste vidé. L'ÉCHELLE est un paramètre de scène : si elle change
    (`ech_avant`, `ech_apres` = taille de case en pixels), les lois en cases sont converties.
    → (Theorie, {"recalcules": {...}, "a_retablir": [...], "inconnus": [...]})."""
    sep = separer(th)
    neuve = dataclasses.replace(Theorie(), **{k: v for k, v in sep["garde"].items()})
    rec = {}
    if ech_avant and ech_apres and ech_avant != ech_apres:
        if ech_avant % ech_apres == 0:
            _changer_echelle(neuve, ech_avant // ech_apres)
            rec["echelle"] = f"{ech_avant} → {ech_apres} : pas, sauts, glissade et formes × {ech_avant // ech_apres}"
        else:
            rec["echelle"] = f"{ech_avant} → {ech_apres} : rapport non entier, lois en cases NON converties"
    th_formes = th.formes
    th = dataclasses.replace(th, formes=neuve.formes) if neuve.formes is not th_formes else th
    p = _pilote(th, etat)
    if th.retour and p is not None:  # retour au départ : le départ est la position du piloté sur la scène neuve
        neuve.retour = tuple((c, a, p[2], p[3]) if c == p[0] else (c, a, x, y) for c, a, x, y in th.retour
                             if c == p[0])
        rec["retour"] = neuve.retour
    if th.fantome and p is not None:
        cj, b, cg, _x, _y = th.fantome
        neuve.fantome = (cj, b, cg, p[2], p[3])
        rec["fantome"] = neuve.fantome
    if th.selection_clic:
        c = th.selection_clic[0]
        o = next((o for o in etat if o[0] == c and len(o[1]) > 1), None)
        if o is not None:
            neuve.selection_clic = (c, o[2], o[3])
            rec["selection_clic"] = neuve.selection_clic
    if th.selection:  # sélection cachée : mêmes classes et même sélecteur, index de départ remis à 0
        sel, classes, _i0 = th.selection
        neuve.selection = (sel, classes, 0)
        rec["selection"] = neuve.selection
    if th.jauge:  # le rythme (coups par cran) est le mécanisme ; la réserve se relit sur la barre (F, reserve_niveau)
        neuve.jauge = th.jauge
        rec["jauge"] = "rythme gardé, réserve à relire sur la barre"
    a_retablir = [HYPOTHESES.get(k, k) for k in sep["observe"]]
    return neuve, {"recalcules": rec, "a_retablir": a_retablir, "inconnus": sep["inconnus"]}
