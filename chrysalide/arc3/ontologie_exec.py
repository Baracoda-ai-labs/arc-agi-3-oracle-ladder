# SPDX-License-Identifier: MIT-0
"""CW-089 : interpréteur de l'ontologie T3.1 — noyau indépendant du format (rendu + rejeu + porte).
1. `rendre(scene)` : image 64×64 comme arcengine (camera.py) : fond uni h×w, sprites triés par calque (tri stable : à calque
   égal, l'ordre de la liste), pixels < 0 transparents, position relative à la caméra, agrandissement entier
   k = min(64 // w, 64 // h), bandes (letterbox) centrées. Le HUD (interfaces) n'est pas dans `rendre` : il est décrit par les
   CANEVAS de la Scene (CW-141/142, `Scene.image_complete`), lus dans les interfaces du moteur par `canevas_moteur`.
2. `scene_moteur(env)` (bancs seulement) : la scène lue dans le moteur, pour valider le rendu contre le vrai rendu sans HUD.
Le format des descriptions de jeux (bloc JSON de B) se branchera sur `rendre` : entités + état → scène."""
import copy

import numpy as np


def rendre(scene):
    h, w = scene["vue"]
    vue = np.full((h, w), scene["fond"], dtype=np.int16)
    cx, cy = scene.get("camera", (0, 0))
    for s in sorted(scene["sprites"], key=lambda s: s["couche"]):  # sorted est stable
        px = np.asarray(s["pixels"], dtype=np.int16)
        sh, sw = px.shape
        rx, ry = s["x"] - cx, s["y"] - cy
        x0, x1, y0, y1 = max(0, rx), min(w, rx + sw), max(0, ry), min(h, ry + sh)
        if x1 <= x0 or y1 <= y0:
            continue
        reg = px[y0 - ry:y1 - ry, x0 - rx:x1 - rx]
        m = reg >= 0
        vue[y0:y1, x0:x1][m] = reg[m]
    k = min(64 // w, 64 // h)
    out = np.full((64, 64), scene["letterbox"], dtype=np.int16)
    gy, gx = (64 - h * k) // 2, (64 - w * k) // 2
    out[gy:gy + h * k, gx:gx + w * k] = np.repeat(np.repeat(vue, k, 0), k, 1) if k > 1 else vue
    return out


# ---------------------------------------------------------------- canevas (écran interne dessiné dans l'interface, CW-141/142)
# Un canevas = dict {"nom", "pixels" (grille de cases H×W, int16, −1 transparent), "x", "y" (origine de la case (0, 0) dans
# l'image 64×64, négative si la 1re case déborde), "kx", "ky" (taille d'une case en pixels)}. Les clés pixels/x/y rendent
# les accesseurs largeur/hauteur/x/y/pixel du langage utilisables tels quels. Dessiné APRÈS la vue mise à l'échelle et le
# letterbox, dans l'ordre de la liste, comme `camera._interfaces` du moteur (camera.render).
K_MAX = 8  # plus grande taille de case cherchée par `geometrie_canevas`


def nouveau_canevas(nom, pixels, x=0, y=0, kx=1, ky=None):
    return {"nom": nom, "pixels": np.asarray(pixels, dtype=np.int16).copy(), "x": int(x), "y": int(y), "kx": int(kx),
            "ky": int(kx if ky is None else ky)}


def copier_canevas(cs):
    return [dict(c, pixels=np.asarray(c["pixels"], dtype=np.int16).copy()) for c in cs or ()]


def dessiner_canevas(out, canevas):
    """Peint chaque canevas sur l'image 64×64 `out` (modifiée et rendue) : case (i, j) de valeur ≥ 0 → rectangle
    [y + i·ky, y + (i+1)·ky) × [x + j·kx, x + (j+1)·kx), découpé au cadre ; cases < 0 transparentes."""
    for c in canevas or ():
        px = c["pixels"]
        if type(px) is not np.ndarray or px.dtype != np.int16:
            px = np.asarray(px, dtype=np.int16)
        kx, ky = c["kx"], c["ky"]
        if px.size == 0 or kx < 1 or ky < 1:
            continue
        g = np.repeat(np.repeat(px, ky, 0), kx, 1) if (kx > 1 or ky > 1) else px
        x0, y0 = c["x"], c["y"]
        gh, gw = g.shape
        a0, a1, b0, b1 = max(0, y0), min(64, y0 + gh), max(0, x0), min(64, x0 + gw)
        if a1 <= a0 or b1 <= b0:
            continue
        reg = g[a0 - y0:a1 - y0, b0 - x0:b1 - x0]
        np.copyto(out[a0:a1, b0:b1], reg, where=reg >= 0)
    return out


def geometrie_canevas(calque):
    """HYPOTHÈSE (documentée, LANGAGE.md) : l'interface dessine une grille de cases unies de côté k. On cherche le plus grand
    k ≤ K_MAX et le plus petit décalage (ox, oy) tels que CHAQUE bloc k×k de l'image (−1 compris, blocs coupés au bord
    compris) soit d'une seule couleur ; sinon k = 1 (case = pixel, toujours exact). Puis on retire les rangées/colonnes
    entièrement transparentes du bord. Rend (pixels, x, y, k) ; dessiner_canevas le redonne au pixel près."""
    calque = np.asarray(calque, dtype=np.int16)
    h, w = calque.shape
    for k in range(K_MAX, 1, -1):
        for oy in range(k):
            for ox in range(k):
                x0, y0 = (ox - k if ox else 0), (oy - k if oy else 0)
                gw, gh = -(-(w - x0) // k), -(-(h - y0) // k)
                p = np.full((gh * k, gw * k), -32000, dtype=np.int16)
                p[-y0:-y0 + h, -x0:-x0 + w] = calque
                b = p.reshape(gh, k, gw, k).swapaxes(1, 2).reshape(gh, gw, k * k)
                hi = b.max(axis=2)
                lo = np.where(b == -32000, np.int16(32000), b).min(axis=2)
                if np.array_equal(hi, lo):
                    return _rogner(lo, x0, y0, k)
    return _rogner(calque, 0, 0, 1)


def _rogner(g, x0, y0, k):
    ys, xs = np.nonzero(g >= 0)
    if ys.size == 0:
        return np.zeros((0, 0), dtype=np.int16), 0, 0, 1
    i0, i1, j0, j1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    return g[i0:i1, j0:j1].copy(), int(x0 + j0 * k), int(y0 + i0 * k), k


def regriller(calque, ancien):
    """Le calque (64×64, −1 transparent) dans la géométrie d'un canevas existant, si elle le redonne EXACTEMENT ; sinon None."""
    kx, ky, x0, y0 = ancien["kx"], ancien["ky"], ancien["x"], ancien["y"]
    h, w = np.asarray(ancien["pixels"]).shape
    ys, xs = np.nonzero(np.asarray(calque) >= 0)
    if ys.size and (ys.min() < max(0, y0) or ys.max() >= y0 + h * ky or xs.min() < max(0, x0) or xs.max() >= x0 + w * kx):
        return None
    cy = np.clip(y0 + np.arange(h) * ky, 0, 63)  # échantillon : 1er pixel visible de chaque case
    cx = np.clip(x0 + np.arange(w) * kx, 0, 63)
    g = np.asarray(calque, dtype=np.int16)[np.ix_(cy, cx)]
    n = nouveau_canevas(ancien["nom"], g, x0, y0, kx, ky)
    vide = np.full((64, 64), -1, dtype=np.int16)
    return n if np.array_equal(dessiner_canevas(vide, [n]), np.asarray(calque, dtype=np.int16)) else None


def _dans(c, x, y):
    h, w = c["pixels"].shape
    return 0 <= x < w and 0 <= y < h


def case_canevas(c, x, y):
    return int(c["pixels"][y, x]) if c is not None and _dans(c, x, y) else None


def cases_de(c, couleur):
    """[[x, y], …] des cases de cette couleur, ordre de lecture (rangée par rangée)."""
    if c is None:
        return []
    ys, xs = np.nonzero(c["pixels"] == couleur)
    return [[int(x), int(y)] for y, x in zip(ys.tolist(), xs.tolist(), strict=True)]


def composantes_canevas(c, filtre=None):
    """Objets DÉRIVÉS (dicts, recalculés à chaque appel) : composantes connexes de cases opaques de même couleur.
    filtre : {"couleur": v | [v…], "connexite": 4 (défaut) | 8}. Objet = {"x", "y" (coin haut-gauche, en cases),
    "largeur", "hauteur", "couleur", "cases": [[x, y]…], "pixels" (boîte : couleur / −1), "canevas": nom} ; ordre : 1re
    case en ordre de lecture."""
    from scipy import ndimage
    if c is None:
        return []
    f = filtre or {}
    px = np.asarray(c["pixels"])
    cols = f.get("couleur")
    present = np.unique(px[px >= 0]).tolist()
    cols = present if cols is None else [v for v in present if v in set(cols if isinstance(cols, list) else [cols])]
    struct = np.ones((3, 3), dtype=bool) if f.get("connexite") == 8 else None  # None : 4-connexité
    trouves = []
    for v in cols:
        lab, n = ndimage.label(px == v, structure=struct)
        if not n:
            continue
        plat = lab.ravel()
        idx = np.nonzero(plat)[0]  # ordre de lecture
        ordre = np.argsort(plat[idx], kind="stable")
        groupes = np.split(idx[ordre], np.cumsum(np.bincount(plat[idx])[1:])[:-1])
        trouves.extend((int(g[0]), v, g) for g in groupes)
    out = []
    w = px.shape[1]
    for _, v, g in sorted(trouves, key=lambda t: t[0]):
        ys, xs = g // w, g % w
        bx, by = int(xs.min()), int(ys.min())
        boite = np.full((int(ys.max()) - by + 1, int(xs.max()) - bx + 1), -1, dtype=np.int16)
        boite[ys - by, xs - bx] = v
        out.append({"x": bx, "y": by, "largeur": boite.shape[1], "hauteur": boite.shape[0], "couleur": int(v),
                    "cases": [[int(x), int(y)] for y, x in zip(ys.tolist(), xs.tolist(), strict=True)], "pixels": boite,
                    "canevas": c.get("nom")})
    return out


def clic_vers_case(canevas, r, col, c=None):
    """Case [x, y] du canevas `c` (défaut : le plus haut dessiné dont la grille contient le pixel) sous le pixel (ligne r,
    colonne col) de l'image 64×64 ; None hors canevas."""
    for cv in ([c] if c is not None else list(reversed(canevas or []))):
        if cv is None:
            continue
        x, y = (col - cv["x"]) // cv["kx"], (r - cv["y"]) // cv["ky"]
        if _dans(cv, x, y):
            return [int(x), int(y)]
    return None


def _rect(c, x, y, lg, ht):
    h, w = c["pixels"].shape
    return max(0, y), min(h, y + ht), max(0, x), min(w, x + lg)


def _echelle_xy(e):
    return (e[0], e[1]) if isinstance(e, (list, tuple)) else (e, e)


def _reduire_mode(px, fy, fx):
    """Réduction de arcengine `_downscale_mode`, étendue à fy ≠ fx : par bloc fy×fx, couleur dominante (égalité → plus grand
    indice) ; transparent (-1) si les pixels < 0 sont plus nombreux que les pixels != -1. Un -2 dans un bloc retenu fait
    planter le moteur (bincount négatif) : on refuse de même."""
    h, w = px.shape
    if h % fy or w % fx:
        raise ValueError(f"dimensions ({h}, {w}) non divisibles par ({fy}, {fx})")
    blocs = px.reshape(h // fy, fy, w // fx, fx).swapaxes(1, 2).reshape(-1, fy * fx)
    out = np.empty(len(blocs), dtype=px.dtype)
    for i, b in enumerate(blocs):
        opaques, transp = b[b != -1], b[b < 0]
        if transp.size > opaques.size:
            out[i] = -1
        else:
            if (opaques < 0).any():
                raise ValueError("pixel -2 dans un bloc réduit (le moteur plante aussi)")
            n = np.bincount(opaques.astype(np.int64))
            out[i] = np.nonzero(n == n.max())[0][-1]
    return out.reshape(h // fy, w // fx)


def scene_moteur(env):
    """Scène du moteur (oracle, bancs) + image du moteur SANS HUD, pour valider `rendre`."""
    jeu = env._game
    cam = jeu.camera
    sprites = jeu.current_level.get_sprites()
    scene = {"vue": (cam._height, cam._width), "fond": int(cam._background), "letterbox": int(cam._letter_box),
             "camera": (cam._x, cam._y),
             "sprites": [{"pixels": np.asarray(s.render()), "x": s.x, "y": s.y, "couche": s.layer} for s in sprites if s.is_visible]}
    interfaces, cam._interfaces = cam._interfaces, []
    try:
        sans_hud = np.asarray(cam.render(sprites), dtype=np.int16)
    finally:
        cam._interfaces = interfaces
    return scene, sans_hud


# ---------------------------------------------------------------- couche 0 exécutable : effets fermés (ONTOLOGIE.md)
class Scene:
    """État exécutable d'un niveau, au niveau des sprites. Les EFFETS sont l'ensemble fermé de la couche 0 de B :
    déplacer, tourner (90°), recolorer, réécrire des pixels, montrer/cacher, changer de calque, créer, retirer ; et, au niveau
    du jeu, niveau suivant, gagner, perdre. Une règle de l'ontologie = condition (Python sur la scène) → liste d'effets.
    Les causes (quand une règle s'applique) restent ouvertes : c'est ce que décrit chaque jeu."""

    def __init__(self, vue, fond, letterbox, sprites, camera=(0, 0), donnees=None, modeles=None, n_niveaux=None,
                 niveau=None, canevas=None):
        self.vue, self.fond, self.letterbox, self.camera = vue, fond, letterbox, camera
        self.canevas = copier_canevas(canevas)  # écrans internes (liste ordonnée = ordre de dessin), voir dessiner_canevas
        self.sprites = [dict(s, pixels=np.asarray(s["pixels"], dtype=np.int16).copy(), visible=s.get("visible", True))
                        for s in sprites]
        self.issue = None  # None | "niveau" | "victoire" | "defaite"
        self.debut = True  # scène neuve (départ, niveau suivant, RESET) : le langage le consomme au 1er coup (debut_niveau)
        self.donnees = donnees or {}  # données du niveau courant (arcengine Level.get_data), non dessinées
        self.modeles = modeles or {}  # catalogue des formes du jeu : nom → pixels d'origine (sans rotation ni échelle)
        self.n_niveaux, self.niveau = n_niveaux, niveau  # n_niveaux None = inconnu (niveau_suivant ne gagne jamais)

    # requêtes
    def par_tag(self, tag):
        return [s for s in self.sprites if tag in s.get("tags", ())]

    def a(self, x, y):
        """Sprites visibles dont un pixel opaque couvre la case (x, y) de la vue, du calque le plus haut au plus bas."""
        out = []
        for s in sorted(self.sprites, key=lambda s: -s["couche"]):
            px, dx, dy = s["pixels"], x - s["x"], y - s["y"]
            if s["visible"] and 0 <= dy < px.shape[0] and 0 <= dx < px.shape[1] and px[dy, dx] >= 0:
                out.append(s)
        return out

    def dans_boite(self, x, y, l, h):
        """Mot `dans_boite` (CCM-159-B) : sprites dont la boîte (x, y, largeur, hauteur) est incluse dans [x, x+l) × [y, y+h),
        opaques ou non, visibles ou non, du calque le plus haut au plus bas (même ordre que `a`)."""
        out = []
        for s in sorted(self.sprites, key=lambda s: -s["couche"]):
            ph, pw = np.asarray(s["pixels"]).shape[:2]
            if s["x"] >= x and s["y"] >= y and s["x"] + pw <= x + l and s["y"] + ph <= y + h:
                out.append(s)
        return out

    # effets (fermés)
    def deplacer(self, s, dx, dy):
        s["x"], s["y"] = s["x"] + dx, s["y"] + dy

    def placer(self, s, x, y):
        s["x"], s["y"] = x, y

    def tourner(self, s, quarts=1):
        s["pixels"] = np.rot90(s["pixels"], -quarts).copy()
        if "cache" in s:  # rotation du moteur (degrés, sens horaire) tenue à jour pour poser_motif / attr_cache
            s["cache"]["rotation"] = (s["cache"].get("rotation", 0) + 90 * quarts) % 360

    def poser_motif(self, s, motif):
        """`sprite.pixels = motif` du moteur : motif d'ORIGINE (liste de listes ou forme_modele), auquel on applique la
        rotation, les miroirs (`cache`) et l'échelle courants de s, comme `Sprite.render`. Position inchangée."""
        if motif is None:
            return
        px = np.asarray(motif, dtype=np.int16)
        c = s.get("cache", {})
        k = int((-c.get("rotation", 0) % 360) / 90)
        px = np.rot90(px, k) if k else px
        px = np.flipud(px) if c.get("mirror_ud") else px
        px = np.fliplr(px) if c.get("mirror_lr") else px
        e = s.get("echelle", 1)
        s.pop("base", None)
        s["pixels"], s["echelle"] = px.copy(), 1
        if e != 1:
            self.remodeler(s, *_echelle_xy(e))

    def poser_bloquant(self, s, b=True):
        """`set_collidable` du moteur : lu par bloquant(o) et contact_moteur."""
        s["bloquant"] = bool(b)

    def rendre_intangible(self, s):
        self.poser_bloquant(s, False)

    def recolorer(self, s, ancienne, nouvelle):
        s["pixels"] = s["pixels"].copy()  # copie à l'écriture : `sim_rapide.cloner` partage les pixels entre clones
        s["pixels"][s["pixels"] == ancienne] = nouvelle
        if "base" in s:  # motif d'origine gardé par remodeler (réduction) : même recoloriage
            s["base"][s["base"] == ancienne] = nouvelle

    def remodeler(self, s, ex, ey=None):
        """Échelle du sprite comme arcengine `set_scale` (`Sprite.render`) : k >= 1 agrandit (chaque pixel → bloc k×k),
        k <= -1 réduit d'un facteur -k+1 (mode du bloc, égalité → plus grand indice, bloc majoritairement transparent → -1).
        `pixels` reste l'image RENDUE (ce que `rendre` dessine) ; l'échelle courante est `s["echelle"]` (1 par défaut, lue dans
        le moteur par `scene_initiale_moteur`). Le motif d'origine se retrouve exactement en sous-échantillonnant une échelle
        >= 1 ; après une réduction il est gardé dans `s["base"]`. ey (défaut ex) : échelle verticale (le moteur n'a que ex = ey).
        Le sprite ne bouge pas (set_scale ne touche pas x, y)."""
        ey = ex if ey is None else ey
        if 0 in (ex, ey):
            raise ValueError("échelle 0 interdite (arcengine)")
        cx, cy = _echelle_xy(s.get("echelle", 1))
        if "base" in s:
            base = s["base"]
        elif cx >= 1 and cy >= 1:
            base = s["pixels"][::cy, ::cx]
        else:
            raise ValueError("motif d'origine inconnu : sprite déjà réduit sans base")
        px = base
        if ey > 1 or ex > 1:
            px = np.repeat(np.repeat(px, max(ey, 1), 0), max(ex, 1), 1)
        if ey < 0 or ex < 0:
            px = _reduire_mode(px, -ey + 1 if ey < 0 else 1, -ex + 1 if ex < 0 else 1)
        s["pixels"] = np.asarray(px, dtype=np.int16).copy()
        s["echelle"] = ex if ex == ey else [ex, ey]
        if ex < 0 or ey < 0:
            s["base"] = np.asarray(base, dtype=np.int16).copy()
        else:
            s.pop("base", None)

    def ecrire(self, s, dy, dx, couleur):
        s["pixels"] = s["pixels"].copy()  # copie à l'écriture (voir recolorer)
        s["pixels"][dy, dx] = couleur

    def montrer(self, s, visible=True):
        s["visible"] = visible

    def calque(self, s, couche):
        s["couche"] = couche

    def creer(self, modele, x, y, **attrs):
        n = dict(modele, pixels=np.asarray(modele["pixels"]).copy(), x=x, y=y, **attrs)
        for k in ("attrs", "cache"):  # copie propre : poser_attr / tourner sur la copie ne touchent pas le modèle
            if k in n:
                n[k] = dict(n[k])
        n.setdefault("visible", True)
        self.sprites.append(n)
        return n

    def retirer(self, s):
        """Par IDENTITÉ (correctif CCM-065-B) : `list.remove` comparait des dicts contenant des tableaux numpy."""
        self.sprites = [t for t in self.sprites if t is not s]

    def dernier_niveau(self):
        return self.n_niveaux is not None and self.niveau == self.n_niveaux - 1

    def niveau_suivant(self):
        """Comme arcengine `next_level` : au dernier niveau, c'est la victoire."""
        self.issue = "victoire" if self.dernier_niveau() else "niveau"

    def gagner(self):
        self.issue = "victoire"

    def perdre(self):
        self.issue = "defaite"

    def image(self):
        """Image SANS interface (sprites seuls) : ce que compare le banc sans HUD."""
        return rendre({"vue": self.vue, "fond": self.fond, "letterbox": self.letterbox, "camera": self.camera,
                       "sprites": [s for s in self.sprites if s["visible"]]})

    def image_complete(self):
        """Image AVEC interface : sprites, puis canevas par-dessus (comme camera.render puis render_interface)."""
        return dessiner_canevas(self.image(), self.canevas)

    # canevas (CW-141/142) : effets sur la grille de cases ; canevas None = effet ignoré (comme un objet absent)
    def canevas_nomme(self, nom=None):
        if nom is None:
            return self.canevas[0] if self.canevas else None
        return next((c for c in self.canevas if c["nom"] == nom), None)

    def ecrire_case(self, c, x, y, couleur):
        if c is not None and _dans(c, x, y):
            c["pixels"][y, x] = couleur

    def remplir(self, c, x, y, lg, ht, couleur):
        if c is not None:
            a0, a1, b0, b1 = _rect(c, x, y, lg, ht)
            if a1 > a0 and b1 > b0:
                c["pixels"][a0:a1, b0:b1] = couleur

    def deplacer_bloc(self, c, x, y, lg, ht, dx, dy, fond=-1):
        """Le bloc lg×ht en (x, y) (découpé à la grille) part en (x+dx, y+dy) : sa place prend `fond` (−1 = transparent),
        puis ses cases OPAQUES sont peintes à l'arrivée (découpées à la grille ; les transparentes n'effacent rien)."""
        if c is None:
            return
        a0, a1, b0, b1 = _rect(c, x, y, lg, ht)
        if a1 <= a0 or b1 <= b0:
            return
        px = c["pixels"]
        bloc = px[a0:a1, b0:b1].copy()
        px[a0:a1, b0:b1] = fond
        h, w = px.shape
        d0, d1, e0, e1 = max(0, a0 + dy), min(h, a1 + dy), max(0, b0 + dx), min(w, b1 + dx)
        if d1 > d0 and e1 > e0:
            reg = bloc[d0 - a0 - dy:d1 - a0 - dy, e0 - b0 - dx:e1 - b0 - dx]
            np.copyto(px[d0:d1, e0:e1], reg, where=reg >= 0)

    def poser_geometrie(self, c, x0, y0, k, ky=None):
        """Affichage du canevas : origine (x0, y0) dans l'image 64×64 et taille de case k (ky : hauteur, défaut k). La grille
        ne change pas (zoom/défilement de l'écran interne). k < 1 refusé (ignoré)."""
        if c is not None and k >= 1 and (ky is None or ky >= 1):
            c["x"], c["y"], c["kx"], c["ky"] = int(x0), int(y0), int(k), int(k if ky is None else ky)


def calques_interface(env):
    """Ce que CHAQUE interface du moteur (`camera._interfaces`, dessinées après les sprites) ajoute à l'image sans HUD :
    liste de calques 64×64 (−1 = pixel non écrit). Rendu sur des COPIES des interfaces (le jeu lui-même partagé, non copié :
    `render_interface` peut consommer une file d'images d'animation) et sur deux fonds différents : un pixel est écrit s'il
    diffère du fond pour l'un des deux (hypothèse : l'interface ne mélange pas sa couleur avec le fond)."""
    from chrysalide.arc3.copie import copie_profonde
    jeu = env._game
    cam = jeu.camera
    if not cam._interfaces:
        return []
    interfaces, cam._interfaces = cam._interfaces, []
    try:
        base = np.asarray(cam.render(jeu.current_level.get_sprites()), dtype=np.int8)
    finally:
        cam._interfaces = interfaces
    fonds = [base.copy(), ((base.astype(np.int16) + 1) % 16).astype(np.int8)]
    copies = [copie_profonde(list(interfaces), {id(jeu): jeu, id(cam): cam}) for _ in fonds]
    calques = []
    for i in range(len(interfaces)):
        sorties = []
        for f, cs in zip(fonds, copies, strict=True):
            avant = f.copy()
            f2 = np.asarray(cs[i].render_interface(f), dtype=np.int8)
            sorties.append((avant, f2))
            f[...] = f2
        ecrit = np.zeros((64, 64), dtype=bool)
        for avant, apres in sorties:
            ecrit |= apres != avant
        calques.append(np.where(ecrit, sorties[0][1], -1).astype(np.int16))
    return calques


def canevas_moteur(env, anciens=None):
    """Un canevas par interface du moteur (« interface », « interface1 », …). Géométrie : celle de l'ancien canevas de même
    nom si elle redonne exactement le calque (resynchronisation en cours de niveau : la géométrie reste stable), sinon
    `geometrie_canevas`."""
    out = []
    vieux = {c["nom"]: c for c in anciens or ()}
    for i, cal in enumerate(calques_interface(env)):
        nom = "interface" if i == 0 else f"interface{i}"
        n = regriller(cal, vieux[nom]) if nom in vieux else None
        if n is None:
            g, x, y, k = geometrie_canevas(cal)
            n = nouveau_canevas(nom, g, x, y, k)
        out.append(n)
    return out


def scene_initiale_moteur(env, canevas=True, anciens_canevas=None):
    """`etat_initial: "moteur"` (CW-092) : la scène du niveau courant lue dans le moteur — pour la MESURE d'exhaustivité
    seulement, jamais pour l'agent (qui tient l'état de la perception). Tags, noms et calques compris ; `canevas` : lit aussi
    ce que dessinent les interfaces du moteur (voir canevas_moteur)."""
    jeu, cam = env._game, env._game.camera
    niv = jeu.current_level
    sprites = [{"nom": s.name, "tags": list(s.tags), "pixels": np.asarray(s.render()), "x": s.x, "y": s.y, "couche": s.layer,
                "visible": bool(s.is_visible), "bloquant": bool(s.is_collidable), "echelle": int(s.scale),
                "blocage": s._blocking.name,
                "cache": {"rotation": int(s.rotation), "mirror_ud": bool(s.mirror_ud), "mirror_lr": bool(s.mirror_lr)}}
               for s in niv.get_sprites()]
    return Scene((cam._height, cam._width), int(cam._background), int(cam._letter_box), sprites, (cam._x, cam._y),
                 donnees=copy.deepcopy(niv._data or {}), modeles=catalogue_moteur(jeu), n_niveaux=len(jeu._levels),
                 niveau=jeu._current_level_index, canevas=canevas_moteur(env, anciens_canevas) if canevas else None)


def catalogue_moteur(jeu):
    """Formes du jeu, nom → pixels d'origine : le dictionnaire `sprites` du module du jeu (modèles placés ou non, convention
    des jeux ARC-AGI-3), complété par les sprites du niveau courant absents du dictionnaire."""
    cat = {}
    glob = getattr(type(jeu).__init__, "__globals__", {})
    for nom, s in (glob.get("sprites") or {}).items() if isinstance(glob.get("sprites"), dict) else ():
        if hasattr(s, "pixels"):
            cat[str(nom)] = np.asarray(s.pixels)
    for s in jeu.current_level.get_sprites():
        cat.setdefault(s.name, np.asarray(s.pixels))
    return cat
