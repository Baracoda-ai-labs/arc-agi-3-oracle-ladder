# SPDX-License-Identifier: MIT-0
"""T3.2 (CW-093/095) : langage v0 tiré de l'ontologie, DÉCLARATIF, exécutable — interpréteur de référence.
Un programme (JSON ou YAML) : {"etat": {nom: valeur initiale}, "regles": [règle…]} ; une règle :
  {"nom": …, "quand": <condition>, "soit": {var: <expr>, …}, "alors": [<effet>, …], "puis": "stop" | "continuer"}
Les règles sont essayées dans l'ordre à chaque coup (liaisons `soit`, puis condition `quand`, puis effets `alors`) ;
« stop » (défaut) arrête après la 1re qui s'applique.
Termes = listes préfixées ["op", args…] ; chaînes "$v" = variable liée par `soit` ou `pour`. AUCUN Python libre.
Vocabulaire v0 (familles de manques de B, CCM-065-B) :
- logique : et, ou, non, =, != (objets : par identité), <, <=, >, >=, +, -, *, //, %, si(c, a, b) ; listes : liste, longueur, elem,
  premier, vide, contient, indice, suivant (cyclique), table({k: v}, clé, défaut), intervalle(a, b) ; quantifieurs
  [op, "$v", liste, cond] : tous, existe, premier_tel_que, filtrer ; tri stable [trier|trier_desc, liste, "$v", clé]
- action : ["action"] → "UP"… ; ["case_clic"] → [x, y] dans la vue (clic → case : conversion caméra inverse)
- jeu : ["niveau"] (index du niveau), ["vue"] → [largeur, hauteur] ; état caché nommé : ["etat", n] ; effets poser(n, e), empiler(n, e), depiler(n)
- objets : ["objets", {"tag"|"nom"|"couleur"|"visible": …}] → liste ; ["a", x, y] (objets à la case, calque haut d'abord) ;
  ["objets_dans_boite", x, y, l, h] (objets dont la boîte est incluse dans le rectangle, opaques ou non, visibles ou non) ;
  ["x", o], ["y", o], ["largeur", o], ["hauteur", o], ["attr", o, nom] (attribut libre : orientation, rôle…), ["nom", o], ["pixel", o, dx, dy] ;
  ["chevauche", o1, o2] (contact AU PIXEL, pixels opaques) ; ["libre", o, dx, dy, filtre] (o décalé ne chevauche aucun objet
  du filtre) ; v0.2 : ["visible", o], ["calque", o] (terme à 1 argument), ["a_tag", o, t], ["bloquant", o] (collidable arcengine)
- début de niveau (v0.2) : ["debut_niveau"] vrai au 1er coup joué sur une scène neuve (Scene.debut) ; section facultative
  "au_debut": [effets…] du programme, exécutée à ce même coup avant les règles
- création liée (v0.2) : ["soit_creer", "$v", modele, x, y, [effets…]] crée l'objet, lie $v à lui, exécute les effets
- effets (fermés, = Scene) : deplacer(o, dx, dy), placer(o, x, y), tourner(o, q), recolorer(o, a, b), ecrire(o, dy, dx, c),
  montrer(o, b), calque(o, c), creer(modele, x, y), retirer(o), poser_attr(o, nom, v), niveau_suivant, gagner, perdre ;
  itération : ["pour", "$v", liste, [effets…]], ["tant_que", cond, [effets…], max=64] ; conditionnel : ["si_alors", cond, [effets…], [sinon…]]
- v0.2 : calcul réel div, racine, arrondi (round de Python), plancher ; ["alea", graine, n, rang?] (suite de
  random.Random(graine).randrange(n)) ; ["composantes", "$a", "$b", liste, relation] (union-find) ; ["echelle", o] ;
  ["contact_moteur", o1, o2] (collides_with du moteur, -2 plein) ; effets remodeler(o, ex, ey?) (set_scale du moteur) et
  ["pousser", o, dx, dy, bloqueurs, poussables, nom_etat?] (poussée en chaîne ; etat[nom_etat] = bloqué)
- v0.3 : données non dessinées ["donnees_de_niveau", clé], ["attr_cache", o, clé], ["dernier_niveau"] ; formes
  ["forme_modele", nom] + effet poser_motif(o, motif) ; chaînes prefixe(c, k), segment(c, sep, i), tags(o) ;
  [argmin|argmax, "$v", liste, clé] ; effets instantane(n), restaurer(n), poser_bloquant(o, b), rendre_intangible(o) ;
  niveau_suivant au dernier niveau = victoire (comme arcengine next_level)
- v0.4 (CW-128 c) : ["correspond", o1, o2], ["correspond_rot", o1, o2] (quarts q de tourner, ou None) ; jauge :
  effet consommer(n, k), terme epuise(n, seuil?) ; recharge à usage unique : effet recharger(n, valeur, o), terme utilise(o)
- v0.5 (CW-132, étage 2) : section "niveau" {"<indice>": {clé: valeur}, "*": {défauts}} ; terme ["param", clé]
- v0.6 (CW-141/142) canevas = écran interne dessiné PAR-DESSUS les sprites (interface du moteur ; ontologie_exec) :
  ["canevas", nom?] (défaut : le 1er), ["case_canevas", c, x, y] (None hors grille ; « case » est un mot de ls20),
  ["cases_de", c, couleur] → [[x, y]…],
  ["composantes_canevas", c, {"couleur", "connexite"}?] → objets dérivés (x, y, largeur, hauteur, couleur, cases, pixels),
  ["pixel_clic", c?] (case sous le clic, None hors canevas), ["geometrie", c] → [x0, y0, kx, ky] ; effets
  ecrire_case(c, x, y, v), remplir(c, x, y, l, h, v), deplacer_bloc(c, x, y, l, h, dx, dy, fond?), poser_geometrie(c, x0, y0, k, ky?) ;
  instantane/restaurer gardent aussi les canevas
Le même texte doit se compiler aussi en simulateur rapide et en ASP (CW-095) : d'où un vocabulaire fermé et sans effet de bord
hors des effets nommés.
Mots nouveaux : sections "mots" (macros du langage) et "fonctions" (expressions Python pures en bac à sable) — voir plus bas
et `mots_valides` pour le journal."""
import ast
import copy
import functools
import hashlib
import json
import math
import random
import types

import numpy as np

from chrysalide.arc3 import ontologie_exec as _oe
from chrysalide.arc3.logique.correspond import dessin as _dessin_c


class ErreurLangage(Exception):
    pass


def _filtre(s, f):
    for k, v in f.items():
        if k == "tag" and v not in s.get("tags", ()):
            return False
        if k == "nom" and s.get("nom") != v:
            return False
        if k == "couleur" and v not in np.unique(np.asarray(s["pixels"])).tolist():
            return False
        if k == "visible" and bool(s.get("visible", True)) != bool(v):
            return False
    return True


