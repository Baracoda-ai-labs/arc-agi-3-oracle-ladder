# SPDX-License-Identifier: MIT-0
"""[C] CW-357 / 358 / 360 : IMPASSE « RÈGLE » de la fusion. Pendant du menu des buts d'E (`E_franzen/menu_buts.py`).
1. `MENU` : mécanismes que l'induction de C sait établir, décrits de façon OPÉRATIONNELLE (condition, effet attendu, coup qui
   départage, contre-indication ; colonnes de `docs/CLASSES_REGLES.md`), jamais par le nom interne d'un champ de `Theorie`.
   Paramètres = identifiants neutres de la scène d'E (o1, o2…), facultatifs.
2. `verifier(prop, th, sources, tr)` : le moteur juge une proposition de Qwen. On induit la loi proposée (drapeau de la loi
   allumé, rien d'autre), on la greffe sur la théorie courante, et on rejoue chaque transition recalée :
   `confirme` = des transitions fausses deviennent justes et aucune juste ne devient fausse ; `regresse` = au moins une juste
   devient fausse (rejet) ; `aucune_modification` = la loi n'est pas trouvée ou ne change rien (PAS une réfutation : les
   données peuvent manquer → l'`experience` du menu dit quel coup jouer) ; `illisible` = hors menu / identifiant inconnu.
   Un paramètre o_k donné doit désigner la classe d'un objet que la loi trouvée concerne, sinon `aucune_modification`.
3. `dossier(...)` : la question (scène neutre, transitions encore fausses, menu, contrat de réponse).
Contrôle : `python experiments/T3.0/menu_mecanismes.py` (qui importe ce module) sur les dossiers parents de la 2ᵉ sonde (loi retirée connue) : la
bonne loi doit sortir `confirme`, les autres jamais `confirme` (→ menu_mecanismes.json)."""
import dataclasses
import os

