"""[G] L'algorithme GELÉ de `macro_g.py` (f9fb62a4), avec le VRAI MOTEUR (arcengine) pour simulateur, pour les jeux
sans programme dans notre langage (T4, lot tenu à l'écart). Rien d'autre ne change :
- objet piloté = sprites dont le déplacement DÉPEND de la flèche (lus dans le moteur, reconnus par leur nom). SEULE
  différence d'algorithme avec macro_g : une jauge qui recule à chaque coup, quelle que soit la direction, n'est pas
  pilotée (trouvé sur g50t N1 avec le moteur, jeu public, avant toute ouverture du lot à l'écart) ;
- macro = largeur aux flèches, nouveauté sur la position des objets pilotés (un état par case, au plus court) ;
- recherche haute = largeur sur les états (clé `recherche._cle`), macros + actions non fléchées (SPACE, clics de
  `recherche._coups`, écartées si elles ne changent rien de visible), alternance (pas deux macros d'affilée), repli sans
  alternance si l'espace s'épuise ; clé = référence + empreinte de l'état sérialisé hors compteurs ;
- victoire = état WIN ou niveau suivant, lue dans le moteur (le plan est donc exact par construction).
`chercher_moteur(jeu, image, etats_hauts=20000, secondes=300)` → dict (plan : liste d'ActionInput, ou None)."""
import time
from collections import deque

import numpy as np

FLECHES = (1, 2, 3, 4)