def _cases(s, dx=0, dy=0):
    px = np.asarray(s["pixels"])
    ys, xs = np.nonzero(px >= 0)
    return set(zip((ys + s["y"] + dy).tolist(), (xs + s["x"] + dx).tolist(), strict=True))


def _contact_moteur(a, b):
    """`Sprite.collides_with` d'arcengine : deux objets distincts, tous deux bloquants (is_collidable), aucun en mode
    NOT_BLOCKED ; boîtes qui se recouvrent ; si l'un est PIXEL_PERFECT (défaut du moteur), au moins un pixel != -1 commun
    (la valeur -2, transparente au rendu, compte comme pleine)."""
    if a is b or not (a.get("bloquant", True) and b.get("bloquant", True)):
        return False
    ma, mb = a.get("blocage", "PIXEL_PERFECT"), b.get("blocage", "PIXEL_PERFECT")
    if "NOT_BLOCKED" in (ma, mb):
        return False
    pa, pb = np.asarray(a["pixels"]), np.asarray(b["pixels"])
    (ha, wa), (hb, wb) = pa.shape, pb.shape
    if a["x"] >= b["x"] + wb or a["x"] + wa <= b["x"] or a["y"] >= b["y"] + hb or a["y"] + ha <= b["y"]:
        return False
    if "PIXEL_PERFECT" not in (ma, mb):
        return True
    x0, x1 = max(a["x"], b["x"]), min(a["x"] + wa, b["x"] + wb)
    y0, y1 = max(a["y"], b["y"]), min(a["y"] + ha, b["y"] + hb)
    ra = pa[y0 - a["y"]:y1 - a["y"], x0 - a["x"]:x1 - a["x"]]
    rb = pb[y0 - b["y"]:y1 - b["y"], x0 - b["x"]:x1 - b["x"]]
    return bool(np.any((ra != -1) & (rb != -1)))


def _correspond_rot(o1, o2):
    """CW-128 (c) : plus petit q (0..3) tel que tourner(o1, q) porte le même dessin que o2 (`dessin` de C, CCM-027/032-C :
    recadré sur la partie non unie, ramené à la plus petite échelle entière, couleurs renommées ; transparents −1/−2
    confondus) ; None sinon (ou dessin réduit à une ligne, comme `correspond` de C)."""
    if o1 is None or o2 is None:
        return None
    p1, p2 = (np.where(np.asarray(o["pixels"]) < 0, -1, np.asarray(o["pixels"])) for o in (o1, o2))
    d2 = _dessin_c(p2)
    if len(d2) <= 1:
        return None
    return next((q for q in range(4) if _dessin_c(np.rot90(p1, -q)) == d2), None)  # sens de Scene.tourner


def _recharger(etat, n, v, o):
    """CW-128 (c) : recharge à usage unique ; o absent ou déjà utilisé : rien."""
    if o is None or o.get("attrs", {}).get("utilise"):
        return
    etat[n] = v
    o.setdefault("attrs", {})["utilise"] = True
    o["visible"] = False


TERMES_CANEVAS = ("canevas", "case_canevas", "cases_de", "composantes_canevas", "pixel_clic", "geometrie")
EFFETS_CANEVAS = ("ecrire_case", "remplir", "deplacer_bloc", "poser_geometrie")


def utilise_canevas(texte):
    """Vrai si le programme emploie un mot de canevas (le banc juge alors l'image complète, interface comprise)."""
    mots = set(TERMES_CANEVAS) | set(EFFETS_CANEVAS)

    def cherche(t):
        if isinstance(t, list):
            return bool(t) and isinstance(t[0], str) and t[0] in mots or any(cherche(x) for x in t)
        if isinstance(t, dict):
            return any(cherche(x) for x in t.values())
        return False
    return cherche(texte)


def terme_canevas(sc, op, args, action):
    """Termes de canevas, arguments déjà évalués (code commun à l'interpréteur et à sim_rapide)."""
    if op == "canevas":
        cs = getattr(sc, "canevas", None) or []
        nom = args[0] if args else None
        return (cs[0] if cs else None) if nom is None else next((c for c in cs if c["nom"] == nom), None)
    if op == "case_canevas":
        return _oe.case_canevas(args[0], args[1], args[2])
    if op == "cases_de":
        return _oe.cases_de(args[0], args[1])
    if op == "composantes_canevas":
        return _oe.composantes_canevas(args[0], args[1] if len(args) > 1 else None)
    if op == "geometrie":
        c = args[0]
        return None if c is None else [c["x"], c["y"], c["kx"], c["ky"]]
    if op == "pixel_clic":
        _, r, col = action
        if r is None or col is None or (args and args[0] is None):
            return None
        return _oe.clic_vers_case(getattr(sc, "canevas", None) or [], r, col, args[0] if args else None)
    raise ErreurLangage(f"terme inconnu : {op}")


def instantane_scene(sc, etat):
    return copy.deepcopy(sc.sprites), copy.deepcopy(etat), _oe.copier_canevas(getattr(sc, "canevas", None))


def restaurer_scene(sc, inst):
    """Remet sprites (et canevas) ; rend l'état du programme restauré."""
    sprites, etat, canevas = inst
    sc.sprites = copy.deepcopy(sprites)
    if hasattr(sc, "canevas"):
        sc.canevas = _oe.copier_canevas(canevas)
    return copy.deepcopy(etat)


def valeur_param(texte, niveau, cle):
    """Étage 2 : valeur de `cle` dans la section « niveau » du programme pour ce niveau, repli sur "*", sinon None."""
    section = texte.get("niveau") or {}
    for k in (str(niveau), "*"):
        d = section.get(k)
        if isinstance(d, dict) and cle in d:
            return copy.deepcopy(d[cle])
    return None


@functools.lru_cache(maxsize=4096)
def _alea(graine, n, rang):
    """rang-ième tirage (0 = premier) de `random.Random(graine).randrange(n)` : même suite que choice(liste de n) et
    randint(0, n-1) du Python du moteur (tous passent par _randbelow(n))."""
    r = random.Random(graine)
    for _ in range(rang):
        r.randrange(n)
    return r.randrange(n)


ATTRIBUT = {"deplacer": "pos", "placer": "pos", "tourner": "pixels", "recolorer": "pixels", "ecrire": "pixels",
            "remodeler": "pixels", "montrer": "visible", "calque": "couche", "retirer": "existe", "poser_motif": "pixels",
            "poser_bloquant": "bloquant", "rendre_intangible": "bloquant"}  # conflits du mode « lois »


