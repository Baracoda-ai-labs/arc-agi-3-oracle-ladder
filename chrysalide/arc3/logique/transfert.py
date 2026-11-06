# SPDX-License-Identifier: MIT-0
"""D (CW-234) — transfert d'une théorie d'un niveau au suivant quand les COULEURS changent (ft09 N3 : la bascule
8↔9 dans une zone 4 devient 8↔12, le cadre change de couleur). Ce qui persiste = les mécaniques ; ce qui se réinitialise =
les couleurs (comme les positions). Les couleurs de la théorie absentes du niveau courant sont renommées vers les couleurs
NOUVELLES du niveau (présentes maintenant, inconnues de la théorie) ; toutes les correspondances injectives sont essayées
(au plus MAX_ESSAIS) et la meilleure au rejeu du niveau courant est rendue."""
from itertools import permutations

MAX_ESSAIS = 720


def _r(x, m):
    """Renomme récursivement les couleurs (entiers) d'un but / d'une mort ; les chaînes (nature) restent."""
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, int):
        return m.get(x, x)
    if isinstance(x, frozenset):
        return frozenset(_r(y, m) for y in x)
    if isinstance(x, tuple):
        return tuple(_r(y, m) for y in x)
    if isinstance(x, list):
        return [_r(y, m) for y in x]
    return x


def renommer(th, m):
    """Copie de la théorie, couleurs renommées par m (dict couleur → couleur). Les reflets (derives) et les champs
    inconnus restent tels quels."""
    from dataclasses import replace

    def f(c):
        return m.get(c, c)
    return replace(
        th,
        moves={(f(c), a): v for (c, a), v in th.moves.items()},
        solides=frozenset(map(f, th.solides)), murs_supposes=frozenset(map(f, th.murs_supposes)),
        moves_supposes={(f(c), a): h for (c, a), h in th.moves_supposes.items()},
        poussables=frozenset(map(f, th.poussables)),
        consomme=frozenset((f(a), f(b)) for a, b in th.consomme), lie=frozenset((f(a), f(b)) for a, b in th.lie),
        autonomes={f(a): f(b) for a, b in th.autonomes.items()},
        bascule={f(a): f(b) for a, b in th.bascule.items()},
        zone=None if th.zone is None else f(th.zone),
        teleports={f(k): d for k, d in th.teleports.items()},
        saut={(f(c), a): v for (c, a), v in th.saut.items()},
        transforme=frozenset((f(a), f(b), f(c)) for a, b, c in th.transforme),
        formes={f(k): v for k, v in th.formes.items()},
        desel={f(a): f(b) for a, b in th.desel.items()},
        but=_r(th.but, m), buts_compatibles=_r(list(th.buts_compatibles), m), mort=_r(th.mort, m))


def couleurs(th):
    cs = ({c for c, _ in th.moves} | set(th.solides) | set(th.poussables) | {c for p in th.consomme | th.lie for c in p}
          | set(th.autonomes) | set(th.autonomes.values()) | set(th.bascule) | set(th.bascule.values())
          | ({th.zone} if th.zone is not None else set()) | set(th.teleports) | {c for t in th.transforme for c in t}
          | set(th.desel) | set(th.desel.values()))
    return {c for c in cs if isinstance(c, int)}


def transferer(th, tr, rejeu):
    """(théorie renommée, correspondance, transitions rejouées) ; correspondance vide si aucune couleur ne manque ou si
    rien ne fait mieux que la théorie telle quelle. `rejeu(theorie, tr)` → (exactes, total, …)."""
    presentes = {o[0] for e in tr.etats for o in e}
    connues = couleurs(th)
    manquantes = sorted(connues - presentes)
    nouvelles = sorted(presentes - connues)
    th.hors_jeu = tr.exclues
    meilleur = (th, {}, rejeu(th, tr)[0])
    if not manquantes or not nouvelles:
        return meilleur
    for n, cible in enumerate(permutations(nouvelles + [None] * len(manquantes), len(manquantes))):
        if n >= MAX_ESSAIS:
            break
        m = {a: b for a, b in zip(manquantes, cible, strict=True) if b is not None}
        if not m:
            continue
        t2 = renommer(th, m)
        t2.hors_jeu = tr.exclues
        ok = rejeu(t2, tr)[0]
        if ok > meilleur[2]:
            meilleur = (t2, m, ok)
    return meilleur


def fusionner(local, ancienne):
    """CW-258 (transfert structuré du défi 5, porté) : théorie LOCALE complétée par les lois de la théorie précédente
    qu'elle ne contredit pas, sans les conjectures de celle-ci (moves H_oppose / H_partage, murs supposés). Priorité aux
    lois observées localement : une loi ancienne n'entre que si la même clé n'existe pas localement."""
    from dataclasses import replace
    conj = set(ancienne.moves_supposes)
    moves = dict(local.moves) | {k: v for k, v in ancienne.moves.items() if k not in local.moves and k not in conj}
    bascule = dict(ancienne.bascule) | dict(local.bascule)
    autonomes = dict(ancienne.autonomes) | dict(local.autonomes)
    ctrl = {c for c, _ in moves}
    solides = local.solides | ((ancienne.solides - ancienne.murs_supposes) - ctrl)  # collisions confirmées seulement
    return replace(
        local, moves=moves, bascule=bascule, autonomes=autonomes, solides=frozenset(solides),
        poussables=local.poussables | ancienne.poussables, consomme=local.consomme | ancienne.consomme,
        lie=local.lie | ancienne.lie, transforme=local.transforme | ancienne.transforme,
        teleports=dict(ancienne.teleports) | dict(local.teleports), saut=dict(ancienne.saut) | dict(local.saut),
        motif=local.motif or ancienne.motif, zone=local.zone if local.zone is not None else ancienne.zone,
        but=local.but if local.but is not None else ancienne.but)
