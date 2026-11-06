"""Petites hypothèses concurrentes de freinage induites des trajectoires visibles."""

import copy
import numpy as np

from selection_observee import SelectionObservee


class FreinagePassif(SelectionObservee):
    def __init__(self, images, actions, films, surface, mode, delai=1, clics_negatifs=False, sans_clic=False):
        super().__init__(images, actions, contact="sortie", films=films, clics_negatifs=clics_negatifs, sans_clic=sans_clic)
        self.sorties = {int(surface)}
        self.mode_frein = mode
        self.delai_frein = int(delai)

    def signature_observation(self):
        return {
            **super().signature_observation(),
            "freinage_candidat": {
                "mode": self.mode_frein,
                "surface": sorted(self.sorties),
                "delai": self.delai_frein,
                "portee": "hypothese de mouvement passif, issue inconnue",
            },
        }

    def programme(self):
        p = copy.deepcopy(super().programme())

        def rewrite(x):
            if not isinstance(x, list):
                return x
            if x and x[0] == "tant_que":
                place = x[1][1]
                traversed = ["attr", "$p", "surface_traversee"]
                outside = ["libre", "$p", 0, 0, {"tag": "frein"}]
                if self.mode_frein == "entree":
                    condition = ["non", traversed]
                    body = x[2]
                else:
                    condition = ["<", ["attr", "$p", "pas_depuis_sortie"], self.delai_frein]
                    body = x[2] + [
                        [
                            "si_alors",
                            ["et", traversed, outside],
                            [["poser_attr", "$p", "pas_depuis_sortie", ["+", ["attr", "$p", "pas_depuis_sortie"], 1]]],
                            [],
                        ]
                    ]
                return ["tant_que", ["et", place, condition], body, 64]
            result = [rewrite(y) for y in x]
            # Initialiser le compteur au même endroit que la mémoire de la traversée.
            if result and isinstance(result[0], list) and result[0] == ["poser_attr", "$p", "surface_traversee", False]:
                result.insert(1, ["poser_attr", "$p", "pas_depuis_sortie", 0])
            return result

        for rule in p["regles"]:
            if rule["nom"].startswith("mouvement_"):
                rule["alors"] = rewrite(rule["alors"])
        return p


def _candidats(images, actions, films, clics_negatifs=False, sans_clic=False):
    """Chaque candidat provient d'une glissade passive ; aucune cible/règle fournie."""
    if sans_clic:
        films = [np.asarray(f) for f in films]
    base = SelectionObservee(images, actions, films=films, clics_negatifs=clics_negatifs, sans_clic=sans_clic)
    h, w = base.coque.shape
    specs = set()
    for action, film in zip(actions, films):
        if not isinstance(action, int) or len(film) < 3:
            continue
        ps = [set(base.positions(g)) for g in film]
        fixed = set.intersection(*ps)
        moving = [list(s - fixed) for s in ps]
        path = []
        for points in moving:
            if len(points) == 1 and (not path or path[-1] != points[0]):
                path.append(points[0])
        if len(path) < 3:
            continue
        # Le marqueur commandé reste fixe : cette trajectoire ne vient pas du déplacement actif.
        if not any(int(film[0][y + base.my, x + base.mx]) == base.selection for x, y in fixed):
            continue
        surfaces = [set(map(int, base.decor[y : y + h, x : x + w].ravel())) for x, y in path]
        for color in surfaces[-1] - surfaces[-2] - {base.fond}:
            specs.add((color, "entree", 1))
        for color in set.union(*surfaces[:-1]) - surfaces[-1] - {base.fond}:
            last = max(i for i, s in enumerate(surfaces) if color in s)
            delay = len(path) - 1 - last
            if 1 <= delay <= 3:
                specs.add((color, "sortie_retardee", delay))
    return [
        (
            f"frein_{mode}_{color}_{delay}",
            FreinagePassif(images, actions, films, color, mode, delay, clics_negatifs=clics_negatifs, sans_clic=sans_clic),
        )
        for color, mode, delay in sorted(specs)
    ]


def candidats(images, actions, films, clics_negatifs=False, sans_clic=False):
    if not sans_clic:
        return _candidats(images,actions,films,clics_negatifs=clics_negatifs)
    resultat=[]
    if any(isinstance(a,list) for a in actions):
        try:
            resultat=_candidats(images,actions,films,clics_negatifs=clics_negatifs)
        except (ValueError,StopIteration):
            pass
    try:
        resultat += [(nom+'_roles',vue) for nom,vue in
                     _candidats(images,actions,films,clics_negatifs=clics_negatifs,sans_clic=True)]
    except (ValueError,StopIteration):
        if not resultat:raise
    # Deux amorces peuvent mener au même exécutable et à la même perception.
    # La preuve de clic/mouvement reste provenance, elle ne crée pas un modèle distinct.
    from chrysalide.arc3.logique.plan_langage import _gel
    uniques={}
    for nom,vue in resultat:
        scene=vue.scene(images[0])
        signature=vue.signature_observation().copy()
        for champ in ('roles_sans_clic','premier_clic_interpretable','preuves_clics_negatifs',
                      'clic_hors_piece','preuves_sortie','sols_hypothetiques'):
            signature.pop(champ,None)
        cle=repr(_gel((vue.programme(),signature,scene.sprites,scene.camera,
                       getattr(scene,'canevas',None),vue.vue(images[0]),sorted(vue.hud))))
        if cle not in uniques:
            uniques[cle]=(nom,vue)
        else:
            retenue=uniques[cle][1]
            retenue.amorces_equivalentes=getattr(retenue,'amorces_equivalentes',[])+[vue.signature_observation()]
    return list(uniques.values())