class Programme:
    def __init__(self, texte):
        self.p = texte
        self.etat = copy.deepcopy(texte.get("etat", {}))
        self.conflits = []  # mode « lois » : (loi écartée, effet, poids gagnant, poids écarté)
        self.mots, self.fonctions = compiler_mots(texte)  # refus à la définition (portée, récursion, AST…)
        self.instantanes = {}  # instantane(n) : nom → (sprites, etat) copiés en profondeur
        self._prof = 0

    def _appel(self, op, a, env, sorte):
        """Appel d'un mot défini : arguments évalués dans l'appelant, corps évalué avec les seuls paramètres liés."""
        if op in self.fonctions:
            f = self.fonctions[op]
            if sorte != "terme":
                raise ErreurLangage(f"la fonction {op!r} est un terme, employée comme effet")
            if len(a) != len(f["params"]):
                raise ErreurLangage(f"fonction {op!r} : arité {len(f['params'])}, {len(a)} argument(s) donné(s)")
            return _appeler_fonction(f, [_simple(self.ev(x, env)) for x in a], op)
        d = self.mots[op]
        ps, s = d.get("params", []), d.get("sorte", "terme")
        if s != sorte:
            raise ErreurLangage(f"le mot {op!r} est un {s}, employé comme {sorte}")
        if len(a) != len(ps):
            raise ErreurLangage(f"mot {op!r} : arité {len(ps)}, {len(a)} argument(s) donné(s)")
        if self._prof >= PROF_MAX:
            raise ErreurLangage(f"mot {op!r} : profondeur d'appel > {PROF_MAX}")
        env2 = {k: v for k, v in env.items() if k.startswith("_")}  # contexte du coup (scène, action), rien d'autre
        env2.update({p[1:]: self.ev(x, env) for p, x in zip(ps, a, strict=True)})
        self._prof += 1
        try:
            if sorte == "terme":
                return self.ev(d["corps"], env2)
            for e in d["corps"]:
                self.fait(e, env2)
        finally:
            self._prof -= 1

    # ------------------------------------------------------------- évaluation
    def ev(self, t, env):
        if isinstance(t, str) and t.startswith("$"):
            if t[1:] not in env:
                raise ErreurLangage(f"variable inconnue {t}")
            return env[t[1:]]
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            return t
        op, a = t[0], t[1:]
        if op in self.mots or op in self.fonctions:
            return self._appel(op, a, env, "terme")
        sc = env["_scene"]
        ev = lambda x: self.ev(x, env)
        if op == "et":
            return all(ev(x) for x in a)
        if op == "ou":
            return any(ev(x) for x in a)
        if op == "non":
            return not ev(a[0])
        if op in ("=", "!="):
            x, y = ev(a[0]), ev(a[1])
            eg = (x is y) if isinstance(x, dict) or isinstance(y, dict) else (x == y)  # objets : par identité
            return eg if op == "=" else not eg
        if op in ("<", "<=", ">", ">=", "+", "-", "*", "//", "%"):
            x, y = ev(a[0]), ev(a[1])
            return {"=": lambda: x == y, "!=": lambda: x != y, "<": lambda: x < y, "<=": lambda: x <= y, ">": lambda: x > y,
                    ">=": lambda: x >= y, "+": lambda: x + y, "-": lambda: x - y, "*": lambda: x * y, "//": lambda: x // y,
                    "%": lambda: x % y}[op]()
        if op == "div":  # division réelle
            return float(ev(a[0])) / float(ev(a[1]))
        if op == "racine":  # x ** 0.5, comme les moteurs (pas math.sqrt)
            return float(ev(a[0])) ** 0.5
        if op == "arrondi":  # round(x) de Python (entier) : moitié → pair (banquier), comme int(round(x)) des moteurs
            return round(float(ev(a[0])))
        if op == "plancher":
            return math.floor(ev(a[0]))
        if op == "alea":  # ["alea", graine, n, rang?] → entier de 0..n-1, déterministe
            return _alea(int(ev(a[0])), int(ev(a[1])), int(ev(a[2])) if len(a) > 2 else 0)
        if op == "si":
            return ev(a[1]) if ev(a[0]) else ev(a[2])
        if op == "liste":
            return [ev(x) for x in a]
        if op == "longueur":
            return len(ev(a[0]))
        if op == "elem":
            v = ev(a[0])
            return v[ev(a[1])] if v is not None else None
        if op == "premier":
            v = ev(a[0])
            return v[0] if v else None
        if op == "vide":
            return not ev(a[0])
        if op == "contient":
            v, x = ev(a[0]), ev(a[1])
            return any(e is x for e in v) if isinstance(x, dict) else x in v
        if op == "indice":
            v, x = ev(a[0]), ev(a[1])
            return next((i for i, e in enumerate(v) if (e is x if isinstance(x, dict) else e == x)), None)
        if op == "suivant":  # élément suivant, cyclique
            v, x = ev(a[0]), ev(a[1])
            i = next((i for i, e in enumerate(v) if (e is x if isinstance(x, dict) else e == x)), None)
            return None if i is None or not v else v[(i + 1) % len(v)]
        if op == "table":  # ["table", {clé: valeur}, clé, défaut?]
            return ev(a[0]).get(str(ev(a[1])), ev(a[2]) if len(a) > 2 else None)
        if op in ("tous", "existe", "premier_tel_que", "filtrer"):  # [op, "$v", liste, condition]
            nom_v, liste = a[0].lstrip("$"), ev(a[1]) or []
            ok = [e for e in liste if self.ev(a[2], {**env, nom_v: e})]
            return {"tous": len(ok) == len(liste), "existe": bool(ok), "premier_tel_que": ok[0] if ok else None,
                    "filtrer": ok}[op]
        if op in ("argmin", "argmax"):  # [op, "$v", liste, clé] : élément de clé minimale (maximale), le 1er à égalité
            nom_v, meilleur, cle = a[0].lstrip("$"), None, None
            for e in ev(a[1]) or []:
                k = self.ev(a[2], {**env, nom_v: e})
                if cle is None or (k < cle if op == "argmin" else k > cle):
                    meilleur, cle = e, k
            return meilleur
        if op == "intervalle":  # ["intervalle", a, b] → [a, …, b-1]
            return list(range(ev(a[0]), ev(a[1])))
        if op in ("trier", "trier_desc"):  # [op, liste, "$v", clé] : tri stable par clé évaluée avec $v lié
            liste, nom_v = ev(a[0]) or [], a[1].lstrip("$")
            return sorted(liste, key=lambda e: self.ev(a[2], {**env, nom_v: e}), reverse=op == "trier_desc")
        if op == "composantes":  # ["composantes", "$a", "$b", liste, relation] : composantes connexes (union-find)
            na, nb, liste = a[0].lstrip("$"), a[1].lstrip("$"), list(ev(a[2]) or [])
            parent = list(range(len(liste)))

            def racine(i):
                while parent[i] != i:
                    i = parent[i]
                return i
            for i in range(len(liste)):
                for j in range(i + 1, len(liste)):
                    if self.ev(a[3], {**env, na: liste[i], nb: liste[j]}):
                        ri, rj = racine(i), racine(j)
                        if ri != rj:
                            parent[rj] = ri
            groupes = {}
            for i, e in enumerate(liste):  # ordre : groupes par 1er membre, membres dans l'ordre de la liste
                groupes.setdefault(racine(i), []).append(e)
            return list(groupes.values())
        if op == "action":
            return env["_action"][0]
        if op == "case_clic":
            act = tuple(env["_action"]) + (None, None)  # l'agent passe ("UP",) (moteur.nom_action), le banc ("UP", None, None)
            r, c = act[1], act[2]
            return None if r is None or c is None else self._clic_vers_case(sc, r, c)  # None hors clic
        if op == "niveau":
            n = getattr(sc, "niveau", None)
            return env.get("_niveau", 0) if n is None else n
        if op == "vue":  # [largeur, hauteur] de la vue du jeu
            return [sc.vue[1], sc.vue[0]]
        if op == "nom":
            return ev(a[0]).get("nom")
        if op == "tags":  # liste des tags de l'objet (vide sans objet)
            o = ev(a[0])
            return [] if o is None else list(o.get("tags", ()))
        if op == "prefixe":  # ["prefixe", chaine, k] → les k premiers caractères (k < 0 : tous sauf les -k derniers)
            c = ev(a[0])
            return None if c is None else str(c)[:ev(a[1])]
        if op == "segment":  # ["segment", chaine, sep, i] → i-ème morceau de chaine.split(sep) (i < 0 depuis la fin), None hors
            c, sep, i = ev(a[0]), ev(a[1]), ev(a[2])
            m = [] if c is None else str(c).split(sep)
            return m[i] if -len(m) <= i < len(m) else None
        if op == "param":  # ["param", clé] : paramètre du niveau courant (section « niveau »), repli sur "*", sinon None
            n = getattr(sc, "niveau", None)
            return valeur_param(self.p, env.get("_niveau", 0) if n is None else n, ev(a[0]))
        if op == "donnees_de_niveau":  # donnée du niveau courant fournie par le moteur (Level.get_data), None si absente
            return copy.deepcopy(getattr(sc, "donnees", {}).get(ev(a[0])))
        if op == "attr_cache":  # champ non dessiné du sprite moteur : rotation (degrés), mirror_ud, mirror_lr
            o = ev(a[0])
            return None if o is None else o.get("cache", {}).get(ev(a[1]))
        if op == "forme_modele":  # pixels d'origine du modèle nommé du jeu (catalogue), liste de listes ; None si inconnu
            m = getattr(sc, "modeles", {}).get(ev(a[0]))
            return None if m is None else np.asarray(m).tolist()
        if op == "dernier_niveau":  # vrai au dernier niveau du jeu (nombre de niveaux connu de la scène)
            d = getattr(sc, "dernier_niveau", None)
            return bool(d()) if callable(d) else False
        if op == "pixel":  # couleur du pixel (dx, dy) de l'objet, None hors sprite ; < 0 = transparent
            o, dx, dy = ev(a[0]), ev(a[1]), ev(a[2])
            px = np.asarray(o["pixels"])
            return int(px[dy, dx]) if 0 <= dy < px.shape[0] and 0 <= dx < px.shape[1] else None
        if op == "etat":
            return self.etat.get(a[0])
        if op == "objets":
            return [s for s in sc.sprites if _filtre(s, a[0] if a else {})]
        if op == "a":
            return sc.a(ev(a[0]), ev(a[1]))
        if op == "objets_dans_boite":  # CCM-159-B (renommé : tn36 a un mot « dans_boite » à lui) : objets dont la boîte est incluse dans le rectangle (opaques ou non, visibles ou non)
            return sc.dans_boite(*(ev(t) for t in a[:4]))
        if op in ("x", "y"):
            return ev(a[0])[op]
        if op == "largeur":
            return np.asarray(ev(a[0])["pixels"]).shape[1]
        if op == "hauteur":
            return np.asarray(ev(a[0])["pixels"]).shape[0]
        if op == "attr":
            return ev(a[0]).get("attrs", {}).get(ev(a[1]))
        if op in ("visible", "bloquant"):  # bloquant = sprite collidable pour arcengine (défaut du moteur : True)
            o = ev(a[0])
            return o is not None and bool(o.get(op, True))
        if op == "a_tag":
            o, t = ev(a[0]), ev(a[1])
            return o is not None and t in o.get("tags", ())
        if op == "calque":  # terme à 1 argument ; l'EFFET calque(o, c) est à 2 arguments
            if len(a) != 1:
                raise ErreurLangage("terme calque(o) : 1 argument (l'effet calque(o, c) n'est pas un terme)")
            o = ev(a[0])
            return None if o is None else o["couche"]
        if op == "debut_niveau":  # vrai pendant le 1er coup joué sur une scène neuve
            return bool(env.get("_debut", False))
        if op == "echelle":  # échelle moteur (1 par défaut ; voir remodeler)
            return ev(a[0]).get("echelle", 1)
        if op == "contact_moteur":
            return _contact_moteur(ev(a[0]), ev(a[1]))
        if op == "chevauche":
            o1, o2 = ev(a[0]), ev(a[1])
            return o1 is not o2 and bool(_cases(o1) & _cases(o2))
        if op in ("correspond", "correspond_rot"):  # CW-128 (c) : même dessin à l'échelle entière et au quart de tour près
            q = _correspond_rot(ev(a[0]), ev(a[1]))
            return q if op == "correspond_rot" else q is not None
        if op == "epuise":  # ["epuise", n, seuil?] : etat[n] (absent = 0) <= seuil (0 par défaut)
            return (self.etat.get(a[0]) or 0) <= (ev(a[1]) if len(a) > 1 else 0)
        if op == "utilise":  # recharge déjà prise (effet recharger)
            o = ev(a[0])
            return o is not None and bool(o.get("attrs", {}).get("utilise"))
        if op in TERMES_CANEVAS:
            return terme_canevas(sc, op, [ev(x) for x in a], env["_action"])
        if op == "libre":
            o, dx, dy, f = ev(a[0]), ev(a[1]), ev(a[2]), (a[3] if len(a) > 3 else {})
            dest = _cases(o, dx, dy)
            return not any(s is not o and s.get("visible", True) and _filtre(s, f) and dest & _cases(s) for s in sc.sprites)
        raise ErreurLangage(f"terme inconnu : {op}")

    @staticmethod
    def _clic_vers_case(sc, r, c):
        h, w = sc.vue
        k = min(64 // w, 64 // h)
        y0, x0 = (64 - h * k) // 2, (64 - w * k) // 2
        if not (y0 <= r < y0 + h * k and x0 <= c < x0 + w * k):
            return None
        return [(c - x0) // k + sc.camera[0], (r - y0) // k + sc.camera[1]]

    # ------------------------------------------------------------- effets
    def fait(self, e, env):
        op, a = e[0], e[1:]
        if op in self.mots or op in self.fonctions:
            self._appel(op, a, env, "effet")
            return
        sc = env["_scene"]
        ev = lambda x: self.ev(x, env)
        if op == "si_alors":  # effet conditionnel : ["si_alors", cond, [effets], [sinon]?]
            for f in (a[1] if ev(a[0]) else (a[2] if len(a) > 2 else [])):
                self.fait(f, env)
            return
        if op == "pour":
            for v in list(ev(a[1]) or []):
                for f in a[2]:
                    self.fait(f, {**env, a[0].lstrip("$"): v})
            return
        if op == "tant_que":  # ["tant_que", cond, [effets], max?] : cond réévaluée après chaque passage, ≤ max (64) passages
            for _ in range(ev(a[2]) if len(a) > 2 else 64):
                if not ev(a[0]):
                    break
                for f in a[1]:
                    self.fait(f, env)
            return
        if op == "refleter":  # ["refleter", objets, "x"|"y", c] : crée le miroir de chaque objet par rapport à l'axe x = c (ou y = c)
            liste, axe, c = ev(a[0]), a[1], ev(a[2])
            for o in list(liste if isinstance(liste, list) else [liste]):
                px = np.asarray(o["pixels"])
                if axe == "x":
                    sc.creer(dict(o, pixels=np.fliplr(px)), 2 * c - o["x"] - px.shape[1], o["y"])
                else:
                    sc.creer(dict(o, pixels=np.flipud(px)), o["x"], 2 * c - o["y"] - px.shape[0])
            return
        if op == "soit_creer":  # ["soit_creer", "$v", modele, x, y, [effets…]] : crée, lie $v au nouvel objet, exécute
            modele, x, y = ev(a[1]), ev(a[2]), ev(a[3])
            if modele is None:
                return  # comme les autres effets : sans modèle, ignoré
            n = sc.creer(modele, x, y)
            for f in (a[4] if len(a) > 4 else []):
                self.fait(f, {**env, a[0].lstrip("$"): n})
            return
        if op == "poser":
            self.etat[a[0]] = ev(a[1])
        elif op == "empiler":
            self.etat.setdefault(a[0], []).append(copy.deepcopy(ev(a[1])))
        elif op == "depiler":
            pile = self.etat.get(a[0]) or []
            env["_depile"] = pile.pop() if pile else None
        elif op == "poser_attr":
            ev(a[0]).setdefault("attrs", {})[ev(a[1])] = ev(a[2])
        elif op == "consommer":  # ["consommer", n, k] : jauge etat[n] (absent = 0) diminuée de k
            self.etat[a[0]] = (self.etat.get(a[0]) or 0) - ev(a[1])
        elif op == "recharger":  # ["recharger", n, valeur, o] : etat[n] = valeur, o marqué utilise et masqué (une fois)
            v = ev(a[1])
            _recharger(self.etat, a[0], v, ev(a[2]))
        elif op == "pousser":  # ["pousser", o, dx, dy, bloqueurs, poussables, nom_etat?]
            o, dx, dy = ev(a[0]), ev(a[1]), ev(a[2])
            bloque = o is not None and self._pousser(sc, o, dx, dy, a[3], a[4] if len(a) > 4 else {})
            if len(a) > 5:
                self.etat[a[5]] = bool(bloque)
        elif op in ("niveau_suivant", "gagner", "perdre"):
            getattr(sc, op)()
        elif op == "instantane":  # ["instantane", n] : copie profonde des sprites de la scène et de l'état du programme
            self.instantanes[ev(a[0])] = instantane_scene(sc, self.etat)
        elif op == "restaurer":  # ["restaurer", n] : remet sprites, canevas et état ; nom inconnu : ignoré
            n = ev(a[0])  # objets NOUVEAUX (copies) : les liaisons faites avant désignent les anciens
            if n in self.instantanes:
                self.etat = restaurer_scene(sc, self.instantanes[n])
        elif op in ("deplacer", "placer", "tourner", "recolorer", "ecrire", "montrer", "calque", "creer", "retirer",
                    "remodeler", "poser_motif", "poser_bloquant", "rendre_intangible", *EFFETS_CANEVAS):
            args = [ev(x) for x in a]
            if args and args[0] is None:
                return  # objet absent : effet sans objet, ignoré
            getattr(sc, op)(*args)
        else:
            raise ErreurLangage(f"effet inconnu : {op}")

    def _pousser(self, sc, o, dx, dy, bloqueurs, poussables):
        """Poussée en chaîne (ka59 `ifoelczjjh`) : o avance ; s'il touche un bloqueur il recule et la poussée échoue ;
        sinon chaque poussable touché est poussé à son tour, et si l'un échoue o recule (ceux déjà poussés restent).
        Contact = contact_moteur. Rend True si bloqué."""
        x0, y0 = o["x"], o["y"]
        o["x"], o["y"] = x0 + dx, y0 + dy
        if any(_filtre(s, bloqueurs) and _contact_moteur(o, s) for s in sc.sprites):
            o["x"], o["y"] = x0, y0
            return True
        for s in [s for s in sc.sprites if _filtre(s, poussables) and _contact_moteur(o, s)]:
            if self._pousser(sc, s, dx, dy, bloqueurs, poussables):
                o["x"], o["y"] = x0, y0
                return True
        return False

    # ------------------------------------------------------------- un coup
    def step(self, scene, action, niveau=0):
        debut = bool(getattr(scene, "debut", False))
        scene.debut = False
        env0 = {"_scene": scene, "_action": action, "_niveau": niveau, "_debut": debut}
        if debut:  # section "au_debut" : effets exécutés une fois par scène neuve, avant les règles du 1er coup
            for e in self.p.get("au_debut", []):
                self.fait(e, dict(env0))
        regles = self.p.get("regles", [])
        if self.p.get("mode") != "lois":
            for r in regles:
                env = dict(env0)
                for v, t in (r.get("soit") or {}).items():  # liaisons d'abord : la condition peut s'en servir
                    env[v] = self.ev(t, env)
                if not self.ev(r.get("quand", True), env):
                    continue
                for e in r.get("alors", []):
                    self.fait(e, env)
                if r.get("puis", "stop") == "stop":
                    break
            return
        # lois atomiques (CW-113) : par PHASE croissante (champ "phase", défaut 0 ; CCM-020-C : consommation après les
        # déplacements), les conditions des lois de la phase sont jugées sur l'état laissé par les phases précédentes
        for ph in sorted({r.get("phase", 0) for r in regles}):
            a_faire = []
            for r in regles:
                if r.get("phase", 0) != ph:
                    continue
                env = dict(env0)
                for v, t in (r.get("soit") or {}).items():
                    env[v] = self.ev(t, env)
                if self.ev(r.get("quand", True), env):
                    a_faire.append((r, env))
            self._appliquer_lois(a_faire)

    def _appliquer_lois(self, a_faire):
        # effets des lois actives, de la plus lourde à la plus légère (ordre du fichier à poids égal) ; produit
        # pondéré (PoE-World) : un effet sur un attribut déjà pris par une loi STRICTEMENT plus lourde est écarté (journalisé)
        pris = {}
        for r, env in sorted(a_faire, key=lambda re: -re[0].get("poids", 1)):
            w = r.get("poids", 1)
            for e in r.get("alors", []):
                k = self._cle_effet(e, env)
                if k is not None and pris.get(k, w) > w:
                    self.conflits.append((r.get("nom"), e[0], pris[k], w))
                    continue
                if k is not None:
                    pris[k] = max(w, pris.get(k, w))
                self.fait(e, env)

    def _cle_effet(self, e, env):
        """(objet, attribut) touché par un effet simple, ou None (effets composés, création) : sert aux conflits."""
        op = e[0] if isinstance(e, list) and e else None
        if op in ATTRIBUT:
            return id(self.ev(e[1], env)), ATTRIBUT[op]
        if op in ("poser", "empiler", "depiler", "consommer", "recharger"):
            return "etat", e[1]
        if op == "poser_attr":
            return id(self.ev(e[1], env)), ("attr", self.ev(e[2], env))
        return None


# ===================================================================== mots nouveaux (CW-1xx)
# Deux façons de définir un mot pendant une partie (acceptées seulement si la porte de rejeu passe) :
# - "mots" : macros dans le langage lui-même (portée lexicale, sans récursion, profondeur ≤ PROF_MAX) ;
# - "fonctions" : dernier recours, une EXPRESSION Python pure vérifiée par liste blanche d'AST, sur valeurs simples.
TERMES_NATIFS = frozenset([
    "a_tag", "alea", "arrondi", "bloquant", "composantes", "contact_moteur", "debut_niveau", "div", "echelle", "intervalle",
    "plancher", "racine", "trier", "trier_desc", "visible",
    "argmin", "argmax", "attr_cache", "dernier_niveau", "donnees_de_niveau", "forme_modele", "param", "prefixe", "segment", "tags",
    "et", "ou", "non", "=", "!=", "<", "<=", ">", ">=", "+", "-", "*", "//", "%", "si", "liste", "longueur", "elem",
    "premier", "vide", "contient", "indice", "suivant", "table", "tous", "existe", "premier_tel_que", "filtrer",
    "action", "case_clic", "niveau", "vue", "nom", "pixel", "etat", "objets", "a", "objets_dans_boite", "x", "y", "largeur", "hauteur",
    "attr", "chevauche", "libre", "correspond", "correspond_rot", "epuise", "utilise", *TERMES_CANEVAS])
EFFETS_NATIFS = frozenset([
    "consommer", "recharger", "pousser", "refleter", "remodeler", "soit_creer", "tant_que",
    "instantane", "restaurer", "poser_motif", "poser_bloquant", "rendre_intangible",
    "si_alors", "pour", "poser", "empiler", "depiler", "poser_attr", "niveau_suivant", "gagner", "perdre", "deplacer",
    "placer", "tourner", "recolorer", "ecrire", "montrer", "calque", "creer", "retirer", *EFFETS_CANEVAS])
NATIFS = TERMES_NATIFS | EFFETS_NATIFS
PROF_MAX = 16
_QUANT = ("tous", "existe", "premier_tel_que", "filtrer")
_NOM_LITTERAL = {"etat": (0,), "poser": (0,), "empiler": (0,), "depiler": (0,), "consommer": (0,), "recharger": (0,),
                 "epuise": (0,)}  # argument = nom, pas un terme


def _verifier_nom(nom, deja):
    if not isinstance(nom, str) or not nom or nom.startswith(("$", "_")):
        raise ErreurLangage(f"nom de mot invalide : {nom!r}")
    if nom in NATIFS:
        raise ErreurLangage(f"le mot {nom!r} masque un mot natif : refusé")
    if nom in deja:
        raise ErreurLangage(f"le mot {nom!r} est déjà défini")


def _parcourir(t, lies, mots, fonctions, appels, nom):
    """Vérifie un corps de macro : variables liées, mots connus, arités ; collecte les macros appelées."""
    rec = lambda x, l=lies: _parcourir(x, l, mots, fonctions, appels, nom)
    if isinstance(t, str) and t.startswith("$"):
        if t[1:] not in lies:
            raise ErreurLangage(f"mot {nom!r} : variable {t} non liée (portée lexicale : paramètres seulement)")
        return
    if not isinstance(t, list) or not t or not isinstance(t[0], str):
        return  # littéral (nombre, chaîne, dict de filtre/table, liste de données)
    op, a = t[0], t[1:]
    if op in mots or op in fonctions:
        attendu = len((mots.get(op) or fonctions.get(op))["params"])
        if len(a) != attendu:
            raise ErreurLangage(f"mot {nom!r} : {op!r} appelé avec {len(a)} argument(s), arité {attendu}")
        if op in mots:
            appels.add(op)
    elif op not in NATIFS:
        raise ErreurLangage(f"mot {nom!r} : mot inconnu {op!r}")
    if op in _QUANT or op in ("pour", "argmin", "argmax"):
        if len(a) < 3 or not isinstance(a[0], str):
            raise ErreurLangage(f"mot {nom!r} : forme [{op}, \"$v\", liste, …] attendue")
        rec(a[1])
        dedans = lies | {a[0].lstrip("$")}
        for x in (a[2] if op == "pour" else [a[2]]):
            rec(x, dedans)
        return
    if op in ("trier", "trier_desc"):  # [op, liste, "$v", clé]
        rec(a[0])
        rec(a[2], lies | {a[1].lstrip("$")})
        return
    if op == "composantes":  # ["composantes", "$a", "$b", liste, relation]
        rec(a[2])
        rec(a[3], lies | {a[0].lstrip("$"), a[1].lstrip("$")})
        return
    if op == "soit_creer":  # ["soit_creer", "$v", modele, x, y, [effets…]]
        for x in a[1:4]:
            rec(x)
        for e in (a[4] if len(a) > 4 else []):
            rec(e, lies | {a[0].lstrip("$")})
        return
    if op == "tant_que":  # ["tant_que", cond, [effets…], max?]
        rec(a[0])
        for e in a[1]:
            rec(e)
        for x in a[2:]:
            rec(x)
        return
    if op == "si_alors":  # branches = listes d'effets
        rec(a[0])
        for branche in a[1:3]:
            for e in branche if isinstance(branche, list) else []:
                rec(e)
        return
    for i, x in enumerate(a):
        if i not in _NOM_LITTERAL.get(op, ()):
            rec(x)


def _verifier_mots(mots, fonctions):
    if not isinstance(mots, dict):
        raise ErreurLangage("« mots » doit être un objet {nom: définition}")
    for nom, d in mots.items():
        _verifier_nom(nom, fonctions)
        if not isinstance(d, dict) or "corps" not in d:
            raise ErreurLangage(f"mot {nom!r} : définition {{params, corps, sorte}} attendue")
        ps = d.get("params", [])
        if (not isinstance(ps, list) or len(set(ps)) != len(ps)
                or not all(isinstance(p, str) and len(p) > 1 and p[0] == "$" and p[1] != "_" for p in ps)):
            raise ErreurLangage(f"mot {nom!r} : params invalides (liste de \"$x\" distincts)")
        if d.get("sorte", "terme") not in ("terme", "effet"):
            raise ErreurLangage(f"mot {nom!r} : sorte {d.get('sorte')!r} (attendu terme|effet)")
    graphe = {}
    for nom, d in mots.items():
        lies, appels = {p[1:] for p in d.get("params", [])}, set()
        if d.get("sorte", "terme") == "effet":
            if not isinstance(d["corps"], list) or not all(isinstance(e, list) for e in d["corps"]):
                raise ErreurLangage(f"mot {nom!r} : un corps d'effet est une liste d'effets")
            for e in d["corps"]:
                _parcourir(e, lies, mots, fonctions, appels, nom)
        else:
            _parcourir(d["corps"], lies, mots, fonctions, appels, nom)
        graphe[nom] = appels
    etat = {}  # 1 = en cours, 2 = fini : détection de cycle (récursion directe ou mutuelle)

    def visite(n, chemin):
        etat[n] = 1
        for m in graphe[n]:
            if etat.get(m) == 1:
                raise ErreurLangage(f"récursion interdite : {' -> '.join([*chemin, m])}")
            if not etat.get(m):
                visite(m, [*chemin, m])
        etat[n] = 2
    for n in graphe:
        if not etat.get(n):
            visite(n, [n])
    return mots


# --------------------------------------------------------------------- bac à sable de fonctions pures
BUDGET_ELEMENTS = 10_000      # taille max d'une liste/tuple produite
BUDGET_PAS = 100_000          # itérations max (toutes compréhensions confondues) par appel
_APPELS_OK = frozenset(["abs", "min", "max", "len", "range", "sum", "round", "int", "sorted", "any", "all"])
_MATH_OK = frozenset(("sqrt", "floor", "ceil"))
_NOEUDS_OK = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.Store, ast.BinOp, ast.UnaryOp, ast.BoolOp,
              ast.Compare, ast.IfExp, ast.Tuple, ast.List, ast.Subscript, ast.Slice, ast.ListComp, ast.GeneratorExp,
              ast.comprehension, ast.Call, ast.Attribute,
              ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
              ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)
_LONG_EXPR = 2000


class _Budget(Exception):
    pass


def _taille(v):
    return len(v) + sum(_taille(x) for x in v if isinstance(x, (list, tuple))) if isinstance(v, (list, tuple)) else 0


def _simple(v, prof=0):
    """Valeur simple autorisée en entrée/sortie : nombre, booléen, None, listes/tuples de ces valeurs."""
    if isinstance(v, np.generic):
        v = v.item()
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, (list, tuple)) and prof < 32:
        return type(v)(_simple(x, prof + 1) for x in v)
    raise ErreurLangage(f"fonction : valeur non simple refusée ({type(v).__name__}) — nombres, booléens, listes seulement")


