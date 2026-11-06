# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — la perception comme hypothèse (CW-072, à la manière d'ARGA et de l'Apperception Engine) :
plusieurs découpages concurrents de la même image ; on garde celui sous lequel la théorie induite explique le plus de
transitions d'apprentissage REJOUÉES exactement (juge CW-065.1), puis le moins d'inexpliquées, puis le découpage le plus simple (ordre de ABSTRACTIONS : « cases » décrit chaque image avec bien plus
d'objets, il ne l'emporte que s'il explique strictement plus de transitions). Découpages : « composantes » (4-connexes par couleur, couleurs qui fusionnent
par mouvement redécoupées), « cases_fond » (chaque case colorée est un objet, le fond n'en est pas un) et « cases »
(chaque case est un objet, fond compris)."""
from chrysalide.arc3.logique.faits import Trajectoire, echelle_candidats
from chrysalide.arc3.logique.induction import induire, precedent_pile

TOUTES = frozenset(range(16))
# (couleurs découpées en cases, sans fond), du plus simple au plus détaillé
ABSTRACTIONS = {"composantes": (None, False), "cases_fond": (TOUTES, False), "cases": (TOUTES, True)}


_CACHE = {}


def _traj(s, atom, sans_fond, ech=None):
    """Trajectoire mise en cache (l'agent réinduit souvent sur les mêmes segments)."""
    cle = (id(s["grilles"]), len(s["grilles"]), atom, sans_fond, ech)
    if cle not in _CACHE:
        if len(_CACHE) > 5000:
            _CACHE.clear()
        _CACHE[cle] = (s["grilles"], Trajectoire(s["grilles"], s["actions"], atomiques=atom, sans_fond=sans_fond, ech=ech))
    return _CACHE[cle][1]


def _temporelles(decoupages=False):
    from chrysalide.arc3.logique.temps import traj_temps  # import tardif : le Pisteur de A n'est utile qu'ici
    out = {"temps": lambda s: traj_temps(s["grilles"], s["actions"]),
           "temps_grille": lambda s: traj_temps(s["grilles"], s["actions"], grille=True)}
    if decoupages:  # découpages concurrents du Pisteur (CCM-047-C) : aucune règle fixe ne gagne, le rejeu tranche
        for opt in ("englobe", "contact"):
            out[f"temps+{opt}"] = lambda s, o=opt: traj_temps(s["grilles"], s["actions"], **{o: True})
            out[f"temps_grille+{opt}"] = lambda s, o=opt: traj_temps(s["grilles"], s["actions"], grille=True, **{o: True})
    return out


def rejeu_apprentissage(th, sources):
    """Juge (CW-065.1) : part des transitions d'apprentissage que la théorie REJOUE exactement (recalée à chaque pas).
    Les « explications » de façade (poursuivant inventé…) ne rejouent rien : elles perdent ici."""
    ok = n = 0
    for tr, ts, *_ in sources:
        for t in (range(len(tr.actions)) if ts is None else ts):
            n += 1
            ok += th.pas(tr.etats[t], tr.actions[t], tr.taille,
                         precedent=precedent_pile(tr.etats, tr.actions, t, th.annule))[0] == tr.etats[t + 1]
    return ok / n if n else 0.0


def induire_abstraction(segments, ts=None, temporelles=False, echelles=False, decoupages=False, **kw):
    """segments = [{grilles, actions, finale, issue}] (format de jeux.segments). Renvoie (nom, Theorie, infos, sources)
    pour le meilleur découpage ; infos['candidats'] = {nom: [inexpliquées, règles, part rejouée]}. « cases » : aucun fond."""
    res, couts = None, {}
    variantes = [(nom, atom, sf, None) for nom, (atom, sf) in ABSTRACTIONS.items()]
    if echelles and segments:  # échelles candidates en concurrence (la 1ʳᵉ est celle par défaut)
        for e in echelle_candidats(segments[0]["grilles"])[1:]:
            variantes += [(f"{nom}@{e[0]}", atom, sf, e) for nom, (atom, sf) in ABSTRACTIONS.items()]
    for rang, (nom, atom, sans_fond, ech) in enumerate(variantes):
        sources = [(_traj(s, atom, sans_fond, ech), ts, s["finale"], s["issue"])
                   for s in segments if s["actions"]]
        if not sources:
            continue
        th, inf = induire(sources, **kw)
        cle = (-round(rejeu_apprentissage(th, sources), 3), inf["cout"][0] if inf["cout"] else 10**9, rang)
        couts[nom] = [cle[1], th.n_regles(), -cle[0]]
        if res is None or cle < res[0]:
            res = (cle, nom, th, inf, sources)
    if temporelles:  # perception TEMPORELLE de A (sans oracle), en pixels et sur la vraie grille, plus détaillées
        for rang, (nom, fab) in enumerate(_temporelles(decoupages).items(), start=len(variantes)):
            sources = [(fab(s), ts, s["finale"], s["issue"]) for s in segments if s["actions"]]
            if not sources:
                continue
            th, inf = induire(sources, **kw)
            th.hors_jeu = sources[0][0].exclues
            cle = (-round(rejeu_apprentissage(th, sources), 3), inf["cout"][0] if inf["cout"] else 10**9, rang)
            couts[nom] = [cle[1], th.n_regles(), -cle[0]]
            if res is None or cle < res[0]:
                res = (cle, nom, th, inf, sources)
    if res is None:
        return None
    _, nom, th, inf, sources = res
    inf["candidats"] = couts
    inf["sans_fond"] = ABSTRACTIONS[nom.split("@")[0]][1] if nom.split("@")[0] in ABSTRACTIONS else True
    return nom, th, inf, sources
