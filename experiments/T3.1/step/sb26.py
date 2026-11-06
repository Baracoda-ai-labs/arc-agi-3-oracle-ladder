"""T3.1 — sb26 : step(scene, action) avec les seuls effets fermés de Scene. Pas d'import du jeu.
Un coup = plusieurs images internes ; on rejoue la machine à états image par image (fondus d'un cran d'index, clignotements,
glissements interpolés) sur les sprites de la scène, puis on rend la main quand le coup est fini.
État privé : pile d'annulation, fondus en cours d'un coup à l'autre, jauge (défaite). La sélection se lit sur la scène
(contour de sélection noir). Retirer = cacher (Scene.retirer plante sur des sprites semblables)."""
import numpy as np

FOND, NOIR, VERT, ROUGE_CADRE, GRIS = 4, 0, 3, 8, 5
BRIQUE, APPEL, CASE = "lngftsryyw", "vgszefyyyp", "susublrply"
T_CADRE, T_PIECE, T_CASE = "pkpgflvjel", "lngftsryyw", "susublrply"
VERT_PX = [[3] * 6] + [[3, -1, -1, -1, -1, 3] for _ in range(4)] + [[3] * 6]
ST = {}


def _nom(s):
    return s.get("nom", "") or ""


class Sim:
    def __init__(self, scene):
        self.sc = scene
        sp = scene.sprites
        self.frames = sorted([s for s in sp if T_CADRE in s.get("tags", ())], key=lambda s: (s["y"], s["x"]))
        self.targets = sorted([s for s in sp if _nom(s) == "quhhhthrri"], key=lambda s: (s["y"], s["x"]))
        self.pieces = [s for s in sp if T_PIECE in s.get("tags", ())]
        self.cases = [s for s in sp if T_CASE in s.get("tags", ())]
        w = [s for s in sp if _nom(s) == "wrqpmmfhup"]
        self.sel = next(s for s in w if s["couche"] == 1)
        self.sel2 = next(s for s in w if s["couche"] == 0)
        self.ayai = next(s for s in w if s["couche"] == 10)
        self.cadre = next(s for s in sp if _nom(s) == "lnzhvcagos")
        self.ohv = next(s for s in sp if _nom(s) == "jkxncpvknr")
        self.echec = next(s for s in sp if _nom(s) in ("oflgslmuku", "jwaufhyryn"))
        self.idx = {id(s): i for i, s in enumerate(sp)}
        self.fades = {}
        for i, t in ST.get("fades", []):
            if i < len(sp):
                self.fades[id(sp[i])] = (sp[i], t)
        self.greens = []
        self.lqcs = None
        if self.sel["pixels"][0, 0] == NOIR:
            self.lqcs = next((p for p in self.pieces if (p["x"], p["y"]) == (self.sel["x"], self.sel["y"])), None)
        self.japg = self.lmv = self.xjx = self.bbia = self.fty = self.arts = self.jl = -1
        self.modq = 0
        self.ulz = []
        self.stack = []
        self.rz = {}
        self.pps = False
        self.pmy = 0
        self.done = False

    # ------------------------------------------------------------- primitives (effets Scene)
    def remap(self, s, c):
        px = s["pixels"]
        for u in np.unique(px[px >= 0]):
            if int(u) != c:
                self.sc.recolorer(s, int(u), int(c))

    def setpix(self, s, new):
        old = s["pixels"]
        for dy, dx in zip(*np.nonzero(old != new)):
            self.sc.ecrire(s, int(dy), int(dx), int(new[dy, dx]))

    def fade(self, s, t):
        self.fades[id(s)] = (s, t)

    def kxdel(self, s):
        self.fades.pop(id(s), None)

    def fk(self, v, width, corners=False):
        c = int(v["pixels"][0, 0])
        new = np.full_like(v["pixels"], -1)
        new[:, 0] = c
        new[:, width - 1] = c
        new[0, :width] = c
        new[-1, :width] = c
        if corners:
            k = 3
            new[k:-k, 0] = -1
            new[k:-k, width - 1] = -1
            new[0, k:width - k] = -1
            new[-1, k:width - k] = -1
        self.setpix(v, new)

    def rqtm(self, v, a, b, t, q):
        fx, fy = a["x"] - q, a["y"] - q
        tx, ty = b["x"] - q, b["y"] - q
        self.sc.placer(v, round(fx + t * (tx - fx)), round(fy + t * (ty - fy)))

    def dagv(self, v, a, b, t):
        r = 1 if v is self.cadre else 0
        self.rqtm(v, a, b, t, r)
        wa = a["pixels"].shape[1] + 2 * r
        wb = b["pixels"].shape[1] + 2 * r
        w = round(wa + t * (wb - wa))
        if v["pixels"][1, w - 1] != 1:
            self.fk(v, w, True)

    def complete(self):
        self.done = True

    # ------------------------------------------------------------- une image
    def frame(self, action):
        for k, (s, t) in list(self.fades.items()):
            p = int(s["pixels"][0, 0])
            n = p + int(np.sign(t - p))
            self.remap(s, n)
            if n == t:
                del self.fades[k]
        if self.japg >= 0:
            self.sc.montrer(self.echec, (self.japg // 3) % 2 == 0)
            self.japg += 1
            if self.japg >= 18:
                self.japg = -1
                self.bbia = 0
            return
        if self.lmv >= 0:
            self.lmv += 1
            if self.lmv > 15:
                self.lmv = -1
                self.complete()
                self.sc.niveau_suivant()
            return
        if self.xjx >= 0:
            r = self.xjx % 4
            f, c = self.stack[-1]
            tg = self.targets[self.pmy]
            col = NOIR if self.xjx < 4 else int(tg["pixels"][0, 0])
            for s in (tg, self.rz[id(f)][c]):
                for dx in range(1, s["pixels"].shape[1] - 1):
                    self.sc.ecrire(s, r + 1, dx, col)
            self.xjx += 1
            if self.xjx == 8:
                self.xjx = -1
                self.modq = 5
            return
        if self.bbia >= 0:
            r = min(self.bbia, 3)
            for tg in self.targets:
                for dx in range(1, tg["pixels"].shape[1] - 1):
                    self.sc.ecrire(tg, r + 1, dx, -1)
            if self.cadre["pixels"][0, 0] == FOND:
                self.dagv(self.cadre, self.frames[0], self.frames[0], 0)
                self.remap(self.cadre, FOND - 1)
                self.fade(self.cadre, NOIR)
            self.bbia += 1
            if self.bbia >= 8:
                self.bbia = -1
                for g in self.greens:
                    self.sc.montrer(g, False)
                self.greens.clear()
                self.sc.montrer(self.ayai, False)
                self.complete()
                if ST["jauge"] == 0:
                    self.sc.perdre()
            return
        if self.fty >= 0:
            c = ROUGE_CADRE if (self.fty // 3) % 2 == 0 else NOIR
            self.remap(self.ayai, c)
            self.remap(self.ohv, c)
            self.fty += 1
            if self.fty >= 18:
                self.fty = -1
                self.bbia = 0
                f = self.stack[-1][0]
                for s in [self.cadre, self.ayai] + self.greens:
                    if s is self.cadre and f is self.frames[0]:
                        continue
                    self.fade(s, FOND)
                self.fade(self.ohv, GRIS)
            return
        if self.ulz:
            self.jl += 1
            t = self.jl / 6
            t = 1 - (1 - t) * (1 - t)
            for s, a, b in self.ulz:
                if s is self.ohv:
                    self.rqtm(s, a, b, t, 1)
                else:
                    self.dagv(s, a, b, t)
            if self.jl == 6:
                self.ulz.clear()
                self.jl = -1
                f, c = self.stack[-1]
                p = self.rz[id(f)][c]
                self.modq = 10 if c == 0 or _nom(p) == APPEL or self.pps else 5
            return
        if self.modq > 0:
            self.modq -= 1
            if self.modq == 0:
                self.dbfx()
            return
        if self.arts >= 0:
            for v in (self.sel, self.sel2):
                self.remap(v, max(0, self.arts - 1))
            self.arts += 1
            if self.sel["pixels"][0, 0] == FOND:
                self.arts = -1
                self.complete()
                if ST["jauge"] == 0:
                    self.sc.perdre()
            return
        kind = action[0]
        if kind == "SPACE":
            ST["jauge"] -= 1
            self.sc.montrer(self.cadre, True)
            self.sc.montrer(self.sel, True)
            if self.lqcs is not None:
                self.fade(self.sel, FOND)
                self.lqcs = None
            self.rfdj()
            return
        elif kind == "UNDO":
            self.undo()
        elif kind == "CLICK":
            s = self.sprite_at(action[2], action[1])
            if s is not None:
                self.hjew(s)
                if self.arts == 0:
                    self.push()
                    return
        self.complete()

    # ------------------------------------------------------------- édition
    def sprite_at(self, x, y, tag="sys_click"):
        for s in sorted(self.sc.sprites, key=lambda s: -s["couche"]):
            if not s.get("bloquant", True) or id(s) in ST.get("morts", set()):
                continue
            h, w = s["pixels"].shape
            if s["x"] <= x < s["x"] + w and s["y"] <= y < s["y"] + h:
                if s["pixels"][y - s["y"], x - s["x"]] == -1:
                    continue
                if tag in s.get("tags", ()):
                    return s
        return None

    def rvq(self, v, x, y):
        self.sc.placer(v, x, y)
        self.remap(v, NOIR)

    def hjew(self, s):
        tags = s.get("tags", ())
        if self.lqcs is None:
            if T_PIECE in tags:
                self.lqcs = s
                self.rvq(self.sel, s["x"], s["y"])
            return
        L = self.lqcs
        if T_PIECE in tags:
            if s is L:
                self.lqcs = None
                self.remap(self.sel, FOND)
            elif L["y"] > 53 and s["y"] > 53:
                self.lqcs = s
                self.sc.placer(self.sel, s["x"], s["y"])
            else:
                ox, oy = L["x"], L["y"]
                self.rvq(self.sel2, s["x"], s["y"])
                self.sc.placer(L, s["x"], s["y"])
                self.sc.placer(s, ox, oy)
                self.arts = 0
                self.lqcs = None
                ST["jauge"] -= 1
        elif T_CASE in tags:
            pc = self.sprite_at(L["x"], L["y"], T_CASE)
            self.sc.montrer(pc, True)
            self.sc.montrer(s, False)
            self.sc.placer(L, s["x"], s["y"])
            self.arts = 0
            self.lqcs = None
            self.rvq(self.sel2, s["x"], s["y"])
            ST["jauge"] -= 1

    def etat(self):
        return [(self.idx[id(s)], s["x"], s["y"], s["visible"]) for s in self.pieces + self.cases]

    def push(self):
        ST["undo"].append(self.etat())

    def undo(self):
        if len(ST["undo"]) < 2:
            return
        self.lqcs = None
        self.remap(self.sel, FOND)
        ST["undo"].pop()
        for i, x, y, v in ST["undo"][-1]:
            s = self.sc.sprites[i]
            self.sc.placer(s, x, y)
            self.sc.montrer(s, v)

    # ------------------------------------------------------------- exécution
    def rfdj(self):
        for f in self.frames:
            lst = []
            for i in range(int(_nom(f)[-1])):
                x, y = f["x"] + 2 + i * 6, f["y"] + 2
                p = next((p for p in self.pieces if (p["x"], p["y"]) == (x, y)), None)
                if p is None:
                    p = next((c for c in self.cases if (c["x"], c["y"]) == (x, y)), None)
                if p is None:
                    raise ValueError("case introuvable")
                lst.append(p)
            self.rz[id(f)] = lst
        self.stack = [(self.frames[0], 0)]
        for v in (self.ayai, self.ohv):
            self.sc.montrer(v, True)
            self.fade(v, NOIR)
        p0 = self.rz[id(self.frames[0])][0]
        self.dagv(self.ayai, p0, p0, 0)
        self.pps = False
        self.pmy = 0
        t = self.targets[0]
        self.sc.montrer(self.ohv, True)
        self.sc.placer(self.ohv, t["x"] - 1, t["y"] - 1)
        self.modq = 15

    def sibi(self):
        self.remap(self.ayai, ROUGE_CADRE)
        self.remap(self.ohv, ROUGE_CADRE)
        self.fty = 0

    def dbfx(self):
        f, c = self.stack[-1]
        p = self.rz[id(f)][c]
        tg = self.targets[self.pmy]
        wrud = tg["pixels"][1, 1] != -1
        if not wrud and _nom(p) == BRIQUE:
            if p["pixels"][1, 1] == tg["pixels"][0, 0]:
                self.xjx = 0
            else:
                self.sibi()
            return
        if self.pmy == len(self.targets) - 1 and wrud:
            self.lmv = 0
            self.fade(self.cadre, FOND)
            self.fade(self.ayai, FOND)
            for s in self.sc.sprites:
                if _nom(s) == "uzxwqmkrmk":
                    self.fade(s, NOIR)
            return
        if self.pps or _nom(p) == BRIQUE:
            if self.pps:
                self.pps = False
                g = self.greens.pop()
                self.sc.montrer(g, False)
            c += 1
            if c < int(_nom(f)[-1]):
                self.ulz.append((self.ayai, p, self.rz[id(f)][c]))
                self.pmy += 1
                self.ulz.append((self.ohv, tg, self.targets[self.pmy]))
                self.jl = 0
                self.stack[-1] = (f, c)
            elif len(self.stack) > 1:
                self.stack.pop()
                self.pps = True
                g, c2 = self.stack[-1]
                self.ulz.append((self.cadre, f, g))
                self.ulz.append((self.ayai, p, self.rz[id(g)][c2]))
                self.jl = 0
                if len(self.greens) > 1:
                    self.fade(self.greens[-2], VERT)
            else:
                self.fade(self.cadre, FOND)
                self.fade(self.ayai, FOND)
                self.fade(self.ohv, GRIS)
                nt = self.targets[self.pmy + 1]
                px, py = nt["x"] - 1, nt["y"] - 1
                if _nom(self.echec) == "oflgslmuku":
                    self.fk(self.echec, 7 * (len(self.targets) - self.pmy - 1) + 1)
                else:
                    px -= 28
                self.sc.placer(self.echec, px, py)
                self.sc.montrer(self.echec, True)
                self.japg = 0
                return
        elif _nom(p) == APPEL:
            if c == 0 and len(self.stack) > 1 and any(a is f and b == c for a, b in self.stack[:-1]) and self.stack[-2][1] == 0:
                self.sibi()
                return
            if self.greens:
                self.fade(self.greens[-1], FOND)
            g = self.sc.creer({"nom": "upbhqnvnyx", "tags": [], "pixels": np.array(VERT_PX), "couche": 0,
                               "visible": True, "bloquant": True}, p["x"], p["y"])
            self.greens.append(g)
            col = p["pixels"][1, 1]
            h = next(fr for fr in self.frames if fr["pixels"][0, 0] == col)
            self.stack.append((h, 0))
            self.ulz.append((self.cadre, f, h))
            self.ulz.append((self.ayai, p, self.rz[id(h)][0]))
            self.jl = 0
        else:
            self.sibi()


def _frais(scene, sim):
    return (sim.ohv["x"], sim.ohv["y"]) == (-100, -100) and (sim.sel["x"], sim.sel["y"]) == (-10, -10) \
        and (sim.sel2["x"], sim.sel2["y"]) == (-10, -10)


def step(scene, action):
    sim = Sim(scene)
    sig = tuple((f["x"], f["y"]) for f in sim.frames) + tuple(int(t["pixels"][0, 0]) for t in sim.targets)
    if ST.get("sig") != sig or (ST.get("scene") != id(scene) and _frais(scene, sim)):
        ST.clear()
        ST.update(sig=sig, jauge=64, fades=[], morts=set())
        ST["undo"] = [sim.etat()]
        sim.fades = {}
    ST["scene"] = id(scene)
    if action[0] not in ("SPACE", "UNDO", "CLICK"):
        return
    for _ in range(2000):
        sim.frame(action)
        if sim.done:
            break
    ST["fades"] = [(sim.idx[k], t) for k, (s, t) in sim.fades.items() if k in sim.idx]