def _verifier_ast(arbre, params, nom):
    noms_ok = set(params) | _APPELS_OK
    for n in ast.walk(arbre):
        if isinstance(n, ast.comprehension):
            if n.is_async:
                raise ErreurLangage(f"fonction {nom!r} : compréhension asynchrone refusée")
            if not all(isinstance(c, (ast.Name, ast.Tuple, ast.Store)) for c in ast.walk(n.target)):
                raise ErreurLangage(f"fonction {nom!r} : cible de compréhension = noms seulement")
            for c in ast.walk(n.target):
                if isinstance(c, ast.Name):
                    noms_ok.add(c.id)
    for n in ast.walk(arbre):
        if not isinstance(n, _NOEUDS_OK):
            raise ErreurLangage(f"fonction {nom!r} : construction refusée ({type(n).__name__})")
        if isinstance(n, ast.Constant) and not (n.value is None or isinstance(n.value, (bool, int, float))):
            raise ErreurLangage(f"fonction {nom!r} : constante refusée ({type(n.value).__name__})")
        if isinstance(n, ast.Name) and (n.id.startswith("_") or n.id not in noms_ok
                                        and not (n.id == "math" and getattr(n, "_math", False))):
            raise ErreurLangage(f"fonction {nom!r} : nom refusé {n.id!r}")
        if isinstance(n, ast.Call):
            f = n.func
            if n.keywords:
                raise ErreurLangage(f"fonction {nom!r} : arguments nommés refusés")
            if isinstance(f, ast.Name) and f.id in _APPELS_OK:
                continue
            if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "math"
                    and f.attr in _MATH_OK):
                f._ok = f.value._math = True
                continue
            raise ErreurLangage(f"fonction {nom!r} : appel refusé ({ast.unparse(f)})")
        if isinstance(n, ast.Attribute) and not getattr(n, "_ok", False):
            raise ErreurLangage(f"fonction {nom!r} : attribut refusé ({ast.unparse(n)})")


