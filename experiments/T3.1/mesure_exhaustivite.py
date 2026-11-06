"""CW-084/089 : score d'exhaustivité de l'ontologie = transitions (et jeux) reproduits AU PIXEL contre le vrai moteur.
Pour chaque jeu non témoin : la scène initiale de chaque niveau est lue dans le moteur (`etat_initial: "moteur"`, mesure
seulement) ; `experiments/T3.1/step/<jeu>.py` doit définir `step(scene, action)` n'utilisant QUE les effets fermés de
`ontologie_exec.Scene` (déplacer, tourner, recolorer, écrire, montrer, calque, créer, retirer, niveau_suivant, gagner,
perdre). Sans fichier : témoin « aucune règle » (identité). Comparaison 1 : image de la scène contre image moteur SANS HUD.
Comparaison 2 (« honnête ») : image sans HUD ET état de tous les sprites (cachés compris) ET, si le programme emploie un
canevas (CW-141/142), IMAGE COMPLÈTE interface comprise (`Scene.image_complete`, canevas lus dans les interfaces du moteur)
ET état caché du moteur (`_get_hidden_state`, comparé à `scene.etat_cache` si
déclaré ; sinon tout changement d'état caché est non expliqué, donc faux). Le témoin identité est rejoué à côté sur la
comparaison 2 (image complète comprise pour un programme à canevas) : témoin ≥ 99 % ⇒ `a_vide`, et un jeu à vide ne compte
pas comme reproduit (lf52 sans canevas était à vide : jeu dessiné dans le HUD).
Langage T3.2 : si `experiments/T3.1/regles/<jeu>.json` existe, il est exécuté par `chrysalide/arc3/langage.py` (prioritaire).
Option `mesurer(…, avec_distracteurs=True)` (OneLife) : rang du vrai état suivant parmi les états atteints depuis le même
état par les autres actions (vrai moteur, copie profonde, ≤ 8), selon la distance pixel à la prédiction (cf. `rang`).
Traces et moteurs (non versionnés) lus sous $CHRYSALIDE_DONNEES (défaut : racine du dépôt).
Usage : uv run python experiments/T3.1/mesure_exhaustivite.py [jeux…]  → experiments/T3.1/exhaustivite.json"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "experiments/T2.12"))
from arc_agi import Arcade, OperationMode
from arcengine.enums import GameAction
from fidelite import NUM, evenements

from chrysalide.arc3.copie import copie_profonde
from chrysalide.arc3.ontologie_exec import scene_initiale_moteur, scene_moteur
from chrysalide.arc3.recherche import _etat_cache

TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
ICI = Path(__file__).parent
DONNEES = Path(os.environ.get("CHRYSALIDE_DONNEES", RACINE))
SEUIL_A_VIDE = 0.99


def a_vide(taux_temoin):
    """Le banc passe « à vide » quand le témoin « aucune règle » fait déjà ≥ 99 % : un 100 % n'y prouve rien."""
    return taux_temoin is not None and taux_temoin >= SEUIL_A_VIDE


def charger_step(jeu):
    r = ICI / "regles" / f"{jeu}.json"  # T3.2 : la description dans le LANGAGE l'emporte sur le step() Python de référence
    if r.exists():
        from chrysalide.arc3.langage import Programme, utilise_canevas
        texte = json.loads(r.read_text())
        prog = Programme(texte)
        step = lambda scene, action: prog.step(scene, action)
        step.canevas = utilise_canevas(texte)  # programme à canevas : banc sur l'image complète (interface comprise)
        return step, r.name
    f = ICI / "step" / f"{jeu}.py"
    if not f.exists():
        return None, "identité"
    spec = importlib.util.spec_from_file_location(f"step_{jeu}", f)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.step, f.name


def action_de(e):
    nom = e.get("action_name", "")
    if nom == "ACTION6":
        aff = e["action_display"]
        r, c = (int(x.split("=")[1]) for x in aff[aff.index("(") + 1:-1].split(", "))
        return ("CLICK", r, c)
    return ({1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 7: "UNDO", 0: "RESET"}[NUM[nom]], None, None)


