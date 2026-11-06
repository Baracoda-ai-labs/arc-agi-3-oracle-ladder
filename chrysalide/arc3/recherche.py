# SPDX-License-Identifier: MIT-0
"""CW-098.4 : traces couvrant TOUS les niveaux d'un jeu public, par recherche en largeur dans le VRAI moteur (bancs seulement :
on copie le jeu et on lit son état interne, ce qu'aucun agent soumis ne peut faire).
Par niveau : BFS depuis l'état de départ du niveau ; un état = (image complète masquée, état caché déclaré, attributs simples
du jeu hors compteurs, niveau) ; les états perdants sont élagués ; arrêt au 1er état qui passe le niveau (chemin le plus
court en coups = borne « optimum »), ou au plafond de temps / de nœuds / de mémoire. On repart du niveau suivant.
Sortie : événements au format du harnais (type initial / action, board, level, action_name, action_display,
level_completed, game_over), lisibles par tous nos bancs (fidelite.py, mesure_exhaustivite.py).

Correctifs du 17/10 (bp35, lf52, r11l, sc25, su15 « épuisés » après 3-15 nœuds) :
- l'empreinte utilisait l'image SANS interfaces ; or plusieurs jeux dessinent tout leur monde dans une interface de caméra
  (bp35, lf52) : image constante, tous les états confondus. On prend l'image complète, cases de jauge masquées ;
- l'état caché déclaré est nul partout ; on ajoute les attributs simples du jeu (et de ses objets propres), sauf ceux qui
  changent à presque chaque coup (compteurs, appris comme la jauge) ;
- les clics déclarés par le moteur (étiquette sys_click) sont partiels ; on ajoute toujours un clic par composante
  connexe de couleur de l'image et par centre de sprite ;
- mémoire : la copie profonde copiait TOUS les niveaux (0,15-1,2 Mo par nœud) ; on partage les niveaux non courants et
  les niveaux propres ; plafond de nœuds en file ; mode « chemin » (on rejoue depuis la racine) si la mémoire l'exige."""

import hashlib
import json
import time
import tracemalloc
from collections import deque

import numpy as np

from chrysalide.arc3.copie import copie_profonde

NOMS = {1: "ACTION1", 2: "ACTION2", 3: "ACTION3", 4: "ACTION4", 5: "ACTION5", 6: "ACTION6", 7: "ACTION7"}
# Champs de tenue de compte du moteur de base (pas l'état du jeu) : exclus de l'empreinte.
TENUE = {"_action_count", "_full_reset", "_action", "_action_complete", "pending_frames", "_levels", "_clean_levels",
         "_camera", "_debug", "_seed", "_game_id", "_win_score"}
PRIM = (int, float, bool, str, bytes, type(None))


def _copier(g):
    """Copie profonde du jeu qui PARTAGE les niveaux propres et les niveaux non courants (seul le niveau courant évolue
    pendant la BFS d'un niveau ; le passage au niveau suivant n'arrive que sur le nœud gagnant, après quoi on rend)."""
    memo = {id(g._clean_levels): g._clean_levels}
    for i, lv in enumerate(g._levels):
        if i != g._current_level_index:
            memo[id(lv)] = lv
    return copie_profonde(g, memo)


def _etat_cache(jeu):
    """Octets de l'état caché déclaré (propriété dans le moteur de base, MÉTHODE dans certains jeux)."""
    hs = jeu._get_hidden_state
    hs = hs() if callable(hs) else hs
    try:
        return np.asarray(hs, dtype=np.int64).tobytes()
    except (TypeError, ValueError):
        return repr(hs).encode()


def _feuille(v, d=0):
    """Représentation stable d'une valeur simple (ou None si la valeur n'est pas simple)."""
    if isinstance(v, PRIM):
        return repr(v)
    if isinstance(v, np.ndarray) and v.size <= 4096:
        return hashlib.sha1(v.tobytes()).hexdigest() + str(v.shape)
    if d < 2 and isinstance(v, (list, tuple)):
        r = [_feuille(x, d + 1) for x in v]
        return None if None in r else "[" + ",".join(r) + "]"
    if d < 2 and isinstance(v, (set, frozenset)):
        r = [_feuille(x, d + 1) for x in v]
        return None if None in r else "{" + ",".join(sorted(r)) + "}"
    if d < 2 and isinstance(v, dict):
        r = [(_feuille(k, d + 1), _feuille(x, d + 1)) for k, x in v.items()]
        return None if any(a is None or b is None for a, b in r) else "{" + ",".join(sorted(f"{a}:{b}" for a, b in r)) + "}"
    return None


