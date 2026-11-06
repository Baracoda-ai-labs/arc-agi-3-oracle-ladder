"""[G] CCM-048-G : A* PONDÉRÉ sur un programme exporté du langage (théorie de C), h lue dans la FORME DU BUT
(comme l'A* d'Astra sur sa théorie corrigée de ka59 N4) : ordonnancement seulement, rien n'est élagué
(h inconnue = 0 → largeur). Coups = flèches/SPACE fournis + clics recalculés sur la scène de chaque état
(objets de la signature d'une pièce du but, ou de tout objet). Clé d'état : `sim_genere.cle_complete`.
  emboite(cibles, pièces[, paires]) : somme, sur la meilleure affectation cible → pièce (paires respectées), de la
      distance de Manhattan entre centres (×2) divisée par 2·pas (pas = 3 par défaut), 0 dans la tolérance de 2 ;
  centre(a, b) : distance du centre de a au plus proche petit b ;
  autre forme : h = 0.
`astar(texte, scene, etat, h, fleches, clics, poids, secondes, noeuds)` → (coups | None, infos)."""
import heapq
import itertools
import time

import numpy as np


def _code(o):
    px = np.asarray(o["pixels"])
    v = px[px >= 0]
    return int(v.max()) if v.size else None


def _rendu(c):
    return c if c is None or c < 512 else (c - 512) % 16


def _centre2(o):
    px = np.asarray(o["pixels"])
    ys, xs = np.nonzero(px >= 0)
    return 2 * o["x"] + xs.min() + xs.max(), 2 * o["y"] + ys.min() + ys.max()


def h_but(but, pas=3):
    if not but:
        return lambda sc: 0
    if but[0] == "emboite":
        cibles, classes = list(but[1]), set(but[2])
        paires = dict(but[3]) if len(but) > 3 and but[3] else {}
        rendus = {_rendu(c) for c in classes} | classes

        def h(sc):
            pieces = [(_code(o), _centre2(o)) for o in sc.sprites if o.get("visible", True) and
                      (_code(o) in classes or _rendu(_code(o)) in rendus) and np.asarray(o["pixels"]).size <= 400]
            if len(pieces) < len(cibles):
                return 0
            best = None
            for perm in itertools.permutations(range(len(pieces)), len(cibles)):
                tot = 0
                for (cx, cy), j in zip(cibles, perm, strict=True):
                    c, (px, py) = pieces[j]
                    if (cx, cy) in paires and _rendu(c) != _rendu(paires[(cx, cy)]) and c != paires[(cx, cy)]:
                        tot = None
                        break
                    d = abs(px - cx) + abs(py - cy)
                    tot += 0 if d <= 2 else d / (2 * pas)
                if tot is not None and (best is None or tot < best):
                    best = tot
            return best or 0
        return h
    if but[0] == "centre":
        a, b = but[1], but[2]

        def h(sc):
            A = [_centre2(o) for o in sc.sprites if _code(o) == a]
            B = [_centre2(o) for o in sc.sprites if _code(o) == b and (np.asarray(o["pixels"]) >= 0).sum() <= 2]
            return min((abs(p[0] - q[0]) + abs(p[1] - q[1])) / (2 * pas) for p in A for q in B) if A and B else 0
        return h
    return lambda sc: 0


def clics_scene(sc, signature=None):
    out = []
    for o in sc.sprites:
        if not o.get("visible", True):
            continue
        if signature is not None and _rendu(_code(o)) not in signature:
            continue
        px = np.asarray(o["pixels"])
        ys, xs = np.nonzero(px >= 0)
        if not len(xs) or len(xs) > 64 * 64 // 4:
            continue
        j = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
        c = ("CLICK", int(o["y"] + ys[j]), int(o["x"] + xs[j]))
        if c not in out:
            out.append(c)
    return out


def astar(texte, scene, etat, h, fleches=("UP", "DOWN", "LEFT", "RIGHT"), clics=None, poids=3.0, secondes=30,
          noeuds=10 ** 7):
    """clics : None (pas de clic), ou ensemble de couleurs rendues des objets cliquables, ou "tous"."""
    from chrysalide.arc3.sim_genere import cle_complete
    from chrysalide.arc3.sim_rapide import ProgrammeCompile, cloner
    prog = ProgrammeCompile(texte)
    t0, n = time.process_time(), 0
    h0 = h(scene)
    tas = [(poids * h0, 0, 0, scene, etat, [])]
    vus = {cle_complete(scene, etat): 0}
    k = 0
    while tas and time.process_time() - t0 < secondes and n < noeuds:
        _f, g, _k, s, e, ch = heapq.heappop(tas)
        n += 1
        coups = [(a, None, None) for a in fleches]
        if clics is not None:
            coups += clics_scene(s, None if clics == "tous" else clics)
        for c in coups:
            s2, e2 = cloner(s, e)
            prog.etat = e2
            try:
                prog.step(s2, c)
            except Exception:  # noqa: BLE001, S112
                continue
            if s2.issue in ("niveau", "victoire"):
                plan = [*ch, c]
                coups_noms = [x[0] if x[0] != "CLICK" else f"CLICK({x[1]}, {x[2]})" for x in plan]
                return coups_noms, {"noeuds": n, "cpu": round(time.process_time() - t0, 2), "h0": h0}
            if s2.issue is not None:
                continue
            kk = cle_complete(s2, prog.etat)
            if vus.get(kk, 10 ** 9) <= g + 1:
                continue
            vus[kk] = g + 1
            k += 1
            heapq.heappush(tas, (g + 1 + poids * h(s2), g + 1, k, s2, prog.etat, [*ch, c]))
    return None, {"noeuds": n, "cpu": round(time.process_time() - t0, 2), "h0": h0, "etats": len(vus)}