def _resync(env, ancienne, canevas=False):
    """Nouvelle scène lue dans le moteur, en GARDANT les attributs posés par les règles (CCM-068-B) : appariement par
    (nom, rang parmi les sprites de même nom). `canevas` : lit aussi les interfaces du moteur (géométrie des canevas de
    l'ancienne scène gardée si elle reste exacte)."""
    s = scene_initiale_moteur(env, canevas=canevas, anciens_canevas=getattr(ancienne, "canevas", None))
    s.niveau = env._game._current_level_index
    if ancienne is not None:
        s.debut = ancienne.debut  # resynchronisation en cours de niveau : ce n'est pas un début de niveau
        rang, vieux = {}, {}
        for o in ancienne.sprites:
            k = (o.get("nom"), rang.setdefault(o.get("nom"), [0])[0])
            rang[o.get("nom")][0] += 1
            if o.get("attrs"):
                vieux[k] = o["attrs"]
        rang = {}
        for o in s.sprites:
            k = (o.get("nom"), rang.setdefault(o.get("nom"), [0])[0])
            rang[o.get("nom")][0] += 1
            if k in vieux:
                o["attrs"] = dict(vieux[k])
    return s


def _cles_sprites(sprites, vue, camera):
    """Sprites VISIBLES touchant la vue : (nom, x, y, calque, pixels). Les sprites cachés ou hors vue sont libres (la
    Scene peut cacher au lieu de retirer, ou garder une mémoire hors champ : choix de modélisation, pas une erreur) ;
    ce canal attrape en plus de l'image : identité et calque des sprites, sprites recouverts ou de la couleur du fond."""
    (h, w), (cx, cy), out = vue, camera, []
    for nom, x, y, couche, px in sprites:
        px = np.asarray(px, dtype=np.int16)
        if x < cx + w and y < cy + h and x + px.shape[1] > cx and y + px.shape[0] > cy:
            out.append((str(nom), int(x), int(y), int(couche), px.shape, px.tobytes()))
    return sorted(out)


def etat_moteur(env):
    """État déclaré par le moteur : sprites (cf. `_cles_sprites`) + état caché `_get_hidden_state`."""
    cam = env._game.camera
    sprites = [(s.name, s.x, s.y, s.layer, s.render()) for s in env._game.current_level.get_sprites() if s.is_visible]
    return _cles_sprites(sprites, (cam._height, cam._width), (cam._x, cam._y)), _etat_cache(env._game)


def etat_scene(scene):
    sprites = [(o.get("nom"), o["x"], o["y"], o["couche"], o["pixels"]) for o in scene.sprites if o.get("visible", True)]
    return _cles_sprites(sprites, scene.vue, scene.camera)


def juger(scene, step, a, vrai, complet=False):
    """Un coup prédit par `step` (None = témoin identité) contre `vrai` = dict(image, complet, sprites, cache,
    cache_change). `complet` (programme à canevas) : le canal honnête exige aussi l'IMAGE COMPLÈTE, interface comprise
    (`Scene.image_complete` = sprites + canevas) égale à la dernière image du moteur. Renvoie (image_ok, honnete_ok,
    erreur, pixels_faux, image_predite)."""
    try:
        if step is not None:
            step(scene, a)
        predit = scene.image()
    except Exception as x:  # noqa: BLE001 — une règle qui plante est une transition fausse
        return False, False, f"{type(x).__name__}: {x}"[:100], None, None
    img = bool(np.array_equal(predit, vrai["image"]))
    ok = img and etat_scene(scene) == vrai["sprites"]
    if ok and complet:  # (a) image avec HUD : seulement quand le programme décrit l'interface (canevas)
        ok = bool(np.array_equal(scene.image_complete(), vrai["complet"]))
    cache = getattr(scene, "etat_cache", None)
    if ok:
        ok = (_etat_cache_de(cache) == vrai["cache"]) if cache is not None else not vrai["cache_change"]
    return img, ok, None, int((predit != vrai["image"]).sum()), predit


def distance(a, b):
    """Pixels différents entre deux images sans HUD ; formes différentes = toutes les cases fausses."""
    if a is None or b is None:
        return float("inf")
    a, b = np.asarray(a), np.asarray(b)
    return int((a != b).sum()) if a.shape == b.shape else max(a.size, b.size)


def rang(d_vrai, d_distracteurs):
    """Rang (1 = premier) du vrai état suivant parmi lui et les distracteurs, selon la distance à la prédiction.
    Égalités PESSIMISTES : tout distracteur à distance ≤ celle du vrai passe devant."""
    return 1 + sum(d <= d_vrai for d in d_distracteurs)