class _Instrumente(ast.NodeTransformer):
    """Fait passer itérations, `range`, `*` et `+` par des gardes de budget."""

    def visit_comprehension(self, n):
        self.generic_visit(n)
        n.iter = ast.Call(ast.Name("_it", ast.Load()), [n.iter], [])
        return n

    def visit_BinOp(self, n):
        self.generic_visit(n)
        if isinstance(n.op, (ast.Mult, ast.Add)):
            g = "_mul" if isinstance(n.op, ast.Mult) else "_add"
            return ast.Call(ast.Name(g, ast.Load()), [n.left, n.right], [])
        return n


def _compiler_fonction(nom, d, deja):
    _verifier_nom(nom, deja)
    if not isinstance(d, dict) or not isinstance(d.get("expr"), str):
        raise ErreurLangage(f"fonction {nom!r} : définition {{params, expr}} attendue")
    ps, src = d.get("params", []), d["expr"]
    if (not isinstance(ps, list) or len(set(ps)) != len(ps)
            or not all(isinstance(p, str) and p.isidentifier() and not p.startswith("_") and p not in _APPELS_OK
                       and p != "math" for p in ps)):
        raise ErreurLangage(f"fonction {nom!r} : params invalides (identifiants distincts, sans « _ » initial)")
    if len(src) > _LONG_EXPR:
        raise ErreurLangage(f"fonction {nom!r} : expression trop longue (> {_LONG_EXPR} caractères)")
    try:
        arbre = ast.parse(src, mode="eval")  # une EXPRESSION : toute instruction est une erreur de syntaxe ici
    except SyntaxError as e:
        raise ErreurLangage(f"fonction {nom!r} : pas une expression Python valide ({e.msg})") from None
    _verifier_ast(arbre, ps, nom)
    arbre = ast.fix_missing_locations(_Instrumente().visit(arbre))
    return {"params": ps, "code": compile(arbre, f"<fonction {nom}>", "eval")}


