# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — exportateur théorie induite → langage de A (`docs/LANGAGE.md`, profil C, CCM-015-C / CW-111) :
chaque théorie peut être exécutée par l'interpréteur de A (`chrysalide/arc3/langage.py`) et jugée contre le vrai moteur,
indépendamment du simulateur Python de C. Hypothèse de correspondance : une classe de C = une COULEUR de sprite
(vrai pour les jeux synthétiques à sprites d'une case ; les jeux publics demanderont des classes par nom/tag).
Mode « lois » de A avec phases (CCM-102-A) : phase 0 déplacements, 1 consommation et transformations, 2 liens, 3 but ;
chaque loi est jugée sur l'état laissé par les phases précédentes.
Exportés par D (CW-196) : poussée (un étage, tout ou rien, comme theorie.pas), autonomes (pas glouton), saut,
téléportation par classe, clics (avec ou sans zone ; sans sélection exclusive), fond solide, annulation (pile d'instantanés).
Reflets / miroirs : image seulement (un sprite par objet source).
Non exportés (renvoyés dans `non_exporte`) : téléportation par case, clics avec sélection exclusive."""

import os

NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 7: "UNDO"}


def _objets(c):
    return ["objets", {"couleur": c}]


def exporter(th, taille):
    """→ (programme JSON du langage, liste des éléments de la théorie non exportés)."""
    w, h = taille
    regles, non = [], []
    autonomes = bool(th.autonomes)
    undo = NOMS.get(th.annule) if th.annule is not None else None
    chg = [["poser", "change", True]] if undo else []  # annulation : ce coup a-t-il changé l'état ?
    pas_undo = ["!=", ["action"], undo] if undo else True
    if undo:  # pile de theorie / induction.precedent_pile : l'état d'avant chaque coup qui a CHANGÉ l'état
        regles.append({"nom": "annuler", "phase": 0, "quand": ["et", ["=", ["action"], undo], [">", ["etat", "prof"], 0]],
                       "alors": [["poser", "prof", ["-", ["etat", "prof"], 1]], ["restaurer", ["etat", "prof"]]]})
        regles.append({"nom": "instantané du coup", "phase": 0, "quand": pas_undo,
                       "alors": [["poser", "change", False], ["instantane", ["etat", "prof"]]]})
    if autonomes:  # « le joueur a bougé » (theorie.pas : bouge) ; remis à faux au début de chaque coup
        regles.append({"nom": "bouge remis", "quand": True, "phase": 0, "alors": [["poser", "bouge", False]]})
    bouge = [["poser", "bouge", True]] if autonomes else []
    selection = th.selection if th.selection and th.selection[0] in NOMS else None
    if selection:  # theorie._pas_selection (re86 N2, C) : sélection CACHÉE etat["sel"] ; le sélecteur ne fait que l'avancer
        s_act, s_classes, _i0 = selection
        regles.append({"nom": "sélecteur", "phase": 0, "quand": ["=", ["action"], NOMS[s_act]],
                       "alors": [["poser", "sel", ["%", ["+", ["etat", "sel"], 1], len(s_classes)]]]})
    if getattr(th, "sans_effet", ()):  # C (CW-354.2) : positions des mobiles et action vus sans effet → aucun pas
        def present(c, x, y):
            return ["existe", "$q", _objets(c), ["et", ["=", ["x", "$q"], x], ["=", ["y", "$q"], y]]]

        def ici(cle):  # CW-355 : mêmes positions des mobiles ET même contexte sur les cases d'arrivée (état caché ignoré)
            a, pos, ctx = cle
            return ["et", ["=", ["action"], NOMS.get(a, a)], *[present(c, x, y) for c, x, y in sorted(pos)],
                    *[present(c, x, y) for c, x, y, _f in sorted(ctx or (), key=str) if c < 1024]]
        regles.append({"nom": "coups sans effet", "phase": -0.95, "quand": True,
                       "alors": [["poser", "_sans_effet", ["ou", False, *[ici(k) for k in sorted(th.sans_effet, key=str)
                                                                         if k[0] in NOMS]]]]})
    for (c, a), (dx, dy) in sorted(th.moves.items()):
        if a not in NOMS or (selection and a == selection[0]):
            continue
        conds = [["libre", "$o", dx, dy, {"couleur": s}] for s in sorted(th.solides - {c})]
        # theorie._pas, libre_vers : une classe qui « déborde » peut sortir en partie de la grille (au moins une case reste)
        conds += _deborde("$o", dx, dy, w, h) if c in th.debordent else _dans("$o", dx, dy, w, h)
        if th.hors_jeu:
            conds.append(_hors_masque("$o", dx, dy, th.hors_jeu))
        if th.fond_solide:
            conds.append(_couvert("$o", dx, dy))
        conds += _portes_libres("$o", dx, dy, th, c)
        saut = []
        if (c, a) in th.saut:  # theorie.pas : pas normal bloqué (ou poussée bloquée) → saut à 2·V si libre
            sx, sy = th.saut[(c, a)]
            libre2 = ["et", *[["libre", "$o", sx, sy, {"couleur": s}] for s in sorted(th.solides - {c})], *_dans("$o", sx, sy, w, h),
                      *([_couvert("$o", sx, sy)] if th.fond_solide else []), *([_hors_masque("$o", sx, sy, th.hors_jeu)] if th.hors_jeu else [])]
            saut = [["si_alors", libre2, [["deplacer", "$o", sx, sy], *bouge, *chg], []]]
        pas = _pas_pousse(th, c, dx, dy, w, h, saut, _teleporte(th) + bouge + chg)  # saut : ni téléportation (theorie.pas)
        sel_c = getattr(th, "selection_clic", ()) and th.selection_clic[0] == c
        if sel_c:  # theorie._pas_selection_clic : seul le sélectionné bouge ; sa position suit
            conds = [["=", ["x", "$o"], ["etat", "_sel_x"]], ["=", ["y", "$o"], ["etat", "_sel_y"]], *conds]
            if getattr(th, "glisse", ()):  # il a poussé une pièce ce coup-ci (theorie._glisser) : il ne bouge pas
                conds = [["!=", ["etat", "_pousse"], 1], *conds]
            suivre = [["poser", "_sel_x", ["x", "$o"]], ["poser", "_sel_y", ["y", "$o"]]]
            pas = [*pas, *suivre]
            saut = [*saut, *suivre] if saut else saut
        quand = ["=", ["action"], NOMS[a]]
        if getattr(th, "sans_effet", ()):  # theorie.pas : coup vu sans effet d'ici (CW-354.2)
            quand = ["et", quand, ["!=", ["etat", "_sans_effet"], True]]
        if selection and c in selection[1]:  # seules les lois de la classe sélectionnée s'appliquent
            quand = ["et", quand, ["=", ["etat", "sel"], list(selection[1]).index(c)]]
        regles.append({"nom": f"move c{c} {NOMS[a]}", "quand": quand,
                       "alors": [["pour", "$o", _objets(c), [["si_alors", ["et", *conds], pas, saut]]]],
                       "phase": 0})
    mobiles = sorted({c for c, _ in th.moves})
    for c1, c2 in sorted(th.consomme):
        regles.append({"nom": f"consomme c{c1} c{c2}", "quand": pas_undo, "phase": 1,
                       "alors": [["pour", "$k", _objets(c2), [["si_alors",
                                  ["existe", "$j", _objets(c1), ["chevauche", "$j", "$k"]], [["retirer", "$k"], *chg], []]]]]})
    for m, c, c2 in sorted(th.transforme):  # approximation : « un mobile est sur M » (pas « vient d'y arriver »)
        sur_m = ["existe", "$m", _objets(m), ["ou", False, *[["existe", "$j", _objets(mb), ["chevauche", "$j", "$m"]]
                                                              for mb in mobiles]]]
        regles.append({"nom": f"transforme c{m} c{c} c{c2}", "quand": pas_undo, "phase": 1,
                       "alors": [["pour", "$o", _objets(c), [["si_alors", sur_m, [["recolorer", "$o", c, c2], *chg], []]]]]})
    for cd, ct in sorted(th.lie):
        regles.append({"nom": f"lie c{cd} c{ct}", "quand": ["et", pas_undo, ["vide", _objets(ct)]], "phase": 2,
                       "alors": [["pour", "$o", _objets(cd), [["retirer", "$o"], *chg]]]})
    for c, (axe, mini, maxi) in sorted(th.enroule.items()):  # theorie.enroule (tr87) : retour à l'autre bout
        coord = ["x", "$o"] if axe == 0 else ["y", "$o"]
        autre = ["y", "$o"] if axe == 0 else ["x", "$o"]
        def poser(v, autre=autre, axe=axe):
            return ["placer", "$o", v, autre] if axe == 0 else ["placer", "$o", autre, v]
        regles.append({"nom": f"enroulement c{c}", "phase": 0.6, "quand": True,
                       "alors": [["pour", "$o", _objets(c), [["si_alors", [">", coord, maxi], [poser(mini)], []],
                                                             ["si_alors", ["<", coord, mini], [poser(maxi)], []]]]]})
    couche = th.couches()  # C (CW-355, dc22 N3) : ordre de dessin de theorie.rendu (mobiles au-dessus), sinon un objet
    fant = {th.fantome[2]} if getattr(th, "fantome", None) else set()
    mk = getattr(th, "marqueur_sel", ())  # marqueur de sélection (ka59) : au-dessus de sa pièce, comme dans theorie.couches
    mk = set(mk[4] if len(mk) > 4 else mk[:1]) if mk else set()
    hauts = sorted(c for c in {c for c, _ in th.moves} | set(th.autonomes) | set(th.poussables) | fant | mk
                   if couche(c) > 0 or c in mk)
    if hauts:  # créé plus tard (bouton) passait par-dessus le joueur ; avant le calque du porteur (2,5), qui prime.
        # À couche égale, theorie.rendu dessine par classe croissante (cle_objet) : + classe / 10⁶ (g50t : le fantôme,
        # copie du joueur créée après lui, passait devant lui)
        regles.append({"nom": "calques des mobiles", "phase": 2.45, "quand": True,
                       "alors": [["pour", "$o", _objets(c), [["calque", "$o", (4 if c in mk else couche(c)) + c / 1e6]]]
                                 for c in hauts]})
    if th.porteur:  # C (CCM-177-B : re86, programme à 0,0 sans cette règle)
        regles += _porteur(th)
    if getattr(th, "peint_contact", ()):  # C (re86 N5, CCM-270-C) : la pièce prend la couleur de la palette touchée
        regles += _peint_contact(th)
    if getattr(th, "fantome", None):  # C (g50t) : boucle temporelle (Theorie._pas_fantome), état caché « trajet »
        regles += _fantome(th)
    if getattr(th, "tenue", ()):  # C (g50t) : porte cachée tant qu'un mobile chevauche sa dalle (theorie._tenir)
        mob = sorted({c for c, _ in th.moves} | set(th.poussables) | ({th.fantome[2]} if getattr(th, "fantome", None) else set()))
        mobiles = ["+", *[_objets(c) for c in mob]] if len(mob) > 1 else _objets(mob[0]) if mob else ["liste"]
        for p, d in th.tenue:
            occupee = ["existe", "$m", mobiles, ["existe", "$d", _objets(d), ["chevauche", "$m", "$d"]]]
            regles.append({"nom": f"tenue c{p} c{d}", "phase": 2.5, "quand": True,
                           "alors": [["pour", "$o", _objets(p), [["montrer", "$o", ["non", occupee]]]]]})
    if getattr(th, "tenue_cases", ()):  # C (g50t, CW-331.4) : porte pivotante (theorie._tenir_cases)
        r, n = _tenue_cases(th)
        regles += r
        non += n
    if getattr(th, "portes_cases", ()):  # theorie._tenir_cases : porte refermée sur le joueur → défaite (avant le but)
        for c in sorted({c for c, _ in th.moves}):
            ecrase = ["existe", "$e", _objets(c), ["ou", False, *[["non", x] for x in _portes_libres("$e", 0, 0, th, c)]]]
            regles.append({"nom": f"porte refermée sur c{c}", "phase": 2.9, "quand": ecrase, "alors": [["perdre"]]})
    for c, a, x0, y0 in getattr(th, "retour", ()):  # C (g50t) : sous l'action, le mobile revient à sa position de départ
        regles.append({"nom": f"retour c{c} {NOMS.get(a, a)}", "phase": 0.7, "quand": ["=", ["action"], NOMS.get(a, a)],
                       "alors": [["pour", "$o", _objets(c), [["placer", "$o", x0, y0]]]]})
    if th.but:
        q = _condition_but(th.but)
        if q is None:  # forme de but sans traduction : signalée, jamais exportée en « faux » muet (CCM-035-G)
            non.append(f"but {th.but[0]}")
        else:
            regles.append({"nom": f"but {th.but[0]}", "quand": q, "alors": [["niveau_suivant"]], "phase": 3})
    if autonomes:
        regles += _autonomes(th, w, h, chg)
    clics_ok = (th.motif or getattr(th, "motif_formes", ())) and not th.exclusif  # zone : _dans_zone (CW-228, ft09)
    if getattr(th, "selection_clic", ()):  # C (ka59 N4) : un clic sur un objet de la classe le sélectionne
        c, _x0, _y0 = th.selection_clic
        sous = ["filtrer", "$s", _objets(c), ["et", ["<=", ["x", "$s"], ["elem", ["case_clic"], 0]],
                                              ["<", ["elem", ["case_clic"], 0], ["+", ["x", "$s"], ["largeur", "$s"]]],
                                              ["<=", ["y", "$s"], ["elem", ["case_clic"], 1]],
                                              ["<", ["elem", ["case_clic"], 1], ["+", ["y", "$s"], ["hauteur", "$s"]]]]]
        jum = [512 + c % 16 + 16 * k for k in range(32) if 512 + c % 16 + 16 * k != c]  # jumeaux perçus (542 à ka59)
        regles.append({"nom": f"sélection : jumeaux de c{c} ramenés à c{c}", "phase": -2, "quand": True,
                       "alors": [["pour", "$j", ["filtrer", "$j", ["objets", {}], ["et", ["ou", False, *[_de_couleur("$j", k) for k in jum]],
                                                                                    [">", ["*", ["largeur", "$j"], ["hauteur", "$j"]], 1]]],
                                  [["recolorer", "$j", k, c] for k in jum]]]})
        regles.append({"nom": f"sélection au clic c{c}", "phase": -0.6,
                       "quand": ["et", ["contient", ["liste", "CLICK", "MOUSE"], ["action"]], ["!=", ["case_clic"], None]],
                       "alors": [["pour", "$s", ["liste", ["premier", sous]], [["si_alors", ["!=", "$s", None],
                                  [["poser", "_sel_x", ["x", "$s"]], ["poser", "_sel_y", ["y", "$s"]], ["poser", "_cc", 1]],
                                  []]]]]})
    if getattr(th, "selection_clic", ()) and getattr(th, "glisse", ()):
        regles += _glisse(th, w, h)
    if getattr(th, "selection_clic", ()) and getattr(th, "marqueur_sel", ()):
        regles += _marqueur_sel(th)
    if getattr(th, "clic_configs", ()):  # C (dc22 N3) : boutons → bascule de configuration (avant les autres clics)
        regles += _clic_configs(th, chg)
    if clics_ok:
        r = _clics(th, chg)
        if getattr(th, "clic_configs", ()):  # theorie.clic : un bouton qui a agi arrête le clic
            r["quand"] = ["et", r["quand"], ["!=", ["etat", "_cc"], 1]]
        regles.append(r)
    if th.derives:
        regles += _reflets(th, pas_undo)
    if undo:  # fin du coup : l'instantané pris au début n'est gardé (empilé) que si le coup a changé l'état
        regles.append({"nom": "empiler si changé", "phase": 4, "quand": ["et", pas_undo, ["=", ["etat", "change"], True]],
                       "alors": [["poser", "prof", ["+", ["etat", "prof"], 1]]]})
    if getattr(th, "jauge", ()):  # C (CW-333) : theorie._consommer / meurt. Défaite en phase 2.9, AVANT le but (3) : la
        # victoire, posée ensuite, remplace l'issue (Scene.issue) : un coup gagnant est gratuit (règle de F)
        regles.append({"nom": "jauge : un coup consommé", "phase": 0, "quand": True,
                       "alors": [["poser", "jauge", ["-", ["etat", "jauge"], 1]]]})
        regles.append({"nom": "jauge vide : défaite", "phase": 2.9, "quand": ["<=", ["etat", "jauge"], 0],
                       "alors": [["perdre"]]})
    if th.mort and th.mort[0] == "contact":  # D (CCM-177-B) : theorie.meurt → perdre (un plan mortel échoue en simulation)
        _, ca, cb = th.mort
        regles.append({"nom": f"mort c{ca} c{cb}", "phase": 3,
                       "quand": ["existe", "$a", _objets(ca), ["existe", "$b", _objets(cb), ["chevauche", "$a", "$b"]]],
                       "alors": [["perdre"]]})
    for nom, present in (("téléportation par case", th.teleports_cases),
                         ("clics (sélection exclusive)", th.motif and not clics_ok),
                         ("annulation (action hors NOMS)", th.annule is not None and not undo),
                         ("mort (forme inconnue)", th.mort and th.mort[0] != "contact")):
        if present:
            non.append(nom)
    non += _champs_inconnus(th)
    etat = ({"prof": 0} if undo else {}) | ({"sel": selection[2]} if selection else {})
    if getattr(th, "fantome", None):
        etat |= {"trajet": [], "_jx": None, "_jy": None}
    if getattr(th, "jauge", ()):
        etat |= {"jauge": th.jauge[0]}
    if getattr(th, "selection_clic", ()):
        etat |= {"_sel_x": th.selection_clic[1], "_sel_y": th.selection_clic[2]}
        if getattr(th, "marqueur_sel", ()):
            etat |= {"_mx": 0, "_my": 0}
        if getattr(th, "glisse", ()):
            etat |= {"_pousse": 0, "_gl_stop": 0}
    if th.selection and not selection:
        non.append("sélection (sélecteur hors NOMS)")
    return {"etat": etat, "mode": "lois", "regles": regles}, non


def _glisse(th, w, h):
    """theorie._glisser (ka59, CCM-041-G) : sous une flèche, si la pièce sélectionnée avancerait sur une autre pièce de sa
    classe, celle-ci glisse par pas, au plus glisse[0] cases, tant qu'elle reste dans la grille et ne recouvre que des
    couleurs traversées ; le contenu de son trou la suit ; le sélectionné ne bouge pas (état _pousse). Boucle déroulée."""
    c = th.selection_clic[0]
    dmax, trav = th.glisse[:2]
    autres = sorted({k % 16 if k >= 16 else k for k in (th.glisse[2] if len(th.glisse) > 2 else ())} - {c % 16})
    obst = [k for k in range(16) if k not in {t % 16 if t >= 16 else t for t in trav}]
    regles = [{"nom": "glissade : remise à zéro", "phase": -2, "quand": True, "alors": [["poser", "_pousse", 0]]}]
    for a in sorted({a for cc, a in th.moves if cc == c}):
        dx, dy = th.moves[(c, a)]
        pas = abs(dx) + abs(dy)
        if not pas:
            continue
        sel = ["premier", ["filtrer", "$s", _objets(c), ["et", ["=", ["x", "$s"], ["etat", "_sel_x"]],
                                                         ["=", ["y", "$s"], ["etat", "_sel_y"]]]]]
        boite = ["et", ["!=", "$p", "$s"],  # boîte du sélectionné décalé ∩ boîte de $p
                 ["<", ["x", "$p"], ["+", ["+", ["x", "$s"], dx], ["largeur", "$s"]]],
                 ["<", ["+", ["x", "$s"], dx], ["+", ["x", "$p"], ["largeur", "$p"]]],
                 ["<", ["y", "$p"], ["+", ["+", ["y", "$s"], dy], ["hauteur", "$s"]]],
                 ["<", ["+", ["y", "$s"], dy], ["+", ["y", "$p"], ["hauteur", "$p"]]]]
        # autre classe poussée (bloc c11, en croix) : contact AUX CASES (libre faux), sinon la pièce entre dans un creux
        devant = ["+", ["filtrer", "$p", _objets(c), boite],
                  *[["filtrer", "$p", _objets(k), ["et", boite, ["non", ["libre", "$s", dx, dy, {"couleur": k}]]]] for k in autres]]
        dedans = ["filtrer", "$r", ["objets", {}], ["et", ["non", _de_couleur("$r", c)],
                                                  [">", ["x", "$r"], ["x", "$p"]], [">", ["y", "$r"], ["y", "$p"]],
                                                  ["<", ["+", ["x", "$r"], ["largeur", "$r"]], ["+", ["x", "$p"], ["largeur", "$p"]]],
                                                  ["<", ["+", ["y", "$r"], ["hauteur", "$r"]], ["+", ["y", "$p"], ["hauteur", "$p"]]],
                                                  ["non", ["et", ["<=", ["x", "$s"], ["x", "$r"]], ["<=", ["y", "$s"], ["y", "$r"]],  # pas
                                                           ["<=", ["+", ["x", "$r"], ["largeur", "$r"]], ["+", ["x", "$s"], ["largeur", "$s"]]],  # dans
                                                           ["<=", ["+", ["y", "$r"], ["hauteur", "$r"]], ["+", ["y", "$s"], ["hauteur", "$s"]]]]]]]  # le pousseur
        libre = ["et", *_dans("$p", dx, dy, w, h), *[["libre", "$p", dx, dy, {"couleur": k}] for k in obst],
                 *([_couvert("$p", dx, dy)] if th.fond_solide else [])]  # fond solide : glisse sur les objets seulement
        par_classe = dict(th.glisse[3]) if len(th.glisse) > 3 else {}
        prolonge = sorted({k % 16 if k >= 16 else k for k in (th.glisse[4] if len(th.glisse) > 4 else ())})
        dmx = 3 * max([dmax, *par_classe.values()]) if prolonge else max([dmax, *par_classe.values()])

        def permis_k(k, par_classe=par_classe, pas=pas, prolonge=prolonge):
            """Le k-ième pas : dans la distance de base (par classe si apprise), sinon seulement si $p chevauche encore une
            classe prolongeante (theorie._glisser, CCM-299-C)."""
            if k * pas <= max([dmax, *par_classe.values()]):
                ok = [f for f, d in par_classe.items() if d >= k * pas]
                return ["ou", False, *[_de_couleur("$p", f) for f in ok]] if par_classe else True
            return ["ou", False, *[["non", ["libre", "$p", 0, 0, {"couleur": c2}]] for c2 in prolonge]]
        pas_k = [["si_alors", ["et", ["!=", ["etat", "_gl_stop"], 1], permis_k(k), libre],
                  [["pour", "$r", dedans, [["deplacer", "$r", dx, dy]]], ["deplacer", "$p", dx, dy], ["poser", "_pousse", 1]],
                  [["poser", "_gl_stop", 1]]] for k in range(1, dmx // pas + 1)]
        regles.append({"nom": f"glissade c{c} {NOMS.get(a, a)}", "phase": -0.3, "quand": ["=", ["action"], NOMS.get(a, a)],
                       "alors": [["poser", "_gl_stop", 0],
                                 ["pour", "$s", ["filtrer", "$s", ["liste", sel], ["!=", "$s", None]],
                                  [["pour", "$p", ["liste", ["premier", devant]], [["si_alors", ["!=", "$p", None], pas_k, []]]]]]]})
    return regles


def _marqueur_sel(th):
    """theorie._pas_selection_clic avec marqueur_sel (ka59 sous CREUX) : le marqueur, noté avant le coup, est replacé dans
    le trou du sélectionné après les déplacements ; un clic qui sélectionne vide le trou de la pièce cliquée."""
    c = th.selection_clic[0]
    k, _cs, dx, dy = th.marqueur_sel[:4]
    vues = th.marqueur_sel[4] if len(th.marqueur_sel) > 4 else (k,)  # classes perçues du marqueur (0 et 272 à ka59)
    marques = ["+", *[_objets(v) for v in vues]] if len(vues) > 1 else _objets(vues[0])
    hote = ["premier", ["filtrer", "$h", _objets(c), ["et", ["=", ["x", "$h"], ["etat", "_sel_x"]],
                                                     ["=", ["y", "$h"], ["etat", "_sel_y"]]]]]
    dedans = ["et", ["non", _de_couleur("$o", c)], [">", ["x", "$o"], ["x", "$p"]], [">", ["y", "$o"], ["y", "$p"]],
              ["<", ["+", ["x", "$o"], ["largeur", "$o"]], ["+", ["x", "$p"], ["largeur", "$p"]]],
              ["<", ["+", ["y", "$o"], ["hauteur", "$o"]], ["+", ["y", "$p"], ["hauteur", "$p"]]]]
    marqueur = ["filtrer", "$m", marques, ["et", ["=", ["x", "$m"], ["etat", "_mx"]], ["=", ["y", "$m"], ["etat", "_my"]]]]
    sur_p = ["et", ["<=", ["x", "$p"], ["elem", ["case_clic"], 0]], ["<", ["elem", ["case_clic"], 0], ["+", ["x", "$p"], ["largeur", "$p"]]],
             ["<=", ["y", "$p"], ["elem", ["case_clic"], 1]], ["<", ["elem", ["case_clic"], 1], ["+", ["y", "$p"], ["hauteur", "$p"]]]]
    # theorie._pas_selection_clic sur une image : la pièce qui porte le marqueur (à son décalage) est la sélectionnée
    porte = ["filtrer", "$s", _objets(c), ["existe", "$q", marques, ["et", ["=", ["x", "$q"], ["+", ["x", "$s"], dx]],
                                                                      ["=", ["y", "$q"], ["+", ["y", "$s"], dy]]]]]
    return [{"nom": "sélection : la pièce qui porte le marqueur", "phase": -1.5, "quand": ["=", ["longueur", porte], 1],
             "alors": [["pour", "$s", porte, [["poser", "_sel_x", ["x", "$s"]], ["poser", "_sel_y", ["y", "$s"]]]]]},
            {"nom": "marqueur de sélection : noté", "phase": -1, "quand": True,  # objet du marqueur au décalage d'un hôte
             "alors": [["pour", "$m", ["filtrer", "$m", marques, ["existe", "$h", ["objets", {}], [
                 "et", ["!=", "$h", "$m"], ["=", ["x", "$h"], ["-", ["x", "$m"], dx]], ["=", ["y", "$h"], ["-", ["y", "$m"], dy]],
                 [">", ["largeur", "$h"], dx + 1], [">", ["hauteur", "$h"], dy + 1]]]],
                        [["poser", "_mx", ["x", "$m"]], ["poser", "_my", ["y", "$m"]]]]]},
            {"nom": "marqueur de sélection : trou de la pièce cliquée vidé", "phase": -0.55,
             "quand": ["et", ["contient", ["liste", "CLICK", "MOUSE"], ["action"]], ["!=", ["case_clic"], None]],
             "alors": [["pour", "$p", ["liste", hote], [["si_alors", ["et", ["!=", "$p", None], sur_p],
                        [["pour", "$o", ["filtrer", "$o", ["objets", {}], dedans], [["retirer", "$o"]]]], []]]]]},
            {"nom": "marqueur de sélection : suit le sélectionné", "phase": 2.4, "quand": True,
             "alors": [["pour", "$m", marqueur, [["placer", "$m", ["+", ["etat", "_sel_x"], dx],
                                                  ["+", ["etat", "_sel_y"], dy]]]]]}]


# Champs de Theorie que l'export connaît : traités ci-dessus, ou métadonnées sans effet sur la dynamique. Un champ AJOUTÉ à
# Theorie et absent d'ici est déclaré non exporté (CCM-177-B : le porteur disparaissait en silence, re86 0,95 → 0,0).
CHAMPS_CONNUS = frozenset({
    "moves", "solides", "poussables", "consomme", "lie", "autonomes", "motif", "bascule", "zone", "derives",
    "teleports_cases", "teleports", "saut", "transforme", "annule", "hotes", "formes_bascule", "porteur", "fond_solide",
    "exclusif", "but", "mort",
    # métadonnées (hypothèses, registre, formes de création, masque, buts concurrents, contrat du but)
    "murs_supposes", "moves_supposes", "formes", "hors_jeu", "buts_compatibles", "buts_motifs", "obligations", "desel",
    # exportés depuis CCM-132-C (sémantique de C) : sélection cachée, débordement
    "selection", "debordent",
    # enroulement (tr87, C)
    "enroule", "retour", "fantome", "tenue", "_dalles", "tenue_cases", "jauge", "motif_formes", "portes_cases", "clic_configs", "saut_sel", "sans_effet", "selection_clic", "marqueur_sel", "peint_contact", "glisse",
})


def _champs_inconnus(th):
    from dataclasses import fields
    out = []
    for f in fields(th):
        if f.name in CHAMPS_CONNUS:
            continue
        v = getattr(th, f.name)
        defaut = f.default if f.default is not f.default_factory else None
        if v not in (None, False, 0, (), frozenset(), {}, []) and v != defaut:
            out.append(f"champ inconnu de l'export : {f.name}")
    return out


def _chaque_pixel(v, cond):
    return ["tous", "$px", ["intervalle", 0, ["largeur", v]],
            ["tous", "$py", ["intervalle", 0, ["hauteur", v]],
             ["ou", ["<", ["pixel", v, "$px", "$py"], 0], cond]]]


def _couvert(v, dx, dy, sources=None):
    x, y = ["+", ["+", ["x", v], dx], "$px"], ["+", ["+", ["y", v], dy], "$py"]
    os = ["a", x, y] if sources is None else sources
    c = ["existe", "$cover", os, ["et", ["!=", "$cover", v],
         [">=", ["-", x, ["x", "$cover"]], 0], ["<", ["-", x, ["x", "$cover"]], ["largeur", "$cover"]],
         [">=", ["-", y, ["y", "$cover"]], 0], ["<", ["-", y, ["y", "$cover"]], ["hauteur", "$cover"]],
         [">=", ["pixel", "$cover", ["-", x, ["x", "$cover"]], ["-", y, ["y", "$cover"]]], 0]]]
    return _chaque_pixel(v, c)


def _hors_masque(v, dx, dy, masque):
    x,y = ["+", ["+", ["x",v],dx],"$px"], ["+", ["+", ["y",v],dy],"$py"]
    return _chaque_pixel(v, ["non", ["ou", False, *[["et", ["=",x,c], ["=",y,r]] for r,c in sorted(masque)]]])


def _deborde(v, dx, dy, w, h):
    """L'objet v décalé de (dx, dy) garde au moins une case de sa boîte dans la grille."""
    return [["<", ["+", ["x", v], dx], w], [">", ["+", ["+", ["x", v], dx], ["largeur", v]], 0],
            ["<", ["+", ["y", v], dy], h], [">", ["+", ["+", ["y", v], dy], ["hauteur", v]], 0]]


def _dans(v, dx, dy, w, h):
    """L'objet v décalé de (dx, dy) reste dans la grille (toute sa boîte)."""
    return [["<=", 0, ["+", ["x", v], dx]], ["<=", ["+", ["+", ["x", v], dx], ["largeur", v]], w],
            ["<=", 0, ["+", ["y", v], dy]], ["<=", ["+", ["+", ["y", v], dy], ["hauteur", v]], h]]


def _teleporte(th):
    """theorie.pas : arriver sur un objet de classe K décale encore de D (1re classe K touchée, ordre du dict)."""
    if not th.teleports:
        return []
    chaine = []
    for k, (tx, ty) in reversed(list(th.teleports.items())):
        chaine = [["si_alors", ["existe", "$k", _objets(k), ["chevauche", "$o", "$k"]], [["deplacer", "$o", tx, ty]],
                   chaine]]
    return chaine


def _pas_pousse(th, c, dx, dy, w, h, saut=(), apres=()):
    """Pas du mobile $o avec la poussée de theorie.pas (un seul étage, tout ou rien) : $o avance ; les poussables d'une
    autre couleur qu'il recouvre alors doivent pouvoir avancer (grille, ni solide ni poussable sur leur case cible),
    sinon $o recule. Sans poussable : simple déplacement."""
    ps = sorted(set(th.poussables) - {c})
    if not ps:
        return [["deplacer", "$o", dx, dy], *apres]
    touches = ["filtrer", "$p", ["objets", {}], ["et", ["ou", False, *[["existe", "$q", _objets(q), ["=", "$q", "$p"]]
                                                                       for q in ps]], ["chevauche", "$o", "$p"]]]
    bloq = sorted(set(th.solides) | set(th.poussables))
    peut = ["et", *_dans("$p", dx, dy, w, h), *[["libre", "$p", dx, dy, {"couleur": b}] for b in bloq]]
    return [["deplacer", "$o", dx, dy],
            ["si_alors", ["tous", "$p", touches, peut],
             [["pour", "$p", touches, [["deplacer", "$p", dx, dy]]], *apres],
             [["deplacer", "$o", -dx, -dy], *saut]]]


def _autonomes(th, w, h, chg=()):
    """Agents autonomes de theorie.pas (phase 2, après consommation et liens) : si le joueur a bougé, chaque objet de
    couleur A fait un pas glouton vers le 1er objet (x, puis y, croissants) de la couleur poursuivie ; 1re direction de
    ORDRE_POURSUITE qui rapproche et dont la case est dans la grille et libre de solides et de poussables."""
    from chrysalide.arc3.logique.theorie import ORDRE_POURSUITE
    bloq = sorted(set(th.solides) | set(th.poussables))
    out = []
    for ca, cp in sorted(th.autonomes.items()):
        cible = ["argmin", "$p", _objets(cp), ["+", ["*", ["x", "$p"], 100000], ["y", "$p"]]]
        rapproche = {(1, 0): [">", ["x", "$c"], ["x", "$a"]], (-1, 0): ["<", ["x", "$c"], ["x", "$a"]],
                     (0, 1): [">", ["y", "$c"], ["y", "$a"]], (0, -1): ["<", ["y", "$c"], ["y", "$a"]]}
        chaine = []
        for dx, dy in reversed(ORDRE_POURSUITE):  # si_alors imbriqués : la 1re direction possible l'emporte
            ok = ["et", rapproche[(dx, dy)], *_dans("$a", dx, dy, w, h),
                  *[["libre", "$a", dx, dy, {"couleur": b}] for b in bloq]]
            chaine = [["si_alors", ok, [["deplacer", "$a", dx, dy], *chg], chaine]]
        out.append({"nom": f"poursuit c{ca} c{cp}", "phase": 2,
                    "quand": ["et", ["=", ["etat", "bouge"], True], ["non", ["vide", _objets(cp)]]],
                    "alors": [["pour", "$a", _objets(ca), [["pour", "$c", ["liste", cible], chaine]]]]})
    return out


COULEURS = range(16)


def _de_couleur(v, c):
    return ["existe", "$q", _objets(c), ["=", "$q", v]]


def _dans_zone(v, zone):
    """theorie.clic avec zone : la boîte de v est dans la boîte d'un objet de couleur `zone` plus grand que lui."""
    z = "$zz"
    return ["existe", z, _objets(zone), ["et", ["<=", ["x", z], ["x", v]], ["<=", ["y", z], ["y", v]],
                                        ["<=", ["+", ["x", v], ["largeur", v]], ["+", ["x", z], ["largeur", z]]],
                                        ["<=", ["+", ["y", v], ["hauteur", v]], ["+", ["y", z], ["hauteur", z]]],
                                        [">", ["*", ["largeur", z], ["hauteur", z]], ["*", ["largeur", v], ["hauteur", v]]]]]


def _forme_bascule(v, th):
    """theorie.formes_bascule (ft09 N3) : seul un objet d'une forme déjà vue basculer est cliquable ; la forme est
    comparée par sa boîte (largeur, hauteur) et son nombre de pixels opaques."""
    if not th.formes_bascule:
        return []
    def dims(f):
        xs, ys = [x for x, _ in f], [y for _, y in f]
        return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    return [["ou", False, *[["et", ["=", ["largeur", v], w], ["=", ["hauteur", v], h]]
                            for w, h in sorted({dims(f) for f in th.formes_bascule})]]]


def _portes_libres(v, dx, dy, th, c):
    """theorie.portes_cases : l'objet v décalé de (dx, dy) ne couvre aucune case de porte encore peinte (opaque) dans un
    objet de la classe porte."""
    out = []
    for p, cs in getattr(th, "portes_cases", ()):
        if p == c:
            continue
        for x, y in sorted(cs):
            moi = ["pixel", v, ["-", x, ["+", ["x", v], dx]], ["-", y, ["+", ["y", v], dy]]]
            porte = ["pixel", "$q", ["-", x, ["x", "$q"]], ["-", y, ["y", "$q"]]]
            out.append(["non", ["et", ["non", ["ou", ["=", moi, None], ["<", moi, 0]]],
                                ["existe", "$q", _objets(p), ["non", ["ou", ["=", porte, None], ["<", porte, 0]]]]]])
    return out


def _clic_configs(th, chg=()):
    """theorie._clic_config : sur un clic dans le bouton, la 1re règle applicable : échange des objets d'une case posés
    en P et en Q ; ou « avant » présent en entier, « après » absent, aucun mobile sur les cases touchées → avant
    remplacé par après (ou l'inverse). etat « _cc » = 1 si un bouton a agi (les autres clics sont alors ignorés)."""
    cx, cy = ["elem", ["case_clic"], 0], ["elem", ["case_clic"], 1]
    mob = sorted({c for c, _ in th.moves})
    mobiles = ["+", *[_objets(c) for c in mob]] if len(mob) > 1 else _objets(mob[0]) if mob else ["liste"]

    def objet(o, v):  # l'objet o (classe, forme, x, y) est présent : v le désigne
        return ["et", ["=", ["x", v], o[2]], ["=", ["y", v], o[3]], _forme_egale(v, o[1])]

    def present(o):
        return ["existe", "$q", _objets(o[0]), objet(o, "$q")]

    def libre(cases):
        out = []
        for x, y in sorted(cases):
            px = ["pixel", "$m", ["-", x, ["x", "$m"]], ["-", y, ["y", "$m"]]]
            out.append(["non", ["existe", "$m", mobiles, ["non", ["ou", ["=", px, None], ["<", px, 0]]]]])
        return out

    def remplacer(av, ap):
        cond = ["et", *[present(o) for o in sorted(av, key=str)], *[["non", present(o)] for o in sorted(ap, key=str)],
                *libre({(o[2] + dx, o[3] + dy) for o in av | ap for dx, dy in o[1]})]
        modele = ["premier", ["+", *[_objets(o[0]) for o in sorted(av | ap, key=str)]]]
        creer = []
        for o in sorted(ap, key=str):
            w, h = max(dx for dx, _ in o[1]) + 1, max(dy for _, dy in o[1]) + 1
            motif = ["liste", *[["liste", *[o[0] if (i, j) in o[1] else -1 for i in range(w)]] for j in range(h)]]
            creer.append(["soit_creer", "$n", modele, o[2], o[3], [["poser_motif", "$n", motif]]])
        retirer = [["pour", "$q", ["filtrer", "$q", _objets(o[0]), objet(o, "$q")], [["retirer", "$q"]]]
                   for o in sorted(av, key=str)]
        return cond, [*creer, *retirer, ["poser", "_cc", 1], *chg]

    regles = [{"nom": "boutons : remis à zéro", "phase": -1, "quand": True, "alors": [["poser", "_cc", 0]]}]
    for k, r in enumerate(th.clic_configs):
        b = r[0]
        sur = ["ou", False, *[["et", ["=", cx, b[2] + dx], ["=", cy, b[3] + dy]] for dx, dy in sorted(b[1])]]
        quand = ["et", ["contient", ["liste", "CLICK", "MOUSE"], ["action"]], ["!=", ["case_clic"], None],
                 ["!=", ["etat", "_cc"], 1], sur]
        if r[1] == "echange":
            p, q = r[2], r[3]
            def en(z):
                return ["filtrer", "$e", ["objets", {}], ["et", ["=", ["x", "$e"], z[0]], ["=", ["y", "$e"], z[1]],
                                                          ["=", ["largeur", "$e"], 1], ["=", ["hauteur", "$e"], 1]]]
            cond = ["et", ["non", ["vide", en(p)]], ["non", ["vide", en(q)]]]
            marque = ["filtrer", "$e", ["objets", {}], ["!=", ["attr", "$e", "_ech"], None]]
            alors = [["pour", "$e", en(p), [["poser_attr", "$e", "_ech", "q"]]],
                     ["pour", "$e", en(q), [["poser_attr", "$e", "_ech", "p"]]],
                     ["pour", "$e", marque, [["si_alors", ["=", ["attr", "$e", "_ech"], "q"], [["placer", "$e", *q]],
                                              [["placer", "$e", *p]]], ["poser_attr", "$e", "_ech", None]]],
                     ["poser", "_cc", 1], *chg]
            regles.append({"nom": f"bouton {k} : échange", "phase": -0.5, "quand": ["et", quand, cond], "alors": alors})
            continue
        c1, e1 = remplacer(r[1], r[2])
        c2, e2 = remplacer(r[2], r[1])
        regles.append({"nom": f"bouton {k}", "phase": -0.5, "quand": quand,
                       "alors": [["si_alors", c1, e1, [["si_alors", c2, e2, []]]]]})
    return regles


def _forme_egale(v, f):
    """L'objet v a exactement la forme f : même boîte, et chaque case de la boîte opaque si et seulement si elle est dans f."""
    x0, y0 = min(x for x, _ in f), min(y for _, y in f)
    w, h = max(x for x, _ in f) - x0 + 1, max(y for _, y in f) - y0 + 1
    cases = [[">=", ["pixel", v, i, j], 0] if (x0 + i, y0 + j) in f else ["<", ["pixel", v, i, j], 0]
             for j in range(h) for i in range(w)]
    return ["et", ["=", ["largeur", v], w], ["=", ["hauteur", v], h], *cases]


def _clics(th, chg=()):
    """theorie.clic (sans zone ni sélection exclusive) : objet cliqué = celui de plus petite (couleur, x, y) sous le clic ;
    tout objet de même taille (approximation de « même forme »), à un décalage du motif et d'une couleur de `bascule`,
    passe à la couleur suivante. Deux passes (marquer, puis recolorer) : pas de bascule en cascade."""
    sous = ["a", ["elem", ["case_clic"], 0], ["elem", ["case_clic"], 1]]
    cle = ["+", ["*", ["x", "$v"], 100000], ["y", "$v"]]
    choix = None
    for c in reversed(COULEURS):  # la plus petite couleur présente sous le clic l'emporte
        cond = [_de_couleur("$v", c)] + ([_dans_zone("$v", th.zone)] if th.zone is not None else []) + _forme_bascule("$v", th)
        de_c = ["filtrer", "$v", sous, cond[0] if len(cond) == 1 else ["et", *cond]]
        choix = ["si", ["vide", de_c], choix, ["argmin", "$v", de_c, cle]]
    decale = ["ou", False, *[["et", ["=", ["-", ["x", "$j"], ["x", "$o"]], dx], ["=", ["-", ["y", "$j"], ["y", "$o"]], dy]]
                             for dx, dy in sorted(th.motif)]]
    meme = ["et", ["=", ["largeur", "$j"], ["largeur", "$o"]], ["=", ["hauteur", "$j"], ["hauteur", "$o"]], decale]
    if getattr(th, "motif_formes", ()):  # C (ft09 N5) : voisinage selon la forme cliquée (theorie.clic, motif_formes)
        def c2(v, axe):  # 2 × centre de la boîte, à une constante près (identique pour $j et $o)
            return ["+", ["*", 2, [axe, v]], ["largeur" if axe == "x" else "hauteur", v]]
        connues = [_forme_egale("$o", f) for f, _ in th.motif_formes]
        par_forme = [["et", _forme_egale("$o", f), ["ou", False, *[
            ["et", ["=", ["-", c2("$j", "x"), c2("$o", "x")], dx], ["=", ["-", c2("$j", "y"), c2("$o", "y")], dy],
             _forme_egale("$j", fj)] for dx, dy, fj in sorted(dec, key=lambda d: (d[0], d[1], sorted(d[2])))]]]
            for f, dec in th.motif_formes]
        meme = ["ou", False, *par_forme, ["et", ["non", ["ou", False, *connues]], meme if th.motif else False]]
    marquer = [["pour", "$j", ["filtrer", "$j", _objets(b), meme], [["poser_attr", "$j", "_bascule", b]]]
               for b in sorted(th.bascule)]
    basculer = [["pour", "$j", ["filtrer", "$j", _objets(b), ["=", ["attr", "$j", "_bascule"], b]],
                 [["recolorer", "$j", b, b2], ["poser_attr", "$j", "_bascule", None], *chg]] for b, b2 in sorted(th.bascule.items())]
    return {"nom": "clic", "phase": 0, "quand": ["et", ["contient", ["liste", "CLICK", "MOUSE"], ["action"]],  # porte : ("MOUSE", r, c)
                                                ["!=", ["case_clic"], None]],
            "alors": [["pour", "$o", ["filtrer", "$v", ["liste", choix], ["!=", "$v", None]], marquer], *basculer]}


def _reflechir(source, sens, a2, couleur, de):
    """Effets : copie miroir de l'objet `source` (reflet de theorie.reflet par l'axe 2·axe = a2), recolorée en `couleur`,
    sous tous les calques, marquée `_reflet` (à défaire par l'appelant). `refleter` du langage envoie x sur 2c − 1 − x :
    c = (a2 + 1) // 2, puis décalage d'une case si a2 est pair."""
    c = (a2 + 1) // 2
    d = a2 - (2 * c - 1)
    neuf = ["filtrer", "$r", ["objets", {}], ["=", ["attr", "$r", "_reflet"], 1]]
    return [["poser_attr", source, "_reflet", 1], ["refleter", source, sens, c], ["poser_attr", source, "_reflet", None],
            ["pour", "$r", neuf, [["recolorer", "$r", de, couleur], ["calque", "$r", -1],
                                  ["deplacer", "$r", d if sens == "x" else 0, d if sens == "y" else 0],
                                  ["poser_attr", "$r", "_reflet", 2]]]]


def _reflets(th, pas_undo):
    """theorie.deriver, recalculé après chaque coup (phase 2,5 : après les autonomes, avant le but). Reflet (clé tuple) :
    les objets de la classe D sont retirés puis refaits comme reflet des classes sources, cases occupées par les autres
    objets effacées ; miroir (clé simple) : D = source ∪ reflet(source). Le découpage atomes / composantes n'est pas rendu
    (un sprite par objet source) : seule l'image est garantie, jugée par la porte."""
    out = []
    for d, v in sorted(th.derives.items(), key=str):
        if isinstance(d, tuple):
            classe, (src, sens, a2, _atom) = d[1], v
            srcs = sorted(src)
        else:
            classe, (s0, sens, a2) = d, v
            srcs = [s0]
        sens_l = ["x", "y"] if sens == "xy" else [sens]
        effets = [["pour", "$d", _objets(classe), [["retirer", "$d"]]]]
        for sc in srcs:
            corps = []
            if not isinstance(d, tuple):  # miroir : la source elle-même fait partie de D
                corps.append(["soit_creer", "$m", "$s", ["x", "$s"], ["y", "$s"],
                              [["recolorer", "$m", sc, classe], ["calque", "$m", -1], ["poser_attr", "$m", "_reflet", 4]]])
            corps += _reflechir("$s", sens_l[0], a2, classe, sc)
            if len(sens_l) == 2:  # 'xy' : reflet x puis reflet y du résultat (le reflet intermédiaire est retiré)
                inter = ["filtrer", "$i", ["objets", {}], ["=", ["attr", "$i", "_reflet"], 2]]
                corps.append(["pour", "$i", inter, [["poser_attr", "$i", "_reflet", 3], *_reflechir("$i", "y", a2, classe, classe),
                                                     ["retirer", "$i"]]])
            effets.append(["pour", "$s", _objets(sc), corps])
        if isinstance(d, tuple):  # cases occupées par un objet ni source ni dérivé : effacées du reflet
            faits = ["filtrer", "$r", ["objets", {}], ["=", ["attr", "$r", "_reflet"], 2]]
            autre = ["existe", "$u", ["a", ["+", ["x", "$r"], "$i"], ["+", ["y", "$r"], "$j"]],
                     ["et", ["!=", "$u", "$r"], ["!=", ["attr", "$u", "_reflet"], 2],
                      *[["non", _de_couleur("$u", q)] for q in srcs]]]
            effets.append(["pour", "$r", faits, [["pour", "$i", ["intervalle", 0, ["largeur", "$r"]], [
                ["pour", "$j", ["intervalle", 0, ["hauteur", "$r"]], [
                    ["si_alors", ["et", [">=", ["pixel", "$r", "$i", "$j"], 0], autre], [["ecrire", "$r", "$j", "$i", -1]], []]]]]]]])
        effets.append(["pour", "$r", ["filtrer", "$r", ["objets", {}], ["!=", ["attr", "$r", "_reflet"], None]],
                       [["poser_attr", "$r", "_reflet", None]]])
        quand = pas_undo if isinstance(d, tuple) else ["et", pas_undo, ["non", ["vide", _objets(classe)]]]  # miroir : D existe
        out.append({"nom": f"reflet c{classe}", "phase": 2.5, "quand": quand, "alors": effets})
    return out


def _hors_palette(v, th):
    """Conditions « v n'est pas un objet palette » (theorie.peint_contact : couleur ET taille de la palette)."""
    out = []
    for k, f in sorted(getattr(th, "peint_contact", ()), key=str):
        w, h = max(x for x, _ in f) + 1, max(y for _, y in f) + 1
        out.append(["non", ["et", _de_couleur(v, k % 16 if k >= 16 else k), ["=", ["largeur", v], w], ["=", ["hauteur", v], h]]])
    return out


def _peint_contact(th):
    """theorie._peindre (re86 N5) : une pièce (hôte, plus d'une case, pas une palette) qui touche une palette d'une autre
    couleur en prend la couleur. Contact approché par les boîtes (écart ≤ 1)."""
    sources = sorted({c for c, _ in th.hotes} | {c for c, _ in th.moves if c < 512})
    regles = []
    for k, f in sorted(th.peint_contact, key=str):
        col = k % 16 if k >= 16 else k
        w, h = max(x for x, _ in f) + 1, max(y for _, y in f) + 1
        pal = ["filtrer", "$p", _objets(col), ["et", ["=", ["largeur", "$p"], w], ["=", ["hauteur", "$p"], h]]]
        touche = ["existe", "$p", pal, ["et", ["<=", ["x", "$p"], ["+", ["x", "$o"], ["largeur", "$o"]]],
                                         ["<=", ["x", "$o"], ["+", ["x", "$p"], w]],
                                         ["<=", ["y", "$p"], ["+", ["y", "$o"], ["hauteur", "$o"]]],
                                         ["<=", ["y", "$o"], ["+", ["y", "$p"], h]]]]
        pieces = ["filtrer", "$o", ["objets", {}], ["et", ["ou", False, *[_de_couleur("$o", c) for c in sources if c % 16 != col]],
                                                    [">", ["*", ["largeur", "$o"], ["hauteur", "$o"]], 1], *_hors_palette("$o", th)]]
        regles.append({"nom": f"peint au contact c{col}", "phase": 0.55, "quand": True,
                       "alors": [["pour", "$o", pieces, [["si_alors", touche,
                                                          [["recolorer", "$o", c, col] for c in sources if c % 16 != col], []]]]]})
    return regles


def _porteur(th):
    """theorie._pas_porteur : (1) avant les lois, la position du marqueur est notée ; (2) après, si le marqueur a bougé,
    la pièce qui couvrait sa position notée (plus d'une case, d'une classe hôte) bouge du même pas ; (3) sous le
    sélecteur, le marqueur saute au centre de la pièce hôte suivante (ordre ligne puis colonne, cyclique)."""
    m, sel = th.porteur
    hotes = sorted({c for c, _ in th.hotes} | {k % 16 if k >= 16 else k for k, _ in getattr(th, "peint_contact", ())})
    piece = ["et", ["ou", False, *[_de_couleur("$h", c) for c in hotes]],
             ["non", ["et", ["=", ["largeur", "$h"], 1], ["=", ["hauteur", "$h"], 1]]], *_hors_palette("$h", th)]
    px, py = ["attr", "$m", "_px"], ["attr", "$m", "_py"]
    dx, dy = ["-", ["x", "$m"], px], ["-", ["y", "$m"], py]
    noter = {"nom": "porteur noter", "phase": -1, "quand": True,
             "alors": [["pour", "$m", _objets(m), [["poser_attr", "$m", "_px", ["x", "$m"]], ["poser_attr", "$m", "_py", ["y", "$m"]]]]]}
    def hote(x, y):  # theorie.porteuse : la pièce qui couvre la case ; sinon (CHRYS_PORTEUR_BOITE) la plus petite pièce
        couvre = ["premier_tel_que", "$h", ["a", x, y], piece]  # creuse dont la boîte contient le marqueur (centre vide)
        if os.environ.get("CHRYS_PORTEUR_BOITE") != "1":
            return couvre
        creuses = ["filtrer", "$b", ["objets", {}], ["et", ["ou", False, *[_de_couleur("$b", c) for c in hotes]],
                                                     [">", ["*", ["largeur", "$b"], ["hauteur", "$b"]], 1],
                                                     ["<=", ["x", "$b"], x], ["<", x, ["+", ["x", "$b"], ["largeur", "$b"]]],
                                                     ["<=", ["y", "$b"], y], ["<", y, ["+", ["y", "$b"], ["hauteur", "$b"]]]]]
        return ["si", ["!=", couvre, None], couvre,
                ["argmin", "$b", creuses, ["*", ["largeur", "$b"], ["hauteur", "$b"]]]]
    suivre = {"nom": "porteur suivre", "phase": 0.5, "quand": ["!=", ["action"], NOMS.get(sel, "")],
              "alors": [["pour", "$m", _objets(m), [["si_alors", ["non", ["et", ["=", dx, 0], ["=", dy, 0]]],
                                                     [["pour", "$h", ["filtrer", "$h", ["liste", hote(px, py)],
                                                                         ["!=", "$h", None]], [["deplacer", "$h", dx, dy]]]], []]]]]}
    toutes = ["filtrer", "$h", ["objets", {}], piece]
    triees = ["trier", toutes, "$v", ["+", ["*", ["y", "$v"], 1000], ["x", "$v"]]]
    courant = hote(["x", "$m"], ["y", "$m"])
    suivante = ["suivant", triees, courant]
    defaut = [["pour", "$s", ["filtrer", "$s", ["liste", suivante], ["!=", "$s", None]],
               [["placer", "$m", ["+", ["x", "$s"], ["//", ["-", ["largeur", "$s"], 1], 2]],
                 ["+", ["y", "$s"], ["//", ["-", ["hauteur", "$s"], 1], 2]]]]]]
    effets = defaut
    for f0, f1, (ddx, ddy) in reversed(getattr(th, "saut_sel", ())):  # C (re86 N5) : sauts APPRIS forme → forme, décalage
        cible = ["premier_tel_que", "$t", triees, ["et", ["!=", "$t", courant], _forme_egale("$t", f1)]]
        effets = [["si_alors", ["et", ["!=", courant, None], ["existe", "$c", ["liste", courant],
                                                              ["et", ["!=", "$c", None], _forme_egale("$c", f0)]],
                                ["!=", cible, None]],
                   [["pour", "$s", ["liste", cible], [["placer", "$m", ["+", ["x", "$s"], ddx], ["+", ["y", "$s"], ddy]]]]],
                   effets]]
    sauter = {"nom": "porteur sélecteur", "phase": 0, "quand": ["=", ["action"], NOMS.get(sel, "")],
              "alors": [["pour", "$m", _objets(m), effets]]}
    # ordre de dessin : la pièce qui porte le marqueur passe au-dessus des autres hôtes DE SA COUCHE (theorie.rendu : tri
    # par (couche de la classe, porteur)) ; chaque hôte garde la couche de sa classe (CCM-189-B : les remettre toutes à 0
    # faisait passer une pièce sous le décor, re86 programme 0,95 → 0,0)
    couche = th.couches()
    alors = []
    for c in hotes:
        de_c = ["filtrer", "$h", ["objets", {}], ["et", piece, _de_couleur("$h", c)]]
        alors.append(["pour", "$h", de_c, [["calque", "$h", couche(c)]]])
        alors.append(["pour", "$m", _objets(m), [["pour", "$h", ["filtrer", "$h", ["a", ["x", "$m"], ["y", "$m"]],
                                                                  ["et", piece, _de_couleur("$h", c)]],
                                                   [["calque", "$h", couche(c) + 0.5]]]]])
    alors.append(["pour", "$m", _objets(m), [["calque", "$m", 10]]])  # le marqueur reste au-dessus de sa pièce (trou de fond)
    calquer = {"nom": "porteur calque", "phase": 2.5, "quand": True, "alors": alors}
    return [noter, suivre, sauter, calquer]


def _fantome(th):
    """theorie._pas_fantome : (1) avant les lois, la position du joueur est notée ; (2) sous la boucle, si le trajet n'est
    pas vide : le fantôme existant s'efface (1 emplacement), sinon une copie du joueur, recolorée, naît au départ avec le
    trajet pour chemin ; le trajet est vidé ; (3) après les lois, sur un pas EFFECTIF du joueur : le pas s'ajoute au
    trajet et chaque fantôme rejoue le pas suivant de son chemin."""
    cj, boucle, cg, x0, y0 = th.fantome
    b = NOMS.get(boucle, boucle)
    fants = ["filtrer", "$g", _objets(cg), ["!=", ["attr", "$g", "chemin"], None]]
    noter = {"nom": "fantôme : position du joueur notée", "phase": -1, "quand": True,
             "alors": [["pour", "$j", _objets(cj), [["poser", "_jx", ["x", "$j"]], ["poser", "_jy", ["y", "$j"]]]]]}
    boucler = {"nom": "fantôme : boucle", "phase": 0.65,
               "quand": ["et", ["=", ["action"], b], [">", ["longueur", ["etat", "trajet"]], 0]],
               "alors": [["si_alors", ["vide", fants],
                          [["pour", "$j", _objets(cj), [["soit_creer", "$n", "$j", x0, y0,
                                                          [["poser_attr", "$n", "chemin", ["etat", "trajet"]],
                                                           ["poser_attr", "$n", "k", 0], ["recolorer", "$n", cj, cg]]]]]],
                          [["pour", "$g", fants, [["retirer", "$g"]]]]],
                         ["poser", "trajet", ["liste"]]]}
    dx, dy = ["-", ["x", "$j"], ["etat", "_jx"]], ["-", ["y", "$j"], ["etat", "_jy"]]
    k, ch = ["attr", "$g", "k"], ["attr", "$g", "chemin"]
    rejouer = {"nom": "fantôme : pas effectif, rejeu", "phase": 0.9, "quand": ["!=", ["action"], b],
               "alors": [["pour", "$j", _objets(cj), [["si_alors", ["non", ["et", ["=", dx, 0], ["=", dy, 0]]],
                          [["empiler", "trajet", ["liste", dx, dy]],
                           ["pour", "$g", fants, [["si_alors", ["<", k, ["longueur", ch]],
                                                   [["deplacer", "$g", ["elem", ["elem", ch, k], 0], ["elem", ["elem", ch, k], 1]],
                                                    ["poser_attr", "$g", "k", ["+", k, 1]]], []]]]], []]]]]}
    return [noter, boucler, rejouer]


def _tenue_cases(th):
    """theorie._tenir_cases : après les lois, si un mobile (joueur, poussable, fantôme) occupe une case de S, les cases R de
    la classe p s'effacent et les cases A apparaissent ; sinon l'inverse. Le langage ne fait pas grandir un sprite : les
    objets d'origine (marqués « base », car un objet tout effacé n'a plus la couleur p) perdent ou regagnent les cases R, et
    les cases A forment un objet à part (« ouverte »), créé une fois par copie d'un objet de la classe, montré ou caché."""
    mob = sorted({c for c, _ in th.moves} | set(th.poussables) | ({th.fantome[2]} if getattr(th, "fantome", None) else set()))
    mobiles = ["+", *[_objets(c) for c in mob]] if len(mob) > 1 else _objets(mob[0]) if mob else ["liste"]
    regles, non = [], []
    for p, r_cases, a_cases, s_cases in th.tenue_cases:
        if not 0 <= p < 16:
            non.append(f"tenue_cases c{p} (classe sans couleur)")
            continue
        cle = f"tenue_c{p}"
        base = ["filtrer", "$b", ["objets", {}], ["=", ["attr", "$b", cle], "base"]]
        ouv = ["filtrer", "$b", ["objets", {}], ["=", ["attr", "$b", cle], "ouverte"]]

        def opaque(v, x, y):
            px = ["pixel", v, ["-", x, ["x", v]], ["-", y, ["y", v]]]
            return ["non", ["ou", ["=", px, None], ["<", px, 0]]]

        def ecrire(x, y, c):
            dx, dy = ["-", x, ["x", "$o"]], ["-", y, ["y", "$o"]]
            return ["si_alors", ["!=", ["pixel", "$o", dx, dy], None], [["ecrire", "$o", dy, dx, c]], []]
        marquer = {"nom": f"tenue_cases c{p} : objets d'origine", "phase": 2.4, "quand": ["vide", base],
                   "alors": [["pour", "$o", _objets(p), [["poser_attr", "$o", cle, "base"]]]]}
        regles.append(marquer)
        if a_cases:
            ax, ay = min(x for x, _ in a_cases), min(y for _, y in a_cases)
            lx, ly = max(x for x, _ in a_cases) - ax + 1, max(y for _, y in a_cases) - ay + 1
            motif = ["liste", *[["liste", *[p if (ax + i, ay + j) in a_cases else -1 for i in range(lx)]]
                                for j in range(ly)]]
            regles.append({"nom": f"tenue_cases c{p} : porte ouverte créée", "phase": 2.45,
                           "quand": ["et", ["vide", ouv], ["non", ["vide", base]]],
                           "alors": [["soit_creer", "$n", ["premier", base], ax, ay,
                                      [["poser_motif", "$n", motif], ["poser_attr", "$n", cle, "ouverte"],
                                       ["montrer", "$n", False]]]]})
        ouverte = ["existe", "$m", mobiles, ["ou", False, *[opaque("$m", x, y) for x, y in sorted(s_cases)]]]
        regles.append({"nom": f"tenue_cases c{p}", "phase": 2.5, "quand": True,
                       "alors": [["pour", "$o", base, [["si_alors", ouverte, [ecrire(x, y, -1) for x, y in sorted(r_cases)],
                                                        [ecrire(x, y, p) for x, y in sorted(r_cases)]]]],
                                 ["pour", "$o", ouv, [["montrer", "$o", ouverte]]]]})
    return regles, non


def _condition_but(b):
    kind = b[0]
    if kind in ("sortie", "sortie_si"):
        c = ["existe", "$j", _objets(b[1]), ["existe", "$k", _objets(b[2]), ["chevauche", "$j", "$k"]]]
        return ["et", c, ["non", ["vide", _objets(b[3])]]] if kind == "sortie_si" else c
    if kind == "ancre":
        return ["existe", "$j", _objets(b[1]), ["existe", "$k", _objets(b[2]),
                                                ["et", ["=", ["x", "$j"], ["x", "$k"]], ["=", ["y", "$j"], ["y", "$k"]]]]]
    if kind == "emboite":  # theorie._vrai : chaque centre (2×) de cible creuse porte le centre d'une pièce, à 1 case près
        pieces = ["+", *[_objets(c) for c in b[2]]] if len(b[2]) > 1 else _objets(b[2][0])
        exige = dict(b[3]) if len(b) > 3 else {}  # CCM-044-G : cible-moule → seule la classe de son objet

        def proche(cx, cy):
            px = ["+", ["*", 2, ["x", "$p"]], ["-", ["largeur", "$p"], 1]]
            py = ["+", ["*", 2, ["y", "$p"]], ["-", ["hauteur", "$p"], 1]]
            libres = [c for c in b[2] if c not in set(exige.values())]  # une classe à moule ne remplit que lui
            ps = _objets(exige[(cx, cy)]) if (cx, cy) in exige else (["+", *[_objets(c) for c in libres]] if len(libres) > 1
                                                                     else _objets(libres[0]) if libres else pieces)
            return ["existe", "$p", ps, ["et", ["<=", ["-", px, cx], 2], ["<=", ["-", cx, px], 2],
                                          ["<=", ["-", py, cy], 2], ["<=", ["-", cy, py], 2]]]
        return ["et", bool(b[1]), *[proche(cx, cy) for cx, cy in b[1]]]
    if kind == "centre":  # theorie._vrai : boîtes en ×2 ; b approché par sa boîte (≤ 2 cases), aire de a ≥ 3 (boîte)
        def proche(axe, dim):
            c2 = ["+", ["*", 2, [axe, "$j"]], ["-", [dim, "$j"], 1]]
            lo, hi = ["*", 2, [axe, "$k"]], ["*", 2, ["+", [axe, "$k"], ["-", [dim, "$k"], 1]]]
            return ["et", ["<=", ["-", lo, c2], 2], ["<=", ["-", c2, hi], 2]]
        return ["existe", "$j", _objets(b[1]), ["et", [">=", ["*", ["largeur", "$j"], ["hauteur", "$j"]], 3],
                ["existe", "$k", _objets(b[2]), ["et", ["!=", "$k", "$j"],
                                                 ["<=", ["*", ["largeur", "$k"], ["hauteur", "$k"]], 2],
                                                 proche("x", "largeur"), proche("y", "hauteur")]]]]
    if kind == "absent":
        return ["vide", _objets(b[1])]
    if kind == "paires":
        return ["et", bool(b[1]), *[_condition_but(("remplir_fam", fam, cible)) for fam, cible in b[1]]]
    if kind in ("remplir", "remplir_fam"):
        famille = (b[1],) if kind == "remplir" else b[1]
        sources = ["filtrer", "$src", ["objets", {}], ["ou", False, *[_de_couleur("$src", c) for c in famille]]]
        return ["et", ["non", ["vide", _objets(b[2])]],
                ["tous", "$k", _objets(b[2]), _couvert("$k", 0, 0, sources)]]
    if kind == "modele":
        return _condition_modele(b[1], b[2])
    if kind == "motif_rel":
        return _condition_motif(b[1], b[2])
    if kind == "copie":  # C (CCM-140-C) : chaque case du motif montre la couleur de la miniature (theorie.copie_ecarts)
        return ["et", *[["=", _couleur_en(x, y), k] for k, cs in b[1] for x, y in cs]]
    if kind == "marques":  # theorie.marques_manquantes == 0 : chaque marque sous une case visible d'une pièce (CCM-035-G)
        def couverte(k, x, y):  # b[2] == "couleur" (CCM-059-E) : le pixel de la pièce sur la marque a sa couleur
            v = "$cv"
            px = ["pixel", v, ["-", x, ["x", v]], ["-", y, ["y", v]]]
            return ["existe", v, ["a", x, y], ["et", [">", ["*", ["largeur", v], ["hauteur", v]], 1],
                                                  ["non", _de_couleur(v, 512)],
                                                  ["=", ["%", px, 16], k] if b[2:3] == ("couleur",) and k >= 0 else [">=", px, 0]]]
        return ["et", True, *[couverte(k, x, y) for k, cs in b[1] for x, y in cs]]
    return None


def _condition_modele(a, b):
    # Normalisation de l'union des pixels opaques, pas de l'identité des sprites.
    def mincoord(c, axe):
        os = _objets(c)
        return [axe, ["argmin", "$mm", os, [axe, "$mm"]]]
    def inclusion(src, dst):
        dx = ["-", mincoord(dst,"x"), mincoord(src,"x")]
        dy = ["-", mincoord(dst,"y"), mincoord(src,"y")]
        return ["tous", "$k", _objets(src), _couvert("$k", dx, dy, _objets(dst))]
    return ["et", ["non", ["vide", _objets(a)]], ["non", ["vide", _objets(b)]], inclusion(a,b), inclusion(b,a)]


def _couleur_en(x, y):
    """Couleur de la case (x, y) de la vue : pixel du sprite le plus haut qui la couvre, -1 sans sprite."""
    s = ["premier", ["a", x, y]]
    return ["si", ["vide", ["a", x, y]], -1, ["pixel", s, ["-", x, ["x", s]], ["-", y, ["y", s]]]]


def _condition_motif(meme, autre):
    """theorie.motif_relatif (CW-228, ft09) : chaque centre (sprite d'une case, hors marques, entouré de 8 marques) ; la
    marque en (dx, dy) désigne la case à 4·(dx, dy) : même couleur que le centre ssi la marque vaut `meme`."""
    from chrysalide.arc3.logique.theorie import VOISINS8
    marques = ["liste", meme, autre]
    x, y, k = ["x", "$z"], ["y", "$z"], ["pixel", "$z", 0, 0]
    centre = ["et", ["=", ["largeur", "$z"], 1], ["=", ["hauteur", "$z"], 1], ["non", ["contient", marques, k]],
              *[["contient", marques, _couleur_en(["+", x, dx], ["+", y, dy])] for dx, dy in VOISINS8]]
    ok = ["et", *[["et", ["!=", _couleur_en(["+", x, 4 * dx], ["+", y, 4 * dy]), -1],
                   ["=", ["=", _couleur_en(["+", x, 4 * dx], ["+", y, 4 * dy]), k],
                    ["=", _couleur_en(["+", x, dx], ["+", y, dy]), meme]]] for dx, dy in VOISINS8]]
    centres = ["filtrer", "$z", ["objets", {}], centre]
    return ["et", ["non", ["vide", centres]], ["tous", "$z", centres, ok]]


def verifier(programme, gid, dossier, actions):
    """Porte indépendante : rejoue `actions` dans le vrai moteur ET dans l'interpréteur de A (scène initiale lue dans le
    moteur, bancs seulement) ; compare les images sans HUD. Arrêt au changement de niveau. → (exactes, total, 1re erreur)."""
    import numpy as np

    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.logique.jeux import environnement, jouer_action
    from chrysalide.arc3.ontologie_exec import scene_initiale_moteur, scene_moteur
    env = environnement(gid, dossier)
    f = env.reset()
    scene, prog = scene_initiale_moteur(env), Programme(programme)
    ok = n = 0
    premiere = None
    for t, a in enumerate(actions):
        n0 = f.levels_completed
        f = jouer_action(env, a)
        if f.levels_completed != n0 or f.state.name in ("WIN", "GAME_OVER"):
            break
        prog.step(scene, (NOMS[a],))
        exact = np.array_equal(np.asarray(scene.image()), scene_moteur(env)[1])
        ok, n = ok + exact, n + 1
        if not exact and premiere is None:
            premiere = t
    return ok, n, premiere
