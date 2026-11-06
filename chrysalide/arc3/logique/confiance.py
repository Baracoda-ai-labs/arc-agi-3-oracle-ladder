# SPDX-License-Identifier: MIT-0
"""C (CW-401, variante « relève conditionnelle », avec D) : PORTE DE CONFIANCE. Le moteur ne prend la main au début du
niveau qui suit une victoire de Franzen que si (1) sa théorie prédit SANS ERREUR les K dernières transitions observées
(recalées, image par image, cases exclues masquées) et (2) son plan est plus court qu'une borne. Toute divergence ensuite
rend la main à Franzen (garde de D). Fonctions pures, sans état ; le branchement est chez D (`garde.py`)."""
import os

from chrysalide.arc3.logique.theorie import egal


def porte(th, tr, k=10):
    """→ {"ouverte": bool, "justes": n, "vues": m, "premiere_fausse": t ou None} sur les k dernières transitions de tr
    (moins si la trajectoire est plus courte). Ouverte seulement si les k sont justes et qu'il y en a au moins k."""
    n = len(tr.actions)
    debut = max(0, n - k)
    justes, premiere = 0, None
    for t in range(debut, n):
        pred = th.rendu(th.pas(tr.etats[t], tr.actions[t], tr.taille)[0], tr.taille, tr.fond)
        if egal(pred, tr.cases[t + 1], tr.exclues):
            justes += 1
        elif premiere is None:
            premiere = t
    vues = n - debut
    return {"ouverte": vues >= k and justes == vues, "justes": justes, "vues": vues, "premiere_fausse": premiere}


def borne_plan(plan, coups_franzen_niveau_precedent, reserve=None, facteur=None):
    """Le plan du moteur n'est joué que s'il est STRICTEMENT plus court que `facteur` × les coups de Franzen au niveau
    qu'il vient de gagner (la décomposition CCM-191-B : le gain est dans la longueur), et, si la réserve est connue (F),
    s'il tient dans la réserve. → bool. D (CCM-308-C : les niveaux s'allongent, 0,8 × le niveau PRÉCÉDENT refuse des plans
    gagnants) : `facteur` par défaut = CHRYS_RELEVE_BORNE (0,8 si absent) ; 0 = réserve seule."""
    if not plan:
        return False
    if reserve is not None and len(plan) > reserve:
        return False
    if facteur is None:
        try:
            facteur = float(os.environ.get("CHRYS_RELEVE_BORNE", "0.8"))
        except ValueError:
            facteur = 0.8
    return facteur <= 0 or len(plan) < facteur * coups_franzen_niveau_precedent