def _attributs(jeu):
    """{chemin: repr} des attributs simples du jeu et, un niveau plus bas, de ses objets propres (classes du jeu, pas
    les sprites ni les objets du moteur, déjà visibles dans l'image)."""
    out = {}

    def ajouter(chemin, v, prof):
        if isinstance(v, dict) and prof <= 1 and all(isinstance(c, (str, int)) for c in v):
            for c, x in v.items():  # dictionnaires aplatis : un compteur d'animation y devient un attribut à part
                ajouter(f"{chemin}[{c!r}]", x, prof + 1)
            return
        f = _feuille(v)
        if f is not None:
            out[chemin] = f
        elif prof == 0 and hasattr(v, "__dict__") and type(v).__module__.startswith("arc_agi_3"):
            for k2, v2 in vars(v).items():
                ajouter(f"{chemin}.{k2}", v2, prof + 1)

    for k, v in vars(jeu).items():
        if k not in TENUE:
            ajouter(k, v, 0)
    return out


def _num(s):
    if s in ("True", "False"):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


APPRIS = {"cases": set(), "compteurs": set()}  # appris au début de chaque niveau


def _cle(jeu, image):
    """Empreinte d'une position : image complète (avec interfaces), cases de jauge masquées + état caché déclaré +
    attributs simples hors compteurs + niveau."""
    g = np.array(image, dtype=np.int16)
    if APPRIS["cases"]:
        ys, xs = zip(*APPRIS["cases"], strict=True)
        g[list(ys), list(xs)] = -1
    h = hashlib.sha1(g.tobytes())
    h.update(_etat_cache(jeu))
    at = _attributs(jeu)
    h.update("|".join(f"{k}={at[k]}" for k in sorted(at) if k not in APPRIS["compteurs"]).encode())
    h.update(str(jeu._current_level_index).encode())
    return h.hexdigest()


def _jouer(jeu, a):
    fr = jeu.perform_action(a, raw=True)
    return fr, (np.asarray(fr.frame[-1]) if fr.frame else None)


def _composantes(image):
    """Composantes connexes (4-voisins, même couleur) de l'image affichée. Rend (points, signature) : un point par
    composante (son pixel le plus proche du barycentre, coordonnées d'affichage) et une fonction (x, y) → signature de
    l'objet sous le curseur (couleur, boîte, taille de sa composante), qui sert à reconnaître un clic déjà vu inerte."""
    from scipy import ndimage
    image = np.asarray(image)
    pts, comp, info = [], np.zeros(image.shape, dtype=np.int32), {}
    base = 0
    for c in np.unique(image):
        lab, n = ndimage.label(image == c)
        tailles = np.bincount(lab.ravel())
        for i, sl in enumerate(ndimage.find_objects(lab), start=1):
            ys, xs = np.nonzero(lab[sl] == i)
            j = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
            pts.append((int(xs[j]) + sl[1].start, int(ys[j]) + sl[0].start))
            info[base + i] = (int(c), sl[0].start, sl[0].stop, sl[1].start, sl[1].stop, int(tailles[i]))
        comp[lab > 0] = lab[lab > 0] + base
        base += n

    def signature(x, y):
        return (x, y, info.get(int(comp[y, x]))) if 0 <= x < image.shape[1] and 0 <= y < image.shape[0] else (x, y)

    return pts, signature


