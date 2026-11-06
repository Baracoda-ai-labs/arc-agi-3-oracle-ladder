# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — deux mesures reprises de la littérature (CW-113) :
- classement contre DISTRACTEURS (OneLife) : la prédiction de la théorie ressemble-t-elle plus (Jaccard sur les objets)
  au vrai état suivant qu'à des distracteurs plantés (un objet du vrai état suivant déplacé d'une case, ou retiré, ou un
  objet mobile laissé à sa place) ? Plus informatif que le rejeu exact quand on n'est pas à 100 % ;
- SUPPORT par règle de déplacement (PoE-World) : transitions où la règle s'applique et est confirmée / contredite ;
  `elaguer` retire les règles induites (non supposées) sans aucune confirmation."""
import random
from dataclasses import replace

from chrysalide.arc3.logique.faits import apparier


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 1.0


def distracteurs(vrai, avant, rnd, n=6):
    """États plausibles mais faux : un objet déplacé d'une case, un objet retiré, un mobile resté sur place."""
    out, vrai = [], list(vrai)
    for _ in range(n):
        if not vrai:
            break
        k = rnd.randrange(len(vrai))
        o = vrai[k]
        mode = rnd.randrange(3)
        if mode == 0:
            dx, dy = rnd.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
            d = vrai[:k] + [(o[0], o[1], o[2] + dx, o[3] + dy)] + vrai[k + 1:]
        elif mode == 1:
            d = vrai[:k] + vrai[k + 1:]
        else:
            d = list(avant)  # « rien ne bouge »
        if set(d) != set(vrai):
            out.append(tuple(d))
    return out


def classement(th, traj, ts, graine=0, precedent=None):
    """Sur les transitions ts : part où la prédiction est plus proche du vrai suivant que de tous les distracteurs
    (« top-1 »), et Jaccard moyen prédiction / vrai suivant."""
    rnd = random.Random(graine)
    top = jac = n = 0
    for t in ts:
        p = th.pas(traj.etats[t], traj.actions[t], traj.taille,
                   precedent=precedent(t) if precedent else None)[0]
        vrai = traj.etats[t + 1]
        s_vrai = jaccard(p, vrai)
        top += all(s_vrai > jaccard(p, d) for d in distracteurs(vrai, traj.etats[t], rnd))
        jac += s_vrai
        n += 1
    return {"top1": top / n if n else 0.0, "jaccard": jac / n if n else 0.0, "n": n}


def support(th, sources):
    """{(classe, action): [confirmées, contredites]} pour chaque règle de déplacement."""
    sup = {k: [0, 0] for k in th.moves}
    for tr, ts, *_ in sources:
        for t in (range(len(tr.actions)) if ts is None else ts):
            a = tr.actions[t]
            if isinstance(a, tuple):
                continue
            paires, _ = apparier(tr.etats[t], tr.etats[t + 1])
            for i, j in paires:
                o = tr.etats[t][i]
                if (o[0], a) not in th.moves or j is None:
                    continue
                v = (tr.etats[t + 1][j][2] - o[2], tr.etats[t + 1][j][3] - o[3])
                if v == th.moves[(o[0], a)]:
                    sup[(o[0], a)][0] += 1
                elif v != (0, 0):  # (0, 0) peut être un blocage : ni pour ni contre
                    sup[(o[0], a)][1] += 1
    return sup


def elaguer(th, sources):
    """Retire les règles de déplacement INDUITES (pas les hypothèses nommées) qui ne sont jamais confirmées, ou plus
    souvent contredites que confirmées. Renvoie (théorie élaguée, règles retirées)."""
    sup = support(th, sources)
    retire = [k for k, (c, x) in sup.items() if k not in th.moves_supposes and (c == 0 or x > c)]
    return replace(th, moves={k: v for k, v in th.moves.items() if k not in retire}), retire