# clé neutre → description opérationnelle, champs de la théorie greffés, drapeau qui autorise l'induction de la loi
MENU = {
    "retour_depart": {"params": ["mobile"], "champs": ["retour"], "drapeau": "CHRYS_RETOUR",
                      "condition": "une action précise (souvent SPACE) est jouée",
                      "effet": "le mobile revient d'un coup à la case où il a commencé le niveau",
                      "experience": "s'éloigner de 2 cases puis jouer l'action : le mobile saute à sa case de départ",
                      "contre": "l'action a déjà été jouée loin du départ sans que le mobile y revienne"},
    "copie_rejoue_trajet": {"params": ["mobile", "copie"], "champs": ["fantome"], "drapeau": "CHRYS_FANTOME",
                            "condition": "après un retour au départ",
                            "effet": "un second objet refait, coup après coup, le trajet que le mobile avait suivi",
                            "experience": "faire un trajet, revenir au départ, jouer une flèche : la copie avance sur l'ancien trajet",
                            "contre": "après un retour, aucun objet ne refait l'ancien trajet"},
    "porte_tenue": {"params": ["dalle", "porte"], "champs": ["tenue", "tenue_cases", "portes_cases"], "drapeau": "CHRYS_TENUE",
                    "condition": "un objet est posé sur une dalle",
                    "effet": "une porte éloignée s'ouvre TANT QUE la dalle est occupée, se referme dès qu'elle est libérée",
                    "experience": "monter sur la dalle puis en descendre : la porte s'ouvre puis se referme",
                    "contre": "la dalle a été occupée et la porte est restée fermée"},
    "clic_bascule_voisins": {"params": ["case"], "champs": ["motif_formes"], "drapeau": "CHRYS_MOTIF_FORME",
                             "condition": "un clic sur une case du plateau",
                             "effet": "la case cliquée et des voisines désignées changent d'aspect (bascule), toujours le même motif",
                             "experience": "cliquer deux fois la même case : tout revient comme avant",
                             "contre": "un clic n'a changé que la case cliquée, ou des voisines différentes à chaque fois"},
    "boutons_configuration": {"params": ["bouton", "objet_commande"], "champs": ["clic_configs"], "drapeau": "CHRYS_CLIC_CONFIG",
                              "condition": "un clic sur un bouton",
                              "effet": "des objets éloignés prennent une configuration fixe propre à ce bouton",
                              "experience": "cliquer le même bouton deux fois : la seconde fois rien ne change",
                              "contre": "le même bouton a donné deux configurations différentes"},
    "selection_au_clic": {"params": ["piece"], "champs": ["selection_clic"], "drapeau": "CHRYS_SELECTION_CLIC",
                          "condition": "un clic sur une pièce parmi plusieurs semblables",
                          "effet": "les flèches déplacent ensuite la pièce cliquée, et elle seule",
                          "experience": "cliquer une autre pièce puis jouer une flèche : c'est elle qui bouge",
                          "contre": "après un clic sur une autre pièce, la même pièce qu'avant bouge encore"},
    "selection_cyclique": {"params": ["piece"], "champs": ["selection", "ordre_sel", "saut_sel", "peint_sel", "desel"],
                           "drapeau": "CHRYS_SELECTION",
                           "condition": "une action (souvent SPACE) sans déplacement",
                           "effet": "la commande passe à la pièce suivante, dans un ordre fixe ; un marqueur la montre",
                           "experience": "jouer l'action puis une flèche : une autre pièce bouge",
                           "contre": "après l'action, la même pièce bouge"},
    "pousser": {"params": ["poussable"], "champs": ["poussables"], "drapeau": None,
                "condition": "le mobile avance vers un objet adjacent",
                "effet": "l'objet avance du même pas devant lui",
                "experience": "pousser contre un mur : ni le mobile ni l'objet ne bougent",
                "contre": "le mobile est entré dans l'objet ou s'est arrêté sans le déplacer, rien derrière"},
    "collecte": {"params": ["objet"], "champs": ["consomme"], "drapeau": None,
                 "condition": "le mobile arrive sur un objet",
                 "effet": "l'objet disparaît et ne revient pas quand le mobile repart",
                 "experience": "entrer sur l'objet puis repartir : la case reste vide",
                 "contre": "l'objet réapparaît quand le mobile repart (il était seulement caché)"},
    "teleportation": {"params": ["entree", "sortie"], "champs": ["teleports", "teleports_cases"], "drapeau": None,
                      "condition": "le mobile entre sur une case marquée",
                      "effet": "il ressort ailleurs, toujours au même endroit",
                      "experience": "entrer deux fois par la même case : même point de sortie",
                      "contre": "le mobile est entré sur la case et est resté dessus"},
    "transformation_contact": {"params": ["objet"], "champs": ["transforme"], "drapeau": None,
                               "condition": "le mobile arrive sur un objet",
                               "effet": "l'objet change de couleur ou de forme, au même endroit",
                               "experience": "repartir : même forme, même place, autre couleur",
                               "contre": "l'objet a disparu sans rien laisser (collecte)"},
    "mouvement_autonome": {"params": ["objet"], "champs": ["autonomes"], "drapeau": None,
                           "condition": "à chaque coup, quel qu'il soit",
                           "effet": "un objet non commandé bouge selon une règle fixe",
                           "experience": "jouer un coup sans effet (contre un mur) : l'objet bouge quand même",
                           "contre": "un coup sans effet n'a rien fait bouger"},
    "objets_lies": {"params": ["mobile", "lie"], "champs": ["lie"], "drapeau": None,
                    "condition": "le mobile se déplace",
                    "effet": "un autre objet, même éloigné, fait exactement le même pas",
                    "experience": "bloquer le mobile contre un mur : l'objet lié ne bouge pas non plus",
                    "contre": "le mobile a bougé et l'autre objet est resté"},
    "coup_sans_effet": {"params": ["mobile"], "champs": ["sans_effet"], "drapeau": "CHRYS_SANS_EFFET",
                        "condition": "une flèche dans une situation précise (case d'arrivée, objets voisins)",
                        "effet": "rien ne bouge, sans obstacle visible, chaque fois que la même situation revient",
                        "experience": "rejouer la même flèche depuis une autre case : le mobile bouge",
                        "contre": "la même flèche, dans la même situation, a déplacé le mobile"},
    "jauge_de_coups": {"params": ["barre"], "champs": ["jauge"], "drapeau": "CHRYS_JAUGE",
                       "condition": "chaque coup joué",
                       "effet": "une barre raccourcit d'un cran ; vide, la partie est perdue",
                       "experience": "compter les crans perdus sur 3 coups : un par coup (ou un tous les k coups)",
                       "contre": "la barre est restée fixe pendant plusieurs coups"},
}