def distracteurs(jeu_avant, a, vraie, cle, n_max=8):
    """Images sans HUD obtenues dans le VRAI moteur depuis l'état avant le coup (copie profonde) avec les AUTRES actions
    disponibles ; clics : candidats du moteur (ou centres de sprites) tirés au hasard (graine = `cle`), sinon cases au
    hasard. Dédupliquées et différentes de la vraie image suivante. ≤ n_max actions essayées."""
    import random

    from arcengine import ActionInput

    from chrysalide.arc3.recherche import _coups, _sans_hud
    dispo = [int(x) for x in jeu_avant._available_actions if int(x) != 0]
    vrai_id = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5, "CLICK": 6, "UNDO": 7}.get(a[0], 0)
    essais = [ActionInput(id=GameAction.from_id(k)) for k in dispo if k != 6 and k != vrai_id][:n_max]
    if 6 in dispo and len(essais) < n_max:
        rng = random.Random(cle)
        vu = {(a[2], a[1])} if a[0] == "CLICK" else set()
        cand = [(c.data["x"], c.data["y"]) for c in _coups(jeu_avant) if int(c.id.value) == 6 and c.data]
        cand = [xy for xy in dict.fromkeys(cand) if xy not in vu]
        rng.shuffle(cand)
        while len(cand) < n_max:
            cand.append((rng.randrange(64), rng.randrange(64)))
        for x, y in cand:
            if len(essais) >= n_max:
                break
            if (x, y) not in vu:
                vu.add((x, y))
                essais.append(ActionInput(id=GameAction.ACTION6, data={"x": x, "y": y}))
    vues, out = {np.asarray(vraie).tobytes() + bytes(str(np.shape(vraie)), "ascii")}, []
    for ai in essais:
        g = copie_profonde(jeu_avant)
        try:
            g.perform_action(ai, raw=True)
            im = _sans_hud(g)
        except Exception:  # noqa: BLE001, S112 — une action refusée par le moteur ne donne pas de distracteur
            continue
        k = im.tobytes() + bytes(str(im.shape), "ascii")
        if k not in vues:
            vues.add(k)
            out.append(im)
    return out


def _etat_cache_de(cache):
    cache = cache() if callable(cache) else cache
    return np.asarray(cache, dtype=np.int64).tobytes()


def _classer(d, predit, vraie, autres):
    """Ajoute au compteur `d` le classement d'une transition (prédiction None = règle plantée : rang le pire)."""
    if not autres:
        d["sans"] += 1
        return
    r = rang(distance(predit, vraie), [distance(predit, x) for x in autres])
    d["n"] += 1
    d["p1"] += r == 1
    d["rang"] += (r - 1) / len(autres)
    d["k"] += len(autres)


def _resume_classement(d, t):
    n = max(d["n"], 1)
    return {"classees": d["n"], "sans_distracteur": d["sans"], "p_at_1": round(d["p1"] / n, 4) if d["n"] else None,
            "rang_norm": round(d["rang"] / n, 4) if d["n"] else None, "n_distr_moy": round(d["k"] / n, 2),
            "p_at_1_temoin": round(t["p1"] / n, 4) if d["n"] else None,
            "rang_norm_temoin": round(t["rang"] / n, 4) if d["n"] else None}


