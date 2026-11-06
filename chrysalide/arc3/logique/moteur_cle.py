# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — `MoteurCle` : la boucle « clé, porte, jauge » (`ressource.py`) derrière l'interface `MoteurFormel`
(CW-145). Essaie d'abord la chaîne standard de `MoteurC` ; si elle refuse et qu'un niveau réussi a appris des rôles
(indicateur transformé par un modificateur, porte, jauge), propose le plan à ressource.
PORTE : ce monde (jauge, rotation du dessin, recharges) n'est pas exportable dans le langage de A ; `programme` vaut
alors None et le moteur déclare `porte_propre = True` avec, dans `infos`, ses deux portes à lui (plus faibles, à compter
à part) : porte1_c = toutes les positions du mobile observées dans ce niveau sont prédites par le modèle (après
réinduction) ; porte2_c = le plan finit sur la porte, dessin accordé, jauge > 0, dans le modèle ;
chemin_sans_surprise_c (CW-177.1) = aucune surprise inexpliquée du niveau ne tombe sur le chemin du plan. Aucun accès au jeu."""
from copy import deepcopy

from chrysalide.arc3.logique import ressource
from chrysalide.arc3.moteur import NOMS, MoteurC
from chrysalide.arc3.moteur import _codes_c as _codes


def _segments(p):
    acts, fin = _codes(p["lots"]), _codes([p["finale"]])
    if acts is None or fin is None:
        return None
    return {"grilles": list(p["grilles"]), "actions": acts, "finale": fin[0], "issue": "niveau"}


MAX_APPRENTISSAGE = 150  # transitions du niveau réussi gardées pour apprendre les rôles (la fin, gagnante)


class MoteurCle(MoteurC):
    porte_propre = True

    def __init__(self, budget=None, limite_plan=50000):
        super().__init__(budget, limite_plan)
        self._roles = {}  # clé : nombre de niveaux réussis → (Roles | None, raison)
        self._carnets = {}  # clé : nombre de niveaux réussis → Carnet relu sur les niveaux réussis (coût CPU, CCM-153-A)

    def roles(self, precedents):
        k = len(precedents)
        if k not in self._roles:
            segs = [_segments(p) for p in precedents[:1]]
            if segs and segs[0] is not None and len(segs[0]["actions"]) > MAX_APPRENTISSAGE:  # coût : on garde la fin
                s0 = segs[0]  # du niveau réussi (celle qui mène à la victoire)
                segs = [{**s0, "grilles": s0["grilles"][-MAX_APPRENTISSAGE - 1:], "actions": s0["actions"][-MAX_APPRENTISSAGE:]}]
            self._roles[k] = (None, "niveau réussi illisible") if not segs or None in segs else ressource.apprendre(segs)
        return self._roles[k]

    def _proposer(self, h, t0, b):
        roles, raison = self.roles(h["precedents"]) if h.get("precedents") else (None, "aucun niveau réussi")
        if roles is None:  # pas de monde « clé, porte, jauge » appris : la chaîne standard de MoteurC
            self.infos["refus_cle"] = raison
            return super()._proposer(h, t0, b)
        # rôles appris : la boucle à ressource joue seule (la chaîne standard réinduisait tous les niveaux réussis à
        # chaque appel, pour un refus « ne rejoue pas » : 22 min de CPU sur 60 dans E2E4, CCM-153-A)
        acts = _codes(h["lots"])
        if not h["lots"] or acts is None:
            self.infos["refus"] = "aucune transition" if not h["lots"] else "lot illisible"
            return None
        k = len(h["precedents"])
        if k not in self._carnets:
            carnet = ressource.Carnet()
            for p in h["precedents"][1:]:  # mémoire portée : recharges, sens, gabarit relus sur les niveaux réussis
                s = _segments(p)
                if s is not None:
                    ressource.lire_niveau(roles, carnet, s["grilles"], s["actions"])
            self._carnets[k] = carnet
        carnet = deepcopy(self._carnets[k])  # relu UNE fois par niveau ; copie : proposer le met à jour
        plan, inf = ressource.proposer(roles, carnet, h["grilles"], acts, limite=self.limite_plan * 8)
        self.infos.update({f"cle_{k}": v for k, v in inf.items() if not k.startswith("_")})
        self.infos["porte1_c"] = inf.get("surprises_restantes", 1) == 0
        self.infos["porte2_c"] = inf.get("mode") == "ressource"
        if plan and inf.get("_th") is not None:  # CW-177.1 : aucune surprise inexpliquée du niveau sur le chemin du plan
            mob = inf["_prevu"][0]
            chemin = [None if mob is None else (mob[2], mob[3]), *ressource.prevoir(inf, plan)]
            pas = {(chemin[i], a) for i, a in enumerate(plan)} | set(chemin)
            self.infos["chemin_sans_surprise_c"] = not any((q, a) in pas or q in pas or vu in pas
                                                           for q, a, _, vu in inf.get("_surprises", []))
        if not plan:
            self.infos["sans_but"] = True
            return None
        return [{"action": NOMS[a]} for a in plan], None