def _classes(v):
    """Classes d'objets citées par la valeur d'un champ de théorie (entiers < 1024 trouvés dans la structure)."""
    out = set()
    pile = [v]
    while pile:
        x = pile.pop()
        if isinstance(x, bool):
            continue
        if isinstance(x, int) and 0 <= x < 1024:
            out.add(x)
        elif isinstance(x, dict):
            pile += list(x.keys()) + list(x.values())
        elif isinstance(x, (list, tuple, set, frozenset)):
            pile += list(x)
    return out


def justes(th, tr):
    from chrysalide.arc3.logique.theorie import egal
    return {t for t in range(len(tr.actions))
            if egal(th.rendu(th.pas(tr.etats[t], tr.actions[t], tr.taille)[0], tr.taille, tr.fond), tr.cases[t + 1],
                    tr.exclues)}


_CACHE = {}


def _loi(cle, sources, limite_s):
    """Induction avec le seul drapeau de la loi allumé en plus de l'environnement courant (cache par loi et par sources)."""
    from chrysalide.arc3.logique.induction import induire
    k = (cle, id(sources))
    if k not in _CACHE:
        d = MENU[cle]["drapeau"]
        avant = os.environ.get(d) if d else None
        if d:
            os.environ[d] = "1"
        try:
            _CACHE[k] = induire(sources, limite_s=limite_s)[0]
        finally:
            if d:
                os.environ.pop(d, None) if avant is None else os.environ.__setitem__(d, avant)
    return _CACHE[k]


def verifier(prop, th, sources, tr, ids=None, limite_s=90):
    """prop = {"mecanisme": clé du MENU, "params": {nom: "o3", …}} → {"statut", "gagnees", "perdues", "experience"}."""
    cle = prop.get("mecanisme")
    if cle not in MENU:
        return {"statut": "illisible", "raison": "mécanisme hors menu"}
    m = MENU[cle]
    citees = set()
    for v in (prop.get("params") or {}).values():
        for o in (v if isinstance(v, list) else [v]):
            if ids is None or o not in ids:
                return {"statut": "illisible", "raison": f"identifiant inconnu {o}"}
            citees.add(ids[o]["_classe"])
    full = _loi(cle, sources, limite_s)
    greffe = {c: getattr(full, c) for c in m["champs"]}
    if not any(greffe.values()) or all(greffe[c] == getattr(th, c) for c in m["champs"]):
        return {"statut": "aucune_modification", "raison": "loi non trouvée dans ces données", "experience": m["experience"]}
    if citees and not citees & _classes(greffe):
        return {"statut": "aucune_modification", "raison": "la loi trouvée ne concerne pas les objets cités",
                "experience": m["experience"]}
    cand = dataclasses.replace(th, **greffe)
    cand.hors_jeu = th.hors_jeu
    j0, j1 = justes(th, tr), justes(cand, tr)
    gagnees, perdues = sorted(j1 - j0), sorted(j0 - j1)
    statut = "regresse" if perdues else "confirme" if gagnees else "aucune_modification"
    return {"statut": statut, "gagnees": len(gagnees), "perdues": len(perdues), "exemples_gagnes": gagnees[:5],
            "experience": m["experience"], "theorie": cand if statut == "confirme" else None}