def mesurer(arc, f, avec_distracteurs=False):
    """`avec_distracteurs` : classement OneLife (rang du vrai état suivant parmi les états atteints par les autres
    actions, selon la distance à la prédiction) ; rang normalisé = (rang − 1)/k, 0 = premier, 1 = dernier."""
    jeu = Path(f).name[:4]
    cl = {"n": 0, "p1": 0, "rang": 0.0, "k": 0, "sans": 0}
    cl_t = {"n": 0, "p1": 0, "rang": 0.0, "k": 0, "sans": 0}
    step, source = charger_step(jeu)
    cv = bool(getattr(step, "canevas", False))  # image complète jugée (programme ET témoin) : voir juger
    env = arc.make(Path(f).name.split("_p")[0])
    env.reset()
    scene, temoin = _resync(env, None, cv), _resync(env, None, cv)
    niveau = env._game._current_level_index
    cache_avant, hud_avant = _etat_cache(env._game), None
    n = dict.fromkeys(("img", "ok", "t_img", "t_ok", "total", "hud_change", "cache_change"), 0)
    premiere = None
    for e in evenements(f):
        if "board" not in e or e.get("type") == "initial":
            continue
        nom = e.get("action_name", "")
        if nom not in NUM:
            continue
        a = action_de(e)
        g = GameAction.from_id(NUM[nom])
        avant = copie_profonde(env._game) if avec_distracteurs else None
        obs = env.step(g, data={"x": a[2], "y": a[1]}) if NUM[nom] == 6 else env.step(g)
        _, image = scene_moteur(env)
        complet = np.asarray(obs.frame[-1], dtype=np.int16) if obs is not None and obs.frame else image
        sprites, cache = etat_moteur(env)
        vrai = {"image": image, "complet": complet, "sprites": sprites, "cache": cache, "cache_change": cache != cache_avant}
        cache_avant = cache
        if a[0] == "RESET" or env._game._current_level_index != niveau or str(e.get("game_over")) == "True":
            scene, temoin = _resync(env, None, cv), _resync(env, None, cv)  # nouveau départ : on ne mesure pas ce coup
            niveau, hud_avant = env._game._current_level_index, None
            continue
        hud = np.where(complet != image, complet, -1)  # ce que le HUD ajoute à l'image (compté, jugé seulement si produit)
        n["total"] += 1
        n["hud_change"] += hud_avant is not None and not np.array_equal(hud, hud_avant)
        n["cache_change"] += bool(vrai["cache_change"])
        hud_avant = hud
        img, ok, erreur, faux, predit = juger(scene, step, a, vrai, cv)
        t_img, t_ok, _, _, t_predit = juger(temoin, None, a, vrai, cv)
        if avec_distracteurs:
            autres = distracteurs(avant, a, image, f"{jeu}:{n['total']}")
            _classer(cl, predit, image, autres)
            _classer(cl_t, t_predit, image, autres)
        n["img"], n["ok"], n["t_img"], n["t_ok"] = n["img"] + img, n["ok"] + ok, n["t_img"] + t_img, n["t_ok"] + t_ok
        if not ok and premiere is None:
            canal = "image" if not img else ("interface" if cv and etat_scene(scene) == vrai["sprites"] else "etat")
            premiere = {"coup": n["total"], "action": a, "erreur": erreur, "pixels_faux": faux, "canal": canal}
        if not ok:
            scene = _resync(env, scene, cv)  # on resynchronise (attributs gardés) : chaque transition est jugée seule
        if not t_ok:
            temoin = _resync(env, temoin, cv)
    tot = max(n["total"], 1)
    temoin_h = round(n["t_ok"] / tot, 4) if n["total"] else None
    vide = a_vide(temoin_h)
    extra = {"classement": _resume_classement(cl, cl_t)} if avec_distracteurs else {}
    return {"jeu": jeu, "source": source, "transitions": n["total"], "exactes": n["img"], "taux": round(n["img"] / tot, 4),
            "exactes_honnetes": n["ok"], "taux_honnete": round(n["ok"] / tot, 4),
            "temoin_image": round(n["t_img"] / tot, 4), "temoin": temoin_h, "a_vide": vide,
            "image_hud": "comparée (canevas)" if cv else "non comparée (programme sans canevas)", "hud_change": n["hud_change"], "cache_change": n["cache_change"],
            "reproduit": n["ok"] == n["total"] > 0 and not vide, "premiere_erreur": premiere, **extra}


def fichiers_traces(jeux=None):
    return [f for f in sorted((DONNEES / "runs_pod/R0").glob("*/artifacts/*_events.jsonl"))
            if f.name[:4] not in TEMOINS and (not jeux or f.name[:4] in jeux)]


def arcade():
    return Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(DONNEES / "experiments/arc3/environment_files"))


def main(jeux):
    arc = arcade()
    res = []
    for f in fichiers_traces(jeux):
        r = mesurer(arc, f)
        res.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
    print(f"JEUX REPRODUITS (honnêtes, hors à vide) : {sum(r['reproduit'] for r in res)}/{len(res)} ; transitions "
          f"exactes {sum(r['exactes_honnetes'] for r in res)}/{sum(r['transitions'] for r in res)} ; à vide : "
          f"{[r['jeu'] for r in res if r['a_vide']]}")
    # fusion par jeu (CW-096) : un lancement sur un seul jeu ne fait pas disparaître les autres
    f = ICI / "exhaustivite.json"
    anciens = {r["jeu"]: r for r in json.loads(f.read_text())} if f.exists() else {}
    anciens.update({r["jeu"]: r for r in res})
    f.write_text(json.dumps(sorted(anciens.values(), key=lambda r: r["jeu"]), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
