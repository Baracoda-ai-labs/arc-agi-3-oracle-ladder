# SPDX-License-Identifier: MIT-0
"""CW-076/077 : signaux bon marché pour classer la famille d'un jeu (piste 13), SANS LLM, en quelques coups.
Trois sources, séparées dans la sortie (on doit savoir ce que l'agent aurait vraiment) :
- « api » : ce que l'environnement donne à tout agent (actions disponibles, nombre de niveaux ; et, en local, les
  métadonnées `tags` et `baseline_actions` = coups humains de référence par niveau — leur présence sur la passerelle
  Kaggle n'est PAS vérifiée) ;
- « observe » : ce qu'on mesure en jouant n coups d'exploration : images par action (animations), cases qui changent à
  chaque coup quelle que soit l'action (HUD), barre qui décroît d'un cran par coup (budget de pas), objets (composantes
  par couleur sur l'image), part des coups sans effet hors HUD ;
- « oracle » (bancs seulement) : vérité du moteur (échelle de caméra, nombre d'interfaces HUD, sprites)."""
from collections import Counter

import numpy as np

from chrysalide.arc3.rendu import objets_moteur, sprites

NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 6: "CLICK", 7: "UNDO"}


def _coups(f, g, n, rng):
    """Coups d'exploration génériques : flèches et SPACE en tourniquet ; s'il n'y a que le clic, le centre des objets."""
    dispo = [int(a) for a in f.available_actions]
    simples = [a for a in dispo if a in (1, 2, 3, 4, 5)]
    if simples:
        return [(simples[i % len(simples)], None) for i in range(n)]
    objs = sorted(sprites(g, Counter(g.ravel().tolist()).most_common(1)[0][0]), key=lambda s: len(s[2]))
    cibles = [(s[4] + s[2][len(s[2]) // 2][0], s[3] + s[2][len(s[2]) // 2][1]) for s in objs] or [(32, 32)]
    return [(6, cibles[i % len(cibles)]) for i in range(n)]


def signaux_partie(arc, game_id, n=8, graine=0, oracle=True):
    from arcengine.enums import GameAction
    env = arc.make(game_id)
    f = env.reset()
    info = next((e for e in arc.get_environments() if e.game_id == game_id), None)
    g = np.array(f.frame[-1])
    rng = np.random.default_rng(graine)
    images, diffs, sans_effet = [], [], 0
    for a, cible in _coups(f, g, n, rng):
        f2 = env.step(GameAction.from_id(a), data={"x": cible[1], "y": cible[0]}) if cible else env.step(GameAction.from_id(a))
        g2 = np.array(f2.frame[-1])
        images.append(len(f2.frame))
        diffs.append(g2 != g)
        if f2.state.name == "GAME_OVER":
            f2 = env.step(GameAction.RESET)
            g2 = np.array(f2.frame[-1])
        g, f = g2, f2
    d = np.array(diffs)
    hud = np.zeros((64, 64), bool)
    hud[:4], hud[-4:], hud[:, :4], hud[:, -4:] = True, True, True, True  # bordure (barres et compteurs)
    toujours = d.mean(axis=0) >= 0.8 if len(d) else np.zeros((64, 64), bool)  # change à chaque coup (joueur, HUD animé)
    hors_hud = d & ~hud
    sans_effet = int((~hors_hud.reshape(len(d), -1).any(axis=1)).sum()) if len(d) else 0
    # budget de pas : la bordure change à (presque) chaque coup, et ce sont des cases NEUVES à chaque fois (barre qui se vide,
    # sans retour en arrière) ; cran = nombre médian de cases de bordure touchées par coup
    par_coup = [set(zip(*np.nonzero(x & hud), strict=True)) for x in d]
    actifs = [c for c in par_coup if c]
    neuves = sum(len(c - set().union(*par_coup[:i])) for i, c in enumerate(par_coup)) if par_coup else 0
    total = sum(len(c) for c in par_coup)
    budget = len(actifs) >= 0.75 * max(len(d), 1) and total > 0 and neuves / total >= 0.8
    cran = float(np.median([len(c) for c in actifs])) if actifs else 0.0
    obs = {"images_par_action": dict(Counter(images)), "animation": max(images, default=1) > 1,
           "cases_toujours_changees": int(toujours.sum()), "cases_bordure_changees": int(total), "cran_par_coup": cran,
           "budget_detecte": bool(budget), "coups_sans_effet_hors_hud": sans_effet, "coups": len(d),
           "objets_image": len(sprites(np.array(f.frame[-1]), Counter(np.array(f.frame[-1]).ravel().tolist()).most_common(1)[0][0]))}
    api = {"actions": [NOMS.get(int(a), str(a)) for a in f.available_actions], "niveaux": int(f.win_levels),
           "tags_meta": list(getattr(info, "tags", None) or []), "baseline_actions_meta": list(getattr(info, "baseline_actions", None) or [])}
    out = {"jeu": game_id, "api": api, "observe": obs}
    if oracle:
        env0 = arc.make(game_id)
        env0.reset()
        om = objets_moteur(env0)
        out["oracle"] = {"echelle": om["echelle"], "vue": om["vue"], "hud_interfaces": len(env0._game.camera._interfaces),
                         "sprites": len(om["sprites"])}
    return out