def enumerer(th, sources, tr, limite_s=90):
    """Impasse « règle » par défaut (CCM-026-H) : les 15 mécanismes du menu vérifiés un à un, sans Qwen ni objet cité.
    → liste des `confirme` (meilleur gain d'abord, puis le moins de transitions perdues), chacune avec sa théorie
    greffée ; vide = aucun mécanisme confirmé, et c'est là seulement qu'on pose la question à Qwen."""
    out = []
    for cle in MENU:
        r = verifier({"mecanisme": cle}, th, sources, tr, limite_s=limite_s)
        if r["statut"] == "confirme":
            out.append({"mecanisme": cle, **r})
    return sorted(out, key=lambda r: (-r["gagnees"], r["perdues"]))


def dossier(th, tr, scene):
    """Question « quelle règle manque ? » : scène neutre (E), transitions encore fausses, menu sans noms internes."""
    from chrysalide.arc3.logique.export_langage import NOMS
    fausses = sorted(set(range(len(tr.actions))) - justes(th, tr))

    def changes(e0, e1):  # objets disparus / apparus entre deux états (couleur, position, taille), sans nom de rôle
        d = lambda o: {"couleur": int(o[0]) % 16, "x": o[2], "y": o[3], "cases": len(o[1])}
        return {"disparus": [d(o) for o in sorted(set(e0) - set(e1)) if o[0] < 1024][:6],
                "apparus": [d(o) for o in sorted(set(e1) - set(e0)) if o[0] < 1024][:6]}

    def symptome(t):
        a = tr.actions[t]
        return {"t": t, "action": NOMS.get(a, str(a)), "observe": changes(tr.etats[t], tr.etats[t + 1]),
                "predit": changes(tr.etats[t], th.pas(tr.etats[t], a, tr.taille)[0])}
    return {"contrat": ("Choisis UN mécanisme du menu (clé) et, si tu peux, les objets concernés (o1…), ou réponds "
                        "Abstention(raison). Indique le coup qui départagerait ta proposition."),
            "scene": [{k: v for k, v in o.items() if not k.startswith("_")} for o in scene],
            "transitions_fausses": [symptome(t) for t in fausses[:8]],
            "n_fausses": len(fausses), "n_transitions": len(tr.actions),
            "menu": {k: {c: v[c] for c in ("params", "condition", "effet", "experience", "contre")} for k, v in MENU.items()}}


# ---------------------------------------------------------------- expériences (CW-365.1, avec G)
# Chaque fiche « coup qui départage » du menu devient un objet exécutable. Seules les hypothèses ABSENTES de la théorie
# courante sont proposées ; le coût compte le trajet (pas du piloté jusqu'à l'objet) plus les actions ; G choisit et joue.
FLECHES = {(0, -1): 1, (0, 1): 2, (-1, 0): 3, (1, 0): 4}


def _boite(o):
    from chrysalide.arc3.logique.theorie import cells
    cs = cells(o)
    return min(x for x, _ in cs), min(y for _, y in cs), max(x for x, _ in cs), max(y for _, y in cs)


def _centre(o):
    b = _boite(o)
    return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2


