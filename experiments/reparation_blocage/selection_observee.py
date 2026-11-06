"""Induction de sélection et marqueurs contextuels depuis pixels/clic observés."""

from collections import Counter

import numpy as np
from objets_variables import localiser
from roles_observes import PerceptionRoles

from chrysalide.arc3.moteur import NOMS, MoteurFormel, _composantes, _sprite
from chrysalide.arc3.ontologie_exec import Scene


class SelectionObservee(MoteurFormel):
    def __init__(self, images, actions, optimistes=(), contact="aucun", films=None, clics_negatifs=False, sans_clic=False):
        self.clics_negatifs = clics_negatifs
        self.preuves_clics_negatifs = []
        self.roles_sans_clic = None
        if sans_clic:
            from roles_sans_clic import amorcer
            base,m,(my,mx),inactif,preuve_roles=amorcer(images,actions,films)
            self.roles_sans_clic=preuve_roles
            self.premier_clic_interpretable=None
            self.base=base
            self.fond,self.hud=base.fond,base.hud
            h,w=m.shape
            self.mx,self.my=mx,my
            self.selection=int(m[my,mx])
            self.inactif=self.inactif_apres_selection=inactif
            if films is not None:
                from clics_negatifs import preuve
                repos=set()
                for t,a in enumerate(actions):
                    if not isinstance(a,list):continue
                    p=preuve(images,actions,films,t)
                    if p['inerte']:
                        self.preuves_clics_negatifs.append(p)
                        continue
                    avant,apres=map(np.asarray,(images[t],images[t+1]))
                    _,cx,cy=a
                    if apres[cy,cx]!=self.selection:continue
                    for yy,xx in np.argwhere((avant==self.selection)&(apres!=avant)):
                        y,x=int(yy)-my,int(xx)-mx
                        if x<0 or y<0 or y+h>avant.shape[0] or x+w>avant.shape[1]:continue
                        masque=np.ones(m.shape,bool);masque[my,mx]=False
                        if np.array_equal(avant[y:y+h,x:x+w][masque],m[masque]):
                            repos.add(int(apres[yy,xx]))
                if len(repos)>1:raise ValueError('Attribut au repos contradictoire')
                if repos:
                    self.inactif_apres_selection=repos.pop()
                    self.roles_sans_clic={**preuve_roles,'selection_clic':'observee_sur_prefixe',
                        'marqueur_repos':'observe_apres_clic'}
                self.clics_negatifs=bool(self.preuves_clics_negatifs) or clics_negatifs
        else:
            clics = [i for i, a in enumerate(actions) if isinstance(a, list)]
            if clics_negatifs:
                from clics_negatifs import preuve

                k = None
                for indice in clics:
                    p = preuve(images, actions, films, indice)
                    if p["inerte"]:
                        self.preuves_clics_negatifs.append(p)
                        continue
                    if k is None:
                        k = indice
                if k is None:
                    raise ValueError("Aucun clic interprétable observé : preuves négatives conservées")
            else:
                k = next(iter(clics))
            self.premier_clic_interpretable = k
            base = PerceptionRoles(
                images[: k + 1], actions[:k], clics_negatifs=clics_negatifs, films=films[:k] if films is not None else None
            )
            self.base = base
            self.fond, self.hud = base.fond, base.hud
            m = base.mobiles[0].copy()
            h, w = m.shape
            avant, apres = base.vue(images[k]), base.vue(images[k + 1])
            x, y = localiser(avant, m)
            d = avant[y : y + h, x : x + w] != apres[y : y + h, x : x + w]
            if d.sum() != 1:
                raise ValueError("Un seul marqueur changeant requis")
            my, mx = map(int, np.argwhere(d)[0])
            self.mx, self.my = mx, my
            self.selection = int(m[my, mx])
            self.inactif_apres_selection = int(apres[y + my, x + mx])
            _, cx, cy = actions[k]
            self.inactif = int(avant[cy, cx])
            if int(apres[cy, cx]) != self.selection:
                raise ValueError("Le clic ne sélectionne pas le marqueur attendu")
        self.motif = m
        self.coque = m.copy()
        self.coque[my, mx] = -1
        self.pos = [self.positions(base.vue(g)) for g in images]
        if any(len(p) != len(self.pos[0]) for p in self.pos):
            raise ValueError("Cardinalité de coques variable")
        self.decor = base.decor.copy()
        sols = Counter(v for p in base.preuves_decor for _, v in p["vues"])
        if not sols:
            raise ValueError("Pas de sol révélé")
        sol = sols.most_common(1)[0][0]
        self.inconnus = []
        occs = []
        for ps in self.pos:
            occ = np.zeros((64, 64), bool)
            for xx, yy in ps:
                occ[yy : yy + h, xx : xx + w] = True
            occs.append(occ)
        for yy, xx in np.argwhere(occs[0]):
            vus = {int(g[yy, xx]) for t, g in enumerate(images) if not occs[t][yy, xx]}
            if len(vus) == 1:
                self.decor[yy, xx] = next(iter(vus))
            elif not vus:
                self.decor[yy, xx] = sol
                self.inconnus.append([int(yy), int(xx)])
            else:
                raise ValueError("Décor variable hors coque")
        self.statiques = [_sprite(o) for o in _composantes(self.decor, self.fond)]
        fond = np.where(self.decor == self.fond, self.fond, -1).astype(np.int16)
        self.statiques.append({"pixels": fond, "x": 0, "y": 0, "couche": 0})
        self.cibles = []
        for s in self.statiques:
            if s["pixels"].shape != (h, w) or not np.all(s["pixels"] >= 0):
                continue
            xx, yy = s["x"], s["y"]
            if xx < 1 or yy < 1 or xx + w >= 64 or yy + h >= 64:
                continue
            bord = self.decor[yy - 1 : yy + h + 1, xx - 1 : xx + w + 1]
            perimetre = np.concatenate([bord[0], bord[-1], bord[1:-1, 0], bord[1:-1, -1]])
            if len(set(perimetre.tolist())) == 1:
                self.cibles.append((xx, yy, int(perimetre[0])))
        if not self.cibles:
            raise ValueError("Pas de contours fermés correspondant aux pièces")
        self.libres = set()
        for t, a in enumerate(actions):
            if not isinstance(a, int):
                continue
            anciens = set(self.pos[t])
            nouveaux = set(self.pos[t + 1]) - anciens
            for xx, yy in nouveaux:
                if images[t + 1][yy + my, xx + mx] != self.selection:
                    continue  # Un passage passif ne prouve pas un passage commandé.
                self.libres.update(self.decor[yy : yy + h, xx : xx + w].ravel().tolist())
        if contact not in ("aucun", "pas", "glisse", "sortie"):
            raise ValueError("Contact inconnu")
        self.contact = contact
        self.optimistes = set(optimistes)
        self.incertains = set(np.unique(self.decor).tolist()) - self.libres - {self.fond}
        self.mouvements = {a: d for a, d in base.mouvements[0].items() if a != 6} if clics_negatifs else base.mouvements[0]
        self.sorties = set()
        self.preuves_sortie = []
        if films is not None:
            for t, film in enumerate(films):
                if len(film) < 3:
                    continue
                positions = [set(self.positions(g)) for g in film]
                fixes = set.intersection(*positions)
                mobiles = [list(ps - fixes) for ps in positions]
                chemin = []
                for ps in mobiles:
                    if len(ps) == 1 and (not chemin or chemin[-1] != ps[0]):
                        chemin.append(ps[0])
                if len(chemin) < 2:
                    continue
                xp, yp = chemin[-2]
                xf, yf = chemin[-1]
                dx, dy = xf - xp, yf - yp
                xn, yn = xf + dx, yf + dy
                if not (0 <= xn <= 64 - w and 0 <= yn <= 64 - h):
                    continue
                suivant = self.decor[yn : yn + h, xn : xn + w]
                if self.fond in suivant or (xn, yn) in fixes:
                    continue
                precedent = set(self.decor[yp : yp + h, xp : xp + w].ravel().tolist())
                final = set(self.decor[yf : yf + h, xf : xf + w].ravel().tolist())
                candidates = precedent - final - self.libres - {self.fond}
                if candidates:
                    self.sorties.update(candidates)
                    self.preuves_sortie.append(
                        {"coup": t + 1, "avant": list(chemin[-2]), "apres": list(chemin[-1]), "surfaces": sorted(candidates)}
                    )

        self.faces = []
        for dx, dy in self.mouvements.values():
            face = [(yy, 0 if dx < 0 else w - 1) for yy in range(h)] if dx else [(0 if dy < 0 else h - 1, xx) for xx in range(w)]
            valeurs = []
            for g, ps in zip(images, self.pos):
                for xx, yy in ps:
                    if g[yy + my, xx + mx] != self.selection or (xx + dx, yy + dy) not in ps:
                        continue
                    changements = [int(g[yy + iy, xx + ix]) for iy, ix in face if g[yy + iy, xx + ix] != self.coque[iy, ix]]
                    if len(changements) == len(face) and len(set(changements)) == 1:
                        valeurs.extend(changements)
            if valeurs:
                self.faces.append((dx, dy, face, valeurs[0]))

    def positions(self, g):
        h, w = self.coque.shape
        fen = np.lib.stride_tricks.sliding_window_view(g, (h, w))
        mask = self.coque >= 0
        erreurs = (fen[..., mask] != self.coque[mask]).sum(axis=-1)
        marqueurs = np.isin(fen[..., self.my, self.mx], [self.selection, self.inactif, self.inactif_apres_selection])
        yy, xx = np.nonzero((erreurs <= max(h, w)) & marqueurs)
        retenus = []
        for _, y, x in sorted((int(erreurs[y, x]), int(y), int(x)) for y, x in zip(yy, xx)):
            if not any(abs(x - a) < w and abs(y - b) < h for a, b in retenus):
                retenus.append((x, y))
        return sorted(retenus)

    def vue(self, g):
        return self.base.vue(g)

    def signature_observation(self):
        return {
            "methode": "coques_selection_observee",
            **({"roles_sans_clic": self.roles_sans_clic} if getattr(self,"roles_sans_clic",None) else {}),
            **(
                {
                    "premier_clic_interpretable": self.premier_clic_interpretable,
                    "preuves_clics_negatifs": self.preuves_clics_negatifs,
                    "clic_hors_piece": "hypothese_sans_effet_validee_sur_prefixe",
                }
                if self.clics_negatifs
                else {}
            ),
            "decor": self.decor.tolist(),
            "coque": self.coque.tolist(),
            "selection": self.selection,
            "inactif": self.inactif,
            "inactif_apres_selection": self.inactif_apres_selection,
            "cibles": self.cibles,
            "sorties_hypothetiques": sorted(self.sorties),
            "preuves_sortie": self.preuves_sortie,
            "faces_contact": self.faces,
            "contact": self.contact,
            "sols_hypothetiques": self.inconnus,
            "libres": sorted(self.libres),
            "optimistes": sorted(self.optimistes),
        }

    def scene(self, g):
        a = self.vue(g)
        sprites = []
        for s in self.statiques:
            couleurs = set(np.unique(s["pixels"]).tolist()) - {-1}
            sprites.append(
                {
                    **s,
                    "pixels": s["pixels"].copy(),
                    "tags": ["decor"]
                    if couleurs <= (self.libres | self.optimistes)
                    else (["bloqueur", "mur"] if self.fond in couleurs else ["bloqueur"]),
                }
            )
        for s in sprites:
            if set(np.unique(s["pixels"]).tolist()) & self.sorties:
                s["tags"].append("frein")
        h, w = self.coque.shape
        for xx, yy in self.positions(a):
            sprites.append(
                {
                    "x": xx,
                    "y": yy,
                    "pixels": a[yy : yy + h, xx : xx + w].copy(),
                    "couche": 1,
                    "tags": ["piece"],
                    "attrs": {
                        "marqueur_repos": self.inactif_apres_selection
                        if a[yy + self.my, xx + self.mx] == self.selection
                        else int(a[yy + self.my, xx + self.mx])
                    },
                }
            )
        for xx, yy, _ in self.cibles:
            sprites.append(
                {"x": xx, "y": yy, "pixels": self.decor[yy : yy + h, xx : xx + w].copy(), "couche": 0, "tags": ["cible"]}
            )
        return Scene(a.shape, self.fond, self.fond, sprites)

    def programme(self):
        pieces = ["objets", {"tag": "piece"}]
        cibles = ["objets", {"tag": "cible"}]

        def sur(o, t):
            return ["et", ["=", ["x", o], ["x", t]], ["=", ["y", o], ["y", t]]]

        def marque(o):
            return ["pixel", o, self.mx, self.my]

        def ecrit(v):
            return ["ecrire", "$o", self.my, self.mx, v]

        actif = ["=", marque("$o"), self.selection]
        regles = []
        from faces_contact import regles_faces
        rendu_faces = regles_faces(self.coque, self.faces, pieces, actif)
        regles.extend(rendu_faces[:1])
        h, w = self.coque.shape
        for action, (dx, dy) in self.mouvements.items():
            libre = [
                "et",
                ["libre", "$o", dx, dy, {"tag": "bloqueur"}],
                ["libre", "$o", dx, dy, {"tag": "piece"}],
                [">=", ["+", ["x", "$o"], dx], 0],
                ["<=", ["+", ["x", "$o"], dx + w], 64],
                [">=", ["+", ["y", "$o"], dy], 0],
                ["<=", ["+", ["y", "$o"], dy + h], 64],
            ]
            effets = [["poser_attr", "$o", "contact_avant", ["non", ["libre", "$o", dx, dy, {"tag": "piece"}]]]]
            if self.contact != "aucun":
                voisin = [
                    "et",
                    ["!=", "$o", "$p"],
                    ["=", ["x", "$p"], ["+", ["x", "$o"], dx]],
                    ["=", ["y", "$p"], ["+", ["y", "$o"], dy]],
                ]
                place = [
                    "et",
                    ["libre", "$p", dx, dy, {"tag": "mur"}],
                    ["libre", "$p", dx, dy, {"tag": "piece"}],
                    [">=", ["+", ["x", "$p"], dx], 0],
                    ["<=", ["+", ["x", "$p"], dx + w], 64],
                    [">=", ["+", ["y", "$p"], dy], 0],
                    ["<=", ["+", ["y", "$p"], dy + h], 64],
                ]
                avance = (
                    ["si_alors", place, [["deplacer", "$p", dx, dy]], []]
                    if self.contact == "pas"
                    else ["tant_que", place, [["deplacer", "$p", dx, dy]], 64]
                )
                if self.contact == "sortie":
                    avance = [
                        "tant_que",
                        [
                            "et",
                            place,
                            ["non", ["et", ["attr", "$p", "surface_traversee"], ["libre", "$p", 0, 0, {"tag": "frein"}]]],
                        ],
                        [
                            ["deplacer", "$p", dx, dy],
                            [
                                "si_alors",
                                ["non", ["libre", "$p", 0, 0, {"tag": "frein"}]],
                                [["poser_attr", "$p", "surface_traversee", True]],
                                [],
                            ],
                        ],
                        64,
                    ]
                effets.append(
                    [
                        "si_alors",
                        ["et", actif, ["libre", "$o", dx, dy, {"tag": "bloqueur"}]],
                        [
                            [
                                "pour",
                                "$p",
                                pieces,
                                [["si_alors", voisin, [["poser_attr", "$p", "surface_traversee", False], avance], []]],
                            ]
                        ],
                        [],
                    ]
                )
            effets.append(
                ["si_alors", ["et", actif, libre, ["non", ["attr", "$o", "contact_avant"]]], [["deplacer", "$o", dx, dy]], []]
            )
            regles.append(
                {
                    "nom": f"mouvement_{action}",
                    "quand": ["=", ["action"], NOMS[action]],
                    "phase": 0,
                    "alors": [["pour", "$o", pieces, effets]],
                }
            )
        cx = ["elem", ["case_clic"], 0]
        cy = ["elem", ["case_clic"], 1]
        touche = [
            "et",
            [">=", cx, ["x", "$o"]],
            ["<", cx, ["+", ["x", "$o"], w]],
            [">=", cy, ["y", "$o"]],
            ["<", cy, ["+", ["y", "$o"], h]],
        ]
        regles.append(
            {
                "nom": "selection_observee",
                "phase": 0,
                "quand": ["=", ["action"], "MOUSE"],
                "alors": [
                    [
                        "pour",
                        "$o",
                        pieces,
                        [ecrit(["si", touche, self.selection, ["si", actif, self.inactif_apres_selection, marque("$o")]])],
                    ]
                ],
            }
        )
        regles.extend(rendu_faces[1:])

        regles.append(
            {
                "nom": "toutes_cibles_hypothese",
                "phase": 2,
                "quand": ["tous", "$t", cibles, ["existe", "$o", pieces, sur("$o", "$t")]],
                "alors": [["niveau_suivant"]],
            }
        )
        if self.clics_negatifs and self.preuves_clics_negatifs:
            for regle in regles:
                if regle["nom"] == "selection_observee":
                    regle["quand"] = ["et", regle["quand"], ["existe", "$o", pieces, touche]]
        return {"mode": "lois", "etat": {}, "regles": regles}