def _appeler_fonction(f, args, nom):
    pas = [0]  # itérations + éléments alloués, cumulés sur l'appel

    def compter(k):
        pas[0] += k
        if pas[0] > BUDGET_PAS:
            raise _Budget(f"plus de {BUDGET_PAS} pas (itérations + éléments alloués)")

    def borne(v):
        if isinstance(v, (list, tuple, range)):
            if len(v) > BUDGET_ELEMENTS:
                raise _Budget(f"taille {len(v)} > {BUDGET_ELEMENTS}")
            compter(len(v))
        return v

    def _it(xs):
        for x in xs:
            compter(1)
            yield x

    def _mul(a, b):
        for s, k in ((a, b), (b, a)):
            if isinstance(s, (list, tuple)) and isinstance(k, int):
                if len(s) * k > BUDGET_ELEMENTS:
                    raise _Budget(f"taille {len(s) * k} > {BUDGET_ELEMENTS}")
                compter(max(len(s) * k, 0))
        return a * b

    def _add(a, b):
        return borne(a + b)

    def _range(*a):
        return borne(range(*a))

    def _sorted(x):
        return borne(sorted(_it(x)))

    def _vers_liste(g):  # sum/min/max/any/all/len sur itérable : passent aussi par le compteur
        return lambda *a: g(*(_it(x) if isinstance(x, (list, tuple, range)) else x for x in a))

    def _sum(xs):  # sans argument « start » : pas de concaténation de listes (coût quadratique non compté)
        return sum(_it(xs) if isinstance(xs, (list, tuple, range)) else xs)

    glob = {"__builtins__": {}, "_it": _it, "_mul": _mul, "_add": _add, "range": _range, "sorted": _sorted,
            "abs": abs, "len": len, "round": round, "int": int, "sum": _sum, "min": _vers_liste(min),
            "max": _vers_liste(max), "any": _vers_liste(any), "all": _vers_liste(all),
            "math": types.SimpleNamespace(sqrt=math.sqrt, floor=math.floor, ceil=math.ceil)}
    glob.update(zip(f["params"], args, strict=True))
    try:
        r = eval(f["code"], glob)
        if isinstance(r, range):
            r = list(r)
        if _taille(r) > BUDGET_ELEMENTS:
            raise _Budget(f"résultat de taille {_taille(r)} > {BUDGET_ELEMENTS}")
    except _Budget as e:
        raise ErreurLangage(f"fonction {nom!r} : budget dépassé ({e})") from None
    except ErreurLangage:
        raise
    except Exception as e:  # noqa: BLE001 — erreur de calcul (division par zéro, index…) : erreur du programme de règles
        raise ErreurLangage(f"fonction {nom!r} : {type(e).__name__}: {e}") from None
    return _simple(r)