def experiences(th, etat, taille, max_n=6):
    """→ liste d'Experience (dict) triée par coût : hypothese (clé du MENU), objets (indices dans `etat`), preconditions,
    preparation (trajet du piloté, en pas), actions, predictions (si vrai / si faux), cout_total, contexte_validite."""
    pas = {c: v for (c, _a), v in th.moves.items() if v != (0, 0)}
    if not pas:
        return []
    c = next(iter(sorted(pas)))
    pilotes = [i for i, o in enumerate(etat) if o[0] == c]
    if not pilotes:
        return []
    ip = pilotes[0]
    p = etat[ip]
    step = max(abs(v[0]) + abs(v[1]) for (cc, _a), v in th.moves.items() if cc == c) or 1
    connu = lambda cle: any(getattr(th, ch, None) for ch in MENU[cle]["champs"])
    from chrysalide.arc3.logique.theorie import _enclos
    # candidats : ni le piloté, ni ce qu'il enclôt (son trou, son marqueur), ni le sol (zones > 4 × le piloté), ni virtuels
    autres = [(i, o) for i, o in enumerate(etat) if i != ip and o[0] < 1024 and len(o[1]) <= 4 * len(p[1])
              and not _enclos(p, o)]
    contexte = tuple(sorted((o[0], o[2], o[3]) for o in etat if o[0] in pas))

    def trajet(o):  # pas du piloté jusqu'au contact de o (distance de boîtes, en pas de la flèche)
        bp, bo = _boite(p), _boite(o)
        dx = max(0, bo[0] - bp[2] - 1, bp[0] - bo[2] - 1)
        dy = max(0, bo[1] - bp[3] - 1, bp[1] - bo[3] - 1)
        return -(-(dx + dy) // step)

    def vers(o):  # flèche qui rapproche le piloté de o
        (px, py), (ox, oy) = _centre(p), _centre(o)
        d = (1 if ox > px else -1, 0) if abs(ox - px) >= abs(oy - py) else (0, 1 if oy > py else -1)
        return FLECHES[d]

    out = []

    def ajoute(cle, objets, prep, actions, vrai, faux, pre=()):
        out.append({"hypothese": cle, "objets": objets, "preconditions": list(pre), "preparation": prep,
                    "actions": actions, "predictions": {"si_vrai": vrai, "si_faux": faux},
                    "cout_total": prep + len(actions), "contexte_validite": contexte,
                    "fiche": {k: MENU[cle][k] for k in ("condition", "effet", "experience", "contre")}})
    if not connu("selection_au_clic"):  # objet de même forme que le piloté : le cliquer, puis une flèche
        for i, o in autres:
            if o[1] == p[1] or _famille_coul(o[0]) == _famille_coul(c) and len(o[1]) == len(p[1]):
                x, y = _centre(o)
                ajoute("selection_au_clic", [i], 0, [("clic", x, y), vers(o)],
                       f"o{i} bouge d'un pas, le piloté o{ip} reste", f"le piloté o{ip} bouge, o{i} reste")
    if not connu("pousser"):
        for i, o in autres:
            if len(o[1]) >= 2 and o[0] not in th.solides:
                ajoute("pousser", [i], trajet(o), [vers(o)], f"o{i} avance dans le sens de la flèche",
                       f"o{ip} entre dans o{i} ou s'arrête, o{i} immobile", ["une case libre derrière l'objet"])
    if not connu("porte_tenue"):
        for i, o in autres:
            if len(o[1]) <= len(p[1]) and o[0] not in th.solides:
                ajoute("porte_tenue", [i], trajet(o), [vers(o), vers(o), FLECHES[_oppose(vers(o))]],
                       "un objet éloigné disparaît tant que la dalle est occupée, revient ensuite",
                       "rien d'autre ne change que le piloté")
    if not (connu("clic_bascule_voisins") or connu("boutons_configuration")):
        for i, o in autres:
            x, y = _centre(o)
            ajoute("boutons_configuration", [i], 0, [("clic", x, y), ("clic", x, y)],
                   "le 1er clic change des objets (voisins ou éloignés), le 2e les rétablit ou ne fait rien",
                   "aucun changement")
    if not connu("mouvement_autonome"):
        ajoute("mouvement_autonome", [], 0, [FLECHES[(0, -1)]],
               "un objet non piloté bouge même si le piloté est bloqué", "rien ne bouge hors du piloté")
    out.sort(key=lambda e: (e["cout_total"], e["hypothese"]))
    vus, choisies = set(), []
    for e in out:  # diversité : au plus une expérience par hypothèse, puis compléter
        if e["hypothese"] not in vus:
            choisies.append(e)
            vus.add(e["hypothese"])
    choisies += [e for e in out if e not in choisies]
    return choisies[:max_n]


def _famille_coul(k):
    return (k - 512) % 16 if 512 <= k < 1024 else k % 16 if k >= 16 else k


def _oppose(a):
    d = {v: k for k, v in FLECHES.items()}[a]
    return (-d[0], -d[1])