def chercher_moteur(jeu, image0, etats_hauts=20000, secondes=300, alterner=True, cle_pleine=None):
    """cle_pleine None : portefeuille, clé pleine (état sérialisé) sur la moitié du budget, puis clé de la référence sur
    le reste ; True / False : une seule des deux."""
    if cle_pleine is None:
        t = time.process_time()
        r = chercher_moteur(jeu, image0, etats_hauts, secondes / 2, alterner, cle_pleine=True)
        if r["plan"] is not None:
            return {**r, "cle": "pleine"}
        r2 = chercher_moteur(jeu, image0, etats_hauts, secondes - (time.process_time() - t), alterner, cle_pleine=False)
        return {**r2, "cle": "référence", "avant": {x: r.get(x) for x in ("arret", "etats_hauts", "cpu")}}
    from arcengine.enums import ActionInput, GameAction, GameState

    from chrysalide.arc3.recherche import APPRIS, _cle, _composantes, _copier, _coups, _jouer
    T, t0 = time.process_time, time.process_time()
    # clé de la recherche haute : celle de la référence (compteurs et cases de jauge appris, `apprendre`) PLUS une empreinte
    # de tout l'état du jeu sérialisé hors compteurs : `_attributs` ne voit pas les objets propres au jeu (g50t : le trajet
    # enregistré du fantôme n'y est pas, et deux SPACE après des trajets différents auraient la même clé)
    import hashlib

    from chrysalide.arc3.recherche import TENUE, apprendre
    APPRIS["cases"], APPRIS["compteurs"] = apprendre(_copier(jeu), image0)

    def empreinte(v, d, vus):
        """Valeur stable d'un état de jeu : primitives, tableaux, listes, dicts ; objets du module du jeu parcourus ;
        sprites résumés (nom, position, visibilité) ; le reste par son type. Profondeur ≤ 5, cycles coupés."""
        if isinstance(v, (int, float, str, bool, type(None))):
            return repr(v)
        if isinstance(v, np.ndarray):
            return hashlib.sha1(v.tobytes()).hexdigest()
        if d > 5 or id(v) in vus:
            return "…"
        vus = vus | {id(v)}
        if isinstance(v, (list, tuple)):
            return "[" + ",".join(empreinte(x, d + 1, vus) for x in v) + "]"
        if isinstance(v, (set, frozenset)):
            return "{" + ",".join(sorted(empreinte(x, d + 1, vus) for x in v)) + "}"
        if isinstance(v, dict):
            return "{" + ",".join(sorted(f"{empreinte(a, d + 1, vus)}:{empreinte(b, d + 1, vus)}" for a, b in v.items())) + "}"
        if type(v).__name__ == "Sprite":
            return f"S({getattr(v, 'name', '')},{getattr(v, 'x', '')},{getattr(v, 'y', '')},{getattr(v, 'is_visible', '')})"
        if hasattr(v, "__dict__") and type(v).__module__.startswith("arc_agi_3"):
            return type(v).__name__ + empreinte(vars(v), d + 1, vus)
        return type(v).__name__

    def cle(g, im):
        if not cle_pleine:
            return _cle(g, im)
        d = {n: v for n, v in vars(g).items() if n not in APPRIS["compteurs"] and n not in TENUE and not n.startswith("_")}
        return _cle(g, im) + hashlib.sha1(empreinte(d, 0, frozenset()).encode()).hexdigest()
    k0 = jeu._current_level_index
    n_sim = 0

    def pas(g, a):
        nonlocal n_sim
        n_sim += 1
        h = _copier(g)
        try:
            fr, im = _jouer(h, a)
        except Exception:  # noqa: BLE001 — coup qui plante : branche abandonnée
            return None, None, None
        if fr.state == GameState.WIN or h._current_level_index > k0:
            return h, im, "gagne"
        if fr.state == GameState.GAME_OVER or im is None:
            return None, None, None
        return h, im, None

    def sprites(g):
        return [(s.name, s.x, s.y) for s in g.current_level.get_sprites() if getattr(s, "is_visible", True)]
    fleches = [ActionInput(id=GameAction.from_id(i)) for i in FLECHES]
    base = sprites(jeu)
    depl = {}  # nom → {déplacement observé pour chaque flèche}
    for a in fleches:
        h, _im, _ = pas(jeu, a)
        if h is not None:
            apres = sprites(h)
            if len(apres) == len(base):
                for b, c in zip(base, apres, strict=True):
                    depl.setdefault(b[0], set()).add((c[1] - b[1], c[2] - b[2]))
    # piloté = son déplacement DÉPEND de la flèche (une jauge recule pareil quelle que soit la direction : pas pilotée)
    pil = {n for n, ds in depl.items() if len(ds) > 1 and any(d != (0, 0) for d in ds)}

    def pos(g):
        return tuple(sorted((n, x, y) for n, x, y in sprites(g) if n in pil))

    def macros(g, im):
        vus, file, out = {pos(g)}, deque([(g, im, [])]), []
        while file:
            s, _si, ch = file.popleft()
            for a in fleches:
                h, hi, issue = pas(s, a)
                if h is None:
                    continue
                if issue == "gagne":
                    return [(h, hi, [*ch, a], True)]
                p = pos(h)
                if p in vus:
                    continue
                vus.add(p)
                out.append((h, hi, [*ch, a], False))
                file.append((h, hi, [*ch, a]))
        return out
    img0 = np.asarray(image0, dtype=np.int8)
    plan = None
    haut, file = {cle(jeu, img0)}, deque([(jeu, img0, [], False)])
    while file and len(haut) < etats_hauts and T() - t0 < secondes and plan is None:
        g, im, ch, apres_macro = file.popleft()
        suivants = [] if (apres_macro and alterner) else [(h, hi, cs, gg, True) for h, hi, cs, gg in macros(g, im)]
        pts, _sig = _composantes(im)
        for a in _coups(g, im, pts):
            if int(a.id.value) in FLECHES:
                continue
            h, hi, issue = pas(g, a)
            if h is not None and (issue == "gagne" or not np.array_equal(np.asarray(hi), np.asarray(im))):
                suivants.append((h, hi, [a], issue == "gagne", False))  # action sans effet visible : écartée
        for h, hi, cs, gagne, est_macro in suivants:
            if gagne:
                plan = [*ch, *cs]
                break
            kk = cle(h, np.asarray(hi, dtype=np.int8))
            if kk in haut:
                continue
            haut.add(kk)
            file.append((h, np.asarray(hi, dtype=np.int8), [*ch, *cs], est_macro))
    r = {"pilotes": sorted(pil), "etats_hauts": len(haut), "simulations": n_sim, "cpu": round(T() - t0, 1),
         "plan": plan, "long_plan": None if plan is None else len(plan), "alterner": alterner,
         "arret": "plan" if plan else ("espace épuisé" if not file else "budget")}
    if plan is None and not file and alterner and T() - t0 < secondes:  # repli de macro_g : sans alternance
        r2 = chercher_moteur(jeu, image0, etats_hauts, secondes - (T() - t0), alterner=False, cle_pleine=cle_pleine)
        return {**r2, "repli": "sans alternance"}
    return r
