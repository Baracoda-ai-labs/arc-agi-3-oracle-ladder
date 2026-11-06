"""T3.1 — r11l : dynamique d'un clic exprimée avec les seuls effets de ontologie_exec.Scene.
État final d'un coup (les animations multi-trames se résolvent : marques de cible = cibles couvertes après l'aller)."""
import numpy as np

MARQUE = {"nom": "flvobx-flkdtg", "tags": [], "couche": 0, "visible": True, "bloquant": True,
          "pixels": np.array([[-1, -1, 0, -1, 0, -1, -1], [-1, 0, -1, -1, -1, 0, -1], [0, -1, -1, -1, -1, -1, 0],
                              [-1] * 7, [0, -1, -1, -1, -1, -1, 0], [-1, 0, -1, -1, -1, 0, -1],
                              [-1, -1, 0, -1, 0, -1, -1]])}
_ORDRE = {}  # ordre des pattes (tri initial par distance à l'origine), par niveau


def _nom(s):
    return s.get("nom", "")


def _pref(scene, p):
    return [s for s in scene.sprites if _nom(s).startswith(p)]


def _suffixe(s, p):
    return _nom(s)[len(p):]


def _touche(a, b, pos=None):
    if a is b or not (a.get("bloquant", True) and b.get("bloquant", True)):
        return False
    ax, ay = pos if pos else (a["x"], a["y"])
    pa, pb = a["pixels"], b["pixels"]
    x0, x1 = max(ax, b["x"]), min(ax + pa.shape[1], b["x"] + pb.shape[1])
    y0, y1 = max(ay, b["y"]), min(ay + pa.shape[0], b["y"] + pb.shape[0])
    if x1 <= x0 or y1 <= y0:
        return False
    ra = pa[y0 - ay:y1 - ay, x0 - ax:x1 - ax]
    rb = pb[y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]]
    return bool(np.any((ra != -1) & (rb != -1)))


def _pattes(scene):
    pattes = _pref(scene, "roefwulewcui-")
    cle = (tuple(sorted(_nom(p) for p in pattes)),
           tuple(sorted((s["x"], s["y"]) for s in scene.sprites if _nom(s).startswith(("wakneh-", "flkdtg-")))))
    if not hasattr(scene, "_r11l_ordre"):
        if cle not in _ORDRE:
            _ORDRE[cle] = [_nom(p) for p in sorted(pattes, key=lambda p: (p["x"] ** 2 + p["y"] ** 2) ** 0.5)]
        scene._r11l_ordre = _ORDRE[cle]
    rang = {n: i for i, n in enumerate(scene._r11l_ordre)}
    return sorted(pattes, key=lambda p: rang.get(_nom(p), 1 << 30))


def _recentrer(scene, k):
    corps = _pref(scene, f"roefwu-{k}")
    corps = [c for c in corps if _nom(c) == f"roefwu-{k}"]
    pattes = [p for p in _pref(scene, "roefwulewcui-") if _suffixe(p, "roefwulewcui-") == k]
    if not corps or not pattes:
        return
    c = corps[0]
    sx = sum(p["x"] + p["pixels"].shape[1] // 2 for p in pattes) // len(pattes)
    sy = sum(p["y"] + p["pixels"].shape[0] // 2 for p in pattes) // len(pattes)
    scene.placer(c, sx - c["pixels"].shape[1] // 2, sy - c["pixels"].shape[0] // 2)


def _couleurs(s):
    return {int(v) for v in np.unique(s["pixels"]) if v > 0}


def step(scene, action):
    if action[0] != "CLICK":
        return
    r, col = action[1], action[2]
    h, w = scene.vue
    k = min(int(64 / w), int(64 / h))
    xp, yp = int((64 - w * k) / 2), int((64 - h * k) / 2)
    gx = int((col - xp) / k) if col - xp >= 0 else -1
    gy = int((r - yp) / k) if r - yp >= 0 else -1
    if gx < 0 or gy < 0 or gx >= w or gy >= h:
        return
    gx, gy = gx + scene.camera[0], gy + scene.camera[1]
    pattes = _pattes(scene)
    sel = next((p for p in pattes if np.any(p["pixels"] == 0)), None)
    for p in pattes:
        ph, pw = p["pixels"].shape
        if p["x"] <= gx < p["x"] + pw and p["y"] <= gy < p["y"] + ph:  # R1 sélection
            if sel is not None:
                scene.recolorer(sel, 0, 3)
            scene.recolorer(p, 3, 0)
            return
    if sel is None:
        return
    nx, ny = gx - sel["pixels"].shape[1] // 2, gy - sel["pixels"].shape[0] // 2
    if any(_touche(sel, m, (nx, ny)) for m in _pref(scene, "wakneh-")):  # R2b mur
        return
    avant = (sel["x"], sel["y"])
    k_sel = _suffixe(sel, "roefwulewcui-")
    scene.placer(sel, nx, ny)  # R2
    _recentrer(scene, k_sel)  # R3
    vierges = [c for c in _pref(scene, "roefwu-whkxtx")]
    for c in vierges:  # R4 peinture par pot
        for pot in _pref(scene, "puukul-"):
            if _touche(c, pot):
                m = (pot["pixels"] != -1) & (pot["pixels"] != 0)
                for dy, dx in zip(*np.nonzero(m)):
                    scene.ecrire(c, int(dy), int(dx), int(pot["pixels"][dy, dx]))
                scene.retirer(pot)
    corps = _pref(scene, "roefwu-")
    danger = any(_touche(c, d) for c in corps for d in _pref(scene, "defgjl"))
    # R6 : marques de cible = cibles couvertes à la position de l'aller
    for cib in _pref(scene, "flkdtg-"):
        kk = _suffixe(cib, "flkdtg-")
        b = next((c for c in corps if _nom(c) == f"roefwu-{kk}"), None)
        if b is None:
            b = next((c for c in vierges if _touche(c, cib) and _couleurs(c) and _couleurs(c) == _couleurs(cib)), None)
        couvert = b is not None and _touche(b, cib)
        marques = [s for s in scene.sprites if _nom(s) == "flvobx-flkdtg" and (s["x"], s["y"]) == (cib["x"], cib["y"])]
        if couvert and not marques:
            scene.creer(MARQUE, cib["x"], cib["y"])
        elif not couvert:
            for mq in marques:
                scene.retirer(mq)
    if danger:  # R5 : retour arrière (pots absorbés conservés)
        scene.placer(sel, *avant)
        _recentrer(scene, k_sel)