def _coups(jeu, image=None, pts_image=None):
    """Coups valides selon le moteur + (si le clic est permis) un clic par composante connexe de l'image et par centre
    de sprite visible, dédoublonnés. Les clics sans effet sont élagués par l'empreinte."""
    from arcengine.enums import ActionInput, GameAction
    coups = [c for c in jeu._get_valid_actions() if int(c.id.value) != 7]
    if 6 not in [int(a) for a in jeu._available_actions]:
        return coups
    vus = {(c.data["x"], c.data["y"]) for c in coups if int(c.id.value) == 6 and c.data}
    pts = []
    k, x0, y0 = jeu.camera._calculate_scale_and_offset()
    cx, cy = jeu.camera._x, jeu.camera._y
    for s in jeu.current_level.get_sprites():
        if s.is_visible:
            pts.append((x0 + (s.x - cx + s.width // 2) * k + k // 2, y0 + (s.y - cy + s.height // 2) * k + k // 2))
    if pts_image is not None:
        pts += pts_image
    elif image is not None:
        pts += _composantes(image)[0]
    for x, y in pts:
        if 0 <= x < 64 and 0 <= y < 64 and (x, y) not in vus:
            vus.add((x, y))
            coups.append(ActionInput(id=GameAction.ACTION6, data={"x": x, "y": y}))
    return coups


def _objet_attr(jeu, chemin):
    """(objet, nom) pour un chemin « a » ou « a.b » (pas les clés de dictionnaire)."""
    if "[" in chemin:
        return None, None
    parts = chemin.split(".")
    o = jeu
    for p in parts[:-1]:
        o = getattr(o, p, None)
    return o, parts[-1]


def _cases_compteur(jeu, compteurs, image):
    """Intervention : on donne à chaque compteur d'autres valeurs sur une COPIE et on re-rend l'image complète ; les
    cases qui bougent sont celles qui affichent le compteur (jauge, chiffres) et sont masquées."""
    cases = set()
    for c in compteurs:
        g = _copier(jeu)
        o, nom = _objet_attr(g, c)
        v0 = getattr(o, nom, None) if o is not None else None
        if not isinstance(v0, (int, float)) or isinstance(v0, bool):
            continue
        try:
            ref = np.asarray(g.camera.render(g.current_level.get_sprites()))
            for v in sorted({0, 1, int(v0) // 2, int(v0) - 1, int(v0) + 1, *range(0, max(int(v0), 0) + 2, 1)})[:130]:
                setattr(o, nom, type(v0)(v))
                im = np.asarray(g.camera.render(g.current_level.get_sprites()))
                ys, xs = np.nonzero(im != ref)
                cases |= set(zip(ys.tolist(), xs.tolist(), strict=True))
        except Exception:  # noqa: BLE001, S110  (un jeu peut refuser une valeur : on garde ce qu'on a)
            pass
        finally:
            setattr(o, nom, v0)
    del image
    return cases


def apprendre(jeu, image, n=60, graine=0, min_chg=3):
    """Joue n coups au hasard sur une COPIE et apprend, de façon générique :
    - les COMPTEURS : attributs numériques qui ont changé ≥ min_chg fois, toujours dans le même sens (pas, horloge) ;
    - les ÉCHOS du coup : attributs qui valent les coordonnées du dernier clic après (presque) chaque clic ;
    - les cases d'image qui affichent ces compteurs (intervention, _cases_compteur) + les barres de jauge (Masque).
    Rend (cases masquées, attributs exclus de l'empreinte)."""
    import random

    from chrysalide.arc3.masque import Masque
    rng, g, m = random.Random(graine), _copier(jeu), Masque(min_coups=8)
    avant, at0 = np.asarray(image), _attributs(g)
    sens, echo, joues = {}, {}, 0
    for _ in range(n):
        coups = _coups(g, avant)
        if not coups:
            break
        a = rng.choice(coups)
        fr, im = _jouer(g, a)
        if fr.state.name in ("GAME_OVER", "WIN") or g._score > jeu._score or im is None:
            break
        m.observer(avant.tolist(), im.tolist())
        joues += 1
        at1 = _attributs(g)
        for k in set(at0) | set(at1):
            if at0.get(k) != at1.get(k):
                x0, x1 = _num(at0.get(k)), _num(at1.get(k))
                sens.setdefault(k, []).append(None if x0 is None or x1 is None else (x1 > x0) - (x1 < x0))
        if int(a.id.value) == 6:
            x, y = a.data["x"], a.data["y"]
            for k, v in at1.items():
                if v != at0.get(k):  # changé après un clic : vaut-il les coordonnées du clic ?
                    e = echo.setdefault(k, [0, 0])
                    e[0] += 1
                    e[1] += v in (f"[{x},{y}]", f"[{y},{x}]")
        avant, at0 = im, at1
    # un COMPTEUR de pas / horloge change à (presque) chaque coup ; un attribut monotone qui ne change que parfois (gemmes
    # ramassées, cibles atteintes) est un ÉTAT du jeu et doit rester dans l'empreinte (banc T4 : y008 niveau 3, faux
    # « aucun chemin » quand le compteur de gemmes était exclu, CCM-164-A)
    seuil = max(min_chg, 0.8 * joues)
    compteurs = {k for k, s in sens.items() if len(s) >= seuil and None not in s and len(set(s)) == 1}
    compteurs |= {k for k, (nc, ok) in echo.items() if nc >= min_chg and ok == nc}
    return set(m.cellules()) | _cases_compteur(jeu, compteurs, image), compteurs


def memoire_par_noeud(jeu, n=5):
    """Mo par copie partagée (tracemalloc)."""
    tracemalloc.start()
    cs = [_copier(jeu) for _ in range(n)]
    cur, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del cs
    return cur / n / 1e6


def resoudre_niveau(jeu, image0, plafond_s=600, plafond_noeuds=200_000, max_file=200_000, memoire_mo=8000, mode="auto",
                    inertes=3):
    """BFS du niveau (voir `_resoudre_niveau`). Si la BFS conclut « aucun chemin » alors que des cases d'image ont été
    masquées (jauge apprise), elle est refaite SANS masque : une jauge d'énergie qu'on peut recharger est un ÉTAT du jeu
    (banc T4 : y008 niveau 3, recharge + gemmes, faux « aucun chemin » après 536 nœuds, CCM-164-A)."""
    t0 = time.monotonic()
    r = _resoudre_niveau(jeu, image0, plafond_s, plafond_noeuds, max_file, memoire_mo, mode, inertes)
    if r[0] is None and r[3].startswith("épuisé") and r[4].get("cases_masquees"):
        reste = max(1.0, plafond_s - (time.monotonic() - t0))
        r2 = _resoudre_niveau(jeu, image0, reste, plafond_noeuds, max_file, memoire_mo, mode, inertes, sans_masque=True)
        r2[4]["second_passage_sans_masque"] = True
        r2[4]["premier_passage"] = r[3]
        return r2
    return r


def _resoudre_niveau(jeu, image0, plafond_s=600, plafond_noeuds=200_000, max_file=200_000, memoire_mo=8000, mode="auto",
                     inertes=3, sans_masque=False):
    """BFS du niveau courant. Rend (chemin [ActionInput], jeu atteint, image, statut, infos).
    mode « copie » : chaque nœud en file garde sa copie du jeu ; « chemin » : il ne garde que (parent, coup) et on
    rejoue depuis la racine à l'expansion ; « auto » : copie tant que (copies en file × Mo/nœud) ≤ memoire_mo, puis
    chemin pour les nœuds suivants (hybride : rapide tant que la mémoire le permet, borné ensuite).
    inertes : un clic dont l'objet sous le curseur (signature de composante) a été sans effet ≥ inertes fois et jamais
    efficace n'est plus essayé (heuristique : la BFS reste exacte sur les coups essayés ; 0 = désactivé)."""
    from arcengine.enums import ActionInput, GameAction, GameState
    racine = copie_profonde(jeu)  # privée : les nœuds partagent SES niveaux non courants, pas ceux du vrai jeu
    APPRIS["cases"], APPRIS["compteurs"] = apprendre(racine, image0)
    if sans_masque:
        APPRIS["cases"] = set()
    mo = memoire_par_noeud(racine)
    max_copies = {"copie": max_file, "chemin": 0}.get(mode, int(memoire_mo / max(mo, 1e-3)))
    infos = {"mo_par_noeud": round(mo, 3), "mode": mode, "max_copies": max_copies,
             "compteurs": sorted(APPRIS["compteurs"]), "cases_masquees": len(APPRIS["cases"])}
    depart_score = jeu._score
    arbre = [(-1, None)]  # (parent, (id, x, y)) : chemin reconstruit par remontée, coups compacts

    def coup(t):
        return ActionInput(id=GameAction.from_id(t[0]), data={"x": t[1], "y": t[2]} if t[0] == 6 else {})

    def chemin_de(i):
        out = []
        while i > 0:
            i, t = arbre[i]
            out.append(coup(t))
        return out[::-1]

    def etat_de(i):
        g = _copier(racine)
        im = image0
        for a in chemin_de(i):
            _fr, im = _jouer(g, a)
        return g, im

    vus = {_cle(racine, image0)}
    file = deque([(0, racine, np.asarray(image0, dtype=np.int8))])
    t0, n, pic, copies, rejeux, sautes = time.monotonic(), 0, 1, 1, 0, 0
    bilan_clic = {}  # signature → [sans effet, avec effet]
    while file:
        i, g, img = file.popleft()
        if g is None:
            g, img = etat_de(i)
            rejeux += 1
        else:
            copies -= 1
        cle_g = _cle(g, img)
        pts, signature = _composantes(img)
        for a in _coups(g, img, pts):
            sig = signature(a.data["x"], a.data["y"]) if int(a.id.value) == 6 and a.data else None
            if inertes and sig is not None:
                b = bilan_clic.get(sig)
                if b is not None and b[0] >= inertes and b[1] == 0:
                    sautes += 1
                    continue
            dt = time.monotonic() - t0
            if dt > plafond_s or n >= plafond_noeuds:
                infos.update(noeuds=n, s=round(dt, 1), pic_file=pic)
                return None, None, None, f"plafond ({n} nœuds, {dt:.0f} s)", infos
            h = _copier(g)
            fr, im = _jouer(h, a)
            n += 1
            if fr.state == GameState.WIN or h._score > depart_score:
                infos.update(noeuds=n, s=round(time.monotonic() - t0, 1), pic_file=pic)
                return chemin_de(i) + [a], h, im, f"résolu ({n} nœuds)", infos
            if fr.state == GameState.GAME_OVER or im is None:
                continue
            k = _cle(h, im)
            if sig is not None:
                bilan_clic.setdefault(sig, [0, 0])[k != cle_g] += 1
            if k not in vus:
                if len(file) >= max_file:
                    infos.update(noeuds=n, s=round(time.monotonic() - t0, 1), pic_file=pic)
                    return None, None, None, f"plafond mémoire ({len(file)} en file, {n} nœuds)", infos
                vus.add(k)
                d = a.data or {}
                arbre.append((i, (int(a.id.value), d.get("x"), d.get("y"))))
                garder = copies < max_copies
                copies += garder
                file.append((len(arbre) - 1, h, im.astype(np.int8)) if garder else (len(arbre) - 1, None, None))
                pic = max(pic, len(file))
        infos.update(rejeux=rejeux, clics_sautes=sautes)
    infos.update(noeuds=n, s=round(time.monotonic() - t0, 1), pic_file=pic)
    return None, None, None, f"épuisé ({n} nœuds{', élagage inertes' if sautes else ''}) : aucun chemin", infos


def traces_jeu(arc, game_id, plafond_s=600, plafond_noeuds=200_000, niveaux=None, **kw):
    """Rend (événements, bilan par niveau). niveaux : nombre maximal de niveaux à résoudre (None = tous)."""
    env = arc.make(game_id)
    fr = env.reset()
    jeu = env._game
    image = np.asarray(fr.frame[-1])
    ev = [{"type": "initial", "board": json.dumps(image.tolist()), "level": str(jeu._current_level_index + 1)}]
    bilan = []
    while niveaux is None or len(bilan) < niveaux:
        n_niv = jeu._current_level_index + 1
        chemin, _h, _im, statut, infos = resoudre_niveau(jeu, image, plafond_s, plafond_noeuds, **kw)
        bilan.append({"niveau": n_niv, "statut": statut, "coups": len(chemin) if chemin else None, **infos})
        if chemin is None:
            break
        g = jeu  # on rejoue le chemin sur le jeu réel pour produire les images intermédiaires
        for i, a in enumerate(chemin):
            fr2, im2 = _jouer(g, a)
            d = a.data or {}
            aff = f"MOUSE(row={d.get('y')}, col={d.get('x')})" if int(a.id.value) == 6 else NOMS[int(a.id.value)]
            ev.append({"type": "action", "board": json.dumps(im2.tolist()), "level": str(n_niv), "action_name": NOMS[int(a.id.value)],
                       "action_display": aff, "level_completed": str(i == len(chemin) - 1),
                       "game_over": str(fr2.state.name == "GAME_OVER")})
        if g._current_level_index + 1 == n_niv and fr2.state.name != "WIN":
            bilan[-1]["statut"] += " ; REJEU NON CONFORME"
            break
        jeu, image = g, im2
        if fr2.state.name == "WIN":
            break
    return ev, bilan
