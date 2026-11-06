"""Tableau des interactions à la OPINE-World (déterministe, sans LLM).

Une entrée = (objet_ou_type, action, contexte) → essais, effets observés, coût pour atteindre/tester (calculé à la
demande par l'explorateur). Les hypothèses compatibles sont les effets observés : une entrée cohérente prédit son effet
unique ; une entrée incohérente (effets différents dans des contextes apparemment identiques) signale un contexte
oublié, un état caché ou une mauvaise segmentation, et devient une expérience de catégorie (b).
"""
from collections import Counter

# utilité pour la décision, par statut (avant division par le coût)
U_JAMAIS = 1.0          # (a) jamais essayée
U_INCOHERENT = 0.6      # (b) effets mal expliqués
U_GENERALISE = 0.25     # jamais essayée dans ce contexte, mais cohérente dans d'autres contextes
U_CONNU_EFFET = 0.08    # cohérente avec effet : peu d'information
U_CONNU_RIEN = 0.01     # cohérente sans effet
U_MORT = -5.0           # a déjà tué : jamais comme expérience


class Interaction:
    __slots__ = ('cle', 'essais', 'effets', 'epoque')

    def __init__(self, cle):
        self.cle = cle; self.essais = 0; self.effets = Counter(); self.epoque = 0

    def resume(self):
        return dict(cle=str(self.cle), essais=self.essais, effets={str(k): v for k, v in self.effets.items()})


class Table:
    def __init__(self):
        self.e = {}; self.epoque = 0     # incrémentée quand un effet de bord change le monde (état caché possible)

    def noter(self, cles, effet):
        """Note l'effet sous plusieurs clés (abstractions concurrentes, contextes plus ou moins fins)."""
        for c in cles:
            it = self.e.get(c)
            if it is None:
                it = self.e[c] = Interaction(c)
            it.essais += 1; it.effets[effet] += 1; it.epoque = self.epoque

    def statut(self, cle):
        it = self.e.get(cle)
        if it is None or it.essais == 0:
            return 'jamais', None
        if len(it.effets) == 1:
            return 'coherent', next(iter(it.effets))
        return 'incoherent', it.effets.most_common(1)[0][0]

    def utilite(self, cles, rien=('rien',), mort=('mort',), u_gen=U_GENERALISE):
        """cles : du plus spécifique au plus général. Rend (utilité, catégorie, effet prédit)."""
        st0, ef0 = self.statut(cles[0])
        if st0 == 'jamais':
            for c in cles[1:]:
                st, ef = self.statut(c)
                if st == 'coherent':
                    if ef in mort:
                        return U_MORT, 'predit_mort', ef
                    return (u_gen * (0.3 if ef in rien else 1.0)), 'a_generalise', ef
                if st == 'incoherent':
                    return 0.35, 'a_jamais', ef      # le niveau général est incohérent : l'objet précis reste à tester
            return U_JAMAIS, 'a_jamais', None
        it = self.e[cles[0]]
        if any(m in it.effets for m in mort):
            return U_MORT, 'predit_mort', ef0
        if st0 == 'incoherent':
            dom = it.effets.most_common(1)[0][1] / it.essais
            if it.essais < 6 and not (it.essais >= 4 and dom >= 0.75):
                return U_INCOHERENT / (1 + 0.5 * it.essais), 'b_incoherent', ef0
            # incohérence résiduelle (bruit, animation) ou assez testée : on prédit l'effet dominant
        if ef0 in rien:
            gen = self.e.get(cles[-1], it)
            if gen.epoque < self.epoque and st0 == 'coherent':
                return 0.3, 'b_contexte_change', ef0    # bloqué/sans effet avant un changement du monde : re-tester
            return U_CONNU_RIEN / it.essais, 'connu_rien', ef0
        return U_CONNU_EFFET / it.essais, 'connu_effet', ef0

    def fusionner(self, autre):
        for c, it in autre.e.items():
            mine = self.e.get(c)
            if mine is None:
                mine = self.e[c] = Interaction(c)
            mine.essais += it.essais; mine.effets.update(it.effets)

    def __len__(self):
        return len(self.e)

    def bilan(self):
        n_inc = sum(1 for it in self.e.values() if len(it.effets) > 1)
        n_eff = sum(1 for it in self.e.values() if any(k not in ('rien',) for k in it.effets))
        return dict(interactions=len(self.e), avec_effet=n_eff, incoherentes=n_inc)