def compiler_mots(texte):
    """Vérifie et compile les sections « mots » et « fonctions » (lève ErreurLangage au moindre défaut)."""
    fs_def, mots = texte.get("fonctions") or {}, texte.get("mots") or {}
    if not isinstance(fs_def, dict):
        raise ErreurLangage("« fonctions » doit être un objet {nom: définition}")
    fonctions = {}
    for nom, d in fs_def.items():
        fonctions[nom] = _compiler_fonction(nom, d, fonctions)
    return _verifier_mots(mots, fonctions), fonctions


def mots_valides(regles):
    """Journal des mots définis par un fichier de règles : [{nom, genre, signature, sha}], trié par nom.
    À journaliser par l'appelant une fois la porte de rejeu passée. Lève ErreurLangage si une définition est invalide."""
    mots, _ = compiler_mots(regles)
    sortie = []
    for genre, defs in (("mot", mots), ("fonction", regles.get("fonctions") or {})):
        for nom, d in defs.items():
            ret = d.get("sorte", "terme") if genre == "mot" else "valeur"
            canon = json.dumps({"genre": genre, "nom": nom, "def": d}, sort_keys=True, ensure_ascii=False)
            sortie.append({"nom": nom, "genre": genre, "signature": f"{nom}({', '.join(d.get('params', []))}) -> {ret}",
                           "sha": hashlib.sha256(canon.encode()).hexdigest()[:12]})
    return sorted(sortie, key=lambda m: m["nom"])


def extraire_regles(texte):
    """CW-115 (1) : le LLM raisonne LIBREMENT, puis donne son bloc de règles ; on prend le DERNIER bloc ```json … ``` (ou, à
    défaut, le dernier objet JSON {…} complet du texte) qui contient "regles". Rend le dict, ou lève ErreurLangage."""
    import re
    blocs = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", texte, flags=re.DOTALL)
    if not blocs:  # dernier objet équilibré du texte
        fins = [i for i, c in enumerate(texte) if c == "}"]
        for fin in reversed(fins):
            prof = 0
            for deb in range(fin, -1, -1):
                prof += {"}": 1, "{": -1}.get(texte[deb], 0)
                if prof == 0:
                    blocs.append(texte[deb:fin + 1])
                    break
            if blocs:
                break
    for b in reversed(blocs):
        try:
            d = json.loads(b)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "regles" in d:
            return d
    raise ErreurLangage("aucun bloc de règles JSON avec « regles » dans la réponse")
