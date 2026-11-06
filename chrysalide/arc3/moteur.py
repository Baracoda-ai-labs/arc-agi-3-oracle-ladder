# SPDX-License-Identifier: MIT-0
"""P2 de CW-126 — point d'entrée du moteur formel dans l'agent (CHRYS_MOTEUR=1, éteint par défaut).

Interface minimale : `MoteurFormel.proposer(historique) -> (plan, programme) | None`.
  historique = {"grilles": [g0, g1, …], "lots": [lot0, …], "precedents": [{"grilles", "lots", "finale"}, …]}
    - grilles/lots : le niveau COURANT, tel que l'agent l'a vu (images 64×64 et lots `{"actions": [...]}` de Franzen) ;
    - precedents : niveaux déjà réussis (même format, `finale` = lot qui a fini le niveau) ;
    rien d'autre : AUCUN accès au moteur du jeu (pas d'oracle).
  plan = liste d'actions au format de Franzen ({"action": "UP"}, …) ; programme = texte du langage (`langage.py`).
Le moteur fournit aussi sa perception (`scene`, `vue`, `rendu`) pour que la PORTE de rejeu exact (`porte`, interpréteur de
référence de A, image par image) soit jugée hors du moteur : c'est elle qui décide si le plan est joué (branche.py).
Porte 2 (`porte_but`, CW-138) : le plan, déroulé dans ce même programme, doit finir en victoire simulée ; sinon refus.
`MoteurC` : chaîne de la session C (perception faits.Trajectoire → induction ASP `induire` → `export_langage.exporter` →
`plan.planifier`), budget CPU par appel CHRYS_MOTEUR_BUDGET_S (défaut 5 s) ; rend None dès qu'une étape ne sait pas."""
import os
import time

import numpy as np

from chrysalide.arc3.ontologie_exec import Scene, rendre

CODES = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5, "UNDO": 7}
NOMS = {v: k for k, v in CODES.items()}
MOTEUR_VERS_MODELE = {"ACTION1": "UP", "ACTION2": "DOWN", "ACTION3": "LEFT", "ACTION4": "RIGHT", "ACTION5": "SPACE",
                      "ACTION6": "MOUSE", "ACTION7": "UNDO"}


def nom_action(a):
    """Action d'un lot de Franzen → tuple attendu par `Programme.step` : ("UP",) … ou ("MOUSE", row, col)."""
    n = str(a.get("action") or "").strip().upper()
    n = MOTEUR_VERS_MODELE.get(n, n)
    return (n, a.get("row"), a.get("col")) if n == "MOUSE" else (n,)


def budget_s():
    try:
        return float(os.environ.get("CHRYS_MOTEUR_BUDGET_S", "5"))
    except ValueError:
        return 5.0


class MoteurFormel:
    """Interface. Perception par défaut = pixels 64×64 : un sprite par composante 4-connexe d'une couleur hors fond."""

    def proposer(self, historique):
        return None

    def classes_inconnues(self, precedents, g0):
        """Déclencheur classe_inconnue (CW-133) : classes de g0 que la théorie des niveaux réussis ignore ; None = inconnu."""

    def attributs(self, prog, scene):
        """P10 (CW-134) : attributs d'état d'une théorie vérifiée (état caché du programme : jauge, vies, recharges, sens…),
        valeurs scalaires seulement ; {} si la théorie n'en a pas."""
        return {k: v for k, v in sorted((getattr(prog, "etat", None) or {}).items())
                if isinstance(v, (bool, int, float, str)) and not str(k).startswith("_")}

    def scene(self, g):
        g = np.asarray(g)
        fond = int(np.bincount(g.ravel()).argmax())
        return Scene(g.shape, fond, fond, [_sprite(o) for o in _composantes(g, fond)])

    def vue(self, g):
        return np.asarray(g)

    def rendu(self, scene):
        return rendre({"vue": scene.vue, "fond": scene.fond, "letterbox": scene.letterbox, "camera": scene.camera,
                       "sprites": [s for s in scene.sprites if s["visible"]]})


def porte(moteur, programme, grilles, lots):
    """Porte de rejeu EXACT, hors du moteur : la scène perçue sur la 1re image est déroulée par l'interpréteur de A, coup par
    coup, et comparée à CHAQUE image observée. → (Programme, scène à l'état courant) si tout est exact, sinon None.
    Un lot de plusieurs actions est déroulé en entier puis comparé (seule l'image finale est vue)."""
    from chrysalide.arc3.langage import Programme
    try:
        prog, sc = Programme(programme), moteur.scene(grilles[0])
        for lot, g1 in zip(lots, grilles[1:], strict=True):
            for a in lot["actions"]:
                prog.step(sc, nom_action(a))
            if sc.issue is not None or not np.array_equal(moteur.rendu(sc), moteur.vue(g1)):
                return None
    except Exception:  # noqa: BLE001 — programme mal formé, perception impossible : la porte refuse
        return None
    return prog, sc


GAGNE = ("niveau", "victoire")


def porte_partielle(moteur, programme, grilles, lots):
    """CW-236 (Thomas : « jamais demandé des règles parfaites ») : rejeu RECALÉ. À chaque transition, la scène est relue
    sur l'image observée (perception), l'état caché du programme continue ; on compte les transitions dont l'image prédite
    est exacte. → (Programme, scène perçue à l'état courant, taux d'explication) ; None si le programme ne s'exécute pas."""
    import copy

    from chrysalide.arc3.langage import Programme
    try:
        prog, ok = Programme(programme), 0
        for lot, g0, g1 in zip(lots, grilles, grilles[1:], strict=False):
            sc = moteur.scene(g0)
            for a in lot["actions"]:
                prog.step(sc, nom_action(a))
            ok += sc.issue is None and bool(np.array_equal(moteur.rendu(sc), moteur.vue(g1)))
        sc = moteur.scene(grilles[-1])
        return prog, sc, (ok / len(lots)) if lots else 0.0, copy
    except Exception:  # noqa: BLE001 — programme qui ne s'exécute pas : aucune théorie partielle
        return None


def porte_but_partielle(moteur, programme, grilles, lots, plan):
    """Porte 2 sur la théorie partielle : le plan déroulé depuis la scène PERÇUE à l'état courant (copie) finit-il sur le
    but ? → (n coups jusqu'au gain simulé | None, issue, taux d'explication)."""
    r = porte_partielle(moteur, programme, grilles, lots)
    if r is None:
        return None, "erreur", 0.0
    prog, sc, taux, copy = r
    prog, sc = copy.deepcopy(prog), copy.deepcopy(sc)
    try:
        for i, a in enumerate(plan):
            prog.step(sc, nom_action(a))
            if sc.issue in GAGNE:
                return i + 1, sc.issue, taux
            if sc.issue is not None:
                return None, sc.issue, taux
    except Exception:  # noqa: BLE001
        return None, "erreur", taux
    return None, sc.issue, taux


def porte_but(moteur, programme, grilles, lots, plan):
    """Porte 2 (CW-138, Executable World Models 2607.15439) : le plan est déroulé dans le programme, sur une COPIE neuve de
    la scène perçue amenée à l'état courant par le rejeu de la porte 1 (la scène suivie n'est pas touchée). → (n, issue) :
    n = nombre de coups jusqu'au 1er coup où l'issue simulée est « niveau » ou « victoire » (le plan est tronqué là),
    None si la simulation ne gagne pas (issue finale rendue : None, « defaite », « rejeu » ou « erreur »)."""
    r = porte(moteur, programme, grilles, lots)
    if not r:
        return None, "rejeu"
    prog, sc = r
    try:
        for i, a in enumerate(plan):
            prog.step(sc, nom_action(a))
            if sc.issue in GAGNE:
                return i + 1, sc.issue
            if sc.issue is not None:
                return None, sc.issue
    except Exception:  # noqa: BLE001 — simulation impossible : but non compris, la porte refuse
        return None, "erreur"
    return None, sc.issue


def _composantes(c, fond, exclues=frozenset()):
    from chrysalide.arc3.logique.faits import objets
    return objets(c, fond, exclues)


def _sprite(o):
    col, forme, x, y = o
    px = np.full((max(dy for _, dy in forme) + 1, max(dx for dx, _ in forme) + 1), -1, dtype=np.int16)
    for dx, dy in forme:
        px[dy, dx] = col
    return {"pixels": px, "x": x, "y": y, "couche": 0, "tags": []}


def reserve_coups(grilles, n_coups):
    """C (CW-321/324, CHRYS_ECONOMIE) : réserve de coups restante, lue sur la barre de budget classée par D
    (`economie.classer`, étiquette « budget » seulement) et le RYTHME observé sur la trajectoire (coups par case perdue).
    → {coups, marge, rythme, statut} ou None (pas de barre, pas assez vu). Statut « supposé » : aucune fin à zéro n'a été
    vue ici, la défaite à zéro vient de l'audit (re86 : GAME_OVER au coup où la barre s'éteint, CCM-175-C)."""
    import math

    from chrysalide.arc3.economie import classer
    if n_coups < 8 or len(grilles) != n_coups + 1:
        return None
    try:
        inds = [i for i in classer(grilles, ["coup"] * n_coups) if "budget" in i["etiquettes"]]
    except Exception:  # noqa: BLE001 — perception de l'interface impossible : pas de réserve
        return None
    if not inds:
        return None
    m, st = inds[0]["mesure"], inds[0]["stats"]
    baisse = st["neg"] >= st["pos"]
    perdu = (m[0] - m[-1]) if baisse else (m[-1] - m[0])
    if perdu <= 0:
        return None
    rythme = n_coups / perdu
    # la zone de D ne couvre que les cases DÉJÀ consommées (celles qui ont changé) : la réserve se compte sur toute la
    # ligne (ou colonne) de la barre, en cases de la couleur que la barre avait au départ sur ces cases
    x0, y0, x1, y1 = inds[0]["boite"]
    g0, g1 = np.asarray(grilles[0]), np.asarray(grilles[-1])
    vals, n = np.unique(g0[y0:y1 + 1, x0:x1 + 1], return_counts=True)
    barre = int(vals[n.argmax()])
    ligne = g1[y0:y1 + 1, :] if (x1 - x0) >= (y1 - y0) else g1[:, x0:x1 + 1]
    reste = int((ligne == barre).sum())
    return {"coups": int(reste * rythme), "marge": math.ceil(2 * rythme), "rythme": round(rythme, 2), "statut": "supposé",
            "boite": (x0, y0, x1, y1), "barre": barre}


def reste_barre(grille, res):
    """Cases de la barre (boîte et couleur de `reserve_coups`) encore allumées sur une autre image du même niveau."""
    x0, y0, x1, y1 = res["boite"]
    g = np.asarray(grille)
    ligne = g[y0:y1 + 1, :] if (x1 - x0) >= (y1 - y0) else g[:, x0:x1 + 1]
    return int((ligne == res["barre"]).sum())


class MoteurC(MoteurFormel):
    """Chaîne de C. Perception = vraie grille (échelle et décalage déduits des images, jauge masquée par le masque de B) ;
    classe = couleur (hypothèse de l'exporteur). Limites actuelles (→ None) : voir TODO."""

    def __init__(self, budget=None, limite_plan=50000):
        self.budget, self.limite_plan, self.tr, self.infos = budget, limite_plan, None, {}

    def proposer(self, historique):
        t0, b = time.process_time(), self.budget if self.budget is not None else budget_s()
        self.infos, self.th_releve = {}, None
        eco = None
        if os.environ.get("CHRYS_ECONOMIE", "1") == "1":  # F (CW-333) : réserve DANS l'état du planificateur, avant la recherche
            from chrysalide.arc3.logique.economie_plan import categorie, reserve_niveau
            res0 = reserve_niveau(historique)  # niveau en cours, sinon rythme du niveau précédent (début de niveau)
            if res0 is not None:  # barème : fiche de famille, sinon lu sur la barre (jeu inconnu), sinon 1 par action
                eco = (max(0, res0["coups"] - res0["marge"]), categorie(historique, res0))
                self.infos["reserve_plan"] = {"coups": eco[0], "cout": eco[1], "statut": res0.get("statut")}
        try:
            if eco is not None:
                from chrysalide.arc3.logique.economie_plan import avec_reserve
                with avec_reserve(*eco):
                    r = self._proposer(historique, t0, b)
            else:
                r = self._proposer(historique, t0, b)
        except Exception as e:  # noqa: BLE001 — clingo absent, perception impossible… : le moteur se tait, Franzen continue
            self.infos["refus"] = f"erreur : {type(e).__name__}: {e}"[:200]
            r = None
        self.infos["cpu_s"] = round(time.process_time() - t0, 3)
        if r is not None and self.infos["cpu_s"] > b:
            self.infos["refus"], r = "budget dépassé", None
        if r is not None and r[0] and os.environ.get("CHRYS_ECONOMIE", "1") == "1":  # C (CW-321/324) : réserve de coups
            res = reserve_coups(historique.get("grilles", []), len(historique.get("lots", [])))
            if res is not None:
                self.infos["reserve"] = res
                if len(r[0]) > res["coups"] - res["marge"]:
                    self.infos["refus"] = f"plan de {len(r[0])} coups > réserve ≈ {res['coups']} (marge {res['marge']})"
                    r = None
        if r is not None and r[0] and eco is not None:  # F : même garde pour tout planificateur, début de niveau compris
            from chrysalide.arc3.logique.economie_plan import fonction_cout
            f = fonction_cout(eco[1])
            if f is not None and sum(f(a) for a in r[0][:-1]) >= eco[0]:  # le dernier coup (gagnant) est gratuit
                self.infos["refus"] = f"plan au-delà de la réserve ({eco[0]} coups, {self.infos['reserve_plan']['statut']})"
                r = None
        if r is not None and os.environ.get("CHRYS_RELEVE") == "1":  # C (CCM-077-D) : porte de confiance + borne
            try:
                r = self._releve(historique, r, eco)
            except Exception as e:  # noqa: BLE001 — perception de la vie gagnante impossible : refus, Franzen continue
                self.infos["refus"], r = f"relève : erreur {type(e).__name__}: {e}"[:200], None
        return r

    def _releve(self, h, r, eco):
        """Relève après victoire de Franzen : le plan ne passe que si la théorie prédit sans erreur les 10 dernières
        transitions de la vie gagnante du niveau précédent ET s'il est plus court que 0,8 × les coups de Franzen."""
        from chrysalide.arc3.logique.confiance import borne_plan, porte
        from chrysalide.arc3.logique.faits import Trajectoire
        from chrysalide.arc3.logique.theorie import egal
        prec = h.get("precedents") or []
        th = getattr(self, "th_releve", None)
        if not prec or th is None:
            self.infos["refus"] = "relève : pas de niveau précédent" if not prec else "relève : pas de théorie"
            return None
        p = prec[-1]  # hist de branche.py : remis à zéro à chaque mort → la vie gagnante seule
        pa, fin = _codes_c(p["lots"]), _codes_c([p["finale"]])
        if pa is None or fin is None or len(p["grilles"]) != len(pa) + 1:
            self.infos["refus"] = "relève : vie gagnante illisible"
            return None
        tr = Trajectoire(p["grilles"], pa)
        n = len(pa)
        if not any(not egal(tr.cases[t], tr.cases[t + 1], tr.exclues) for t in range(max(0, n - 10), n)):
            # rien ne bouge dans ce qui est jugé (perception dégénérée) : « tout reste fixe » serait jugé juste à tort
            self.infos["refus"] = "relève : aucun changement perçu dans la vie gagnante"
            return None
        po = porte(th, tr, 10)
        coups = len(pa) + 1  # finale comprise
        self.infos["releve"] = {**po, "coups_franzen": coups, "plan": len(r[0])}
        if not po["ouverte"]:
            self.infos["refus"] = f"relève : porte fermée ({po['justes']}/{po['vues']} justes)"
            return None
        if not borne_plan(r[0], coups, eco[0] if eco is not None else None):
            self.infos["refus"] = f"relève : plan de {len(r[0])} coups ≥ 0,8 × {coups} (Franzen)"
            return None
        return r

    def _proposer(self, h, t0, b):
        from chrysalide.arc3.logique.faits import Trajectoire
        from chrysalide.arc3.logique.induction import induire
        from chrysalide.arc3.logique.plan import planifier
        from chrysalide.arc3.logique.theorie import monde_final, rejeu

        def reste():
            return max(0.2, b - (time.process_time() - t0))

        acts = _codes_c(h["lots"])  # clics compris : ("clic", x, y) en pixels de la vue (CCM-054-C)
        debut = (not h["lots"] and os.environ.get("CHRYS_RELEVE") == "1" and bool(h.get("precedents"))
                 and bool(h.get("grilles")))  # C (CW-424) : relève = plan dès la 1re image du niveau, sans coup joué
        if (not h["lots"] and not debut) or acts is None:
            # lots de plusieurs actions : découpés en amont par branche.py (films, CW-166) ; reste un lot non découpable
            self.infos["refus"] = "aucune transition" if not h["lots"] else "lot multiple"
            return None
        def percevoir(k=None):
            """Perception + induction sur les k premières transitions du niveau (toutes si None)."""
            prec = []
            for p in h.get("precedents", []):
                pa, fin = _codes_c(p["lots"]), _codes_c([p["finale"]])
                if pa is not None and fin is not None:
                    prec.append((Trajectoire(p["grilles"], pa), None, fin[0]))
            ancienne = induire(prec, limite_s=reste())[0] if prec else None
            g_, a_ = (h["grilles"], acts) if k is None else (h["grilles"][:k + 1], acts[:k])
            tr = _trajectoire_heritee(g_, a_, prec)
            if os.environ.get("CHRYS_FILMS_EVT") == "1":  # E (CW-441) : événements de film de chaque coup, pour l'induction
                tr.evenements = _evenements_films(g_, (h.get("films") or [])[:len(a_)], len(a_), acts=a_)
            vies = []  # D (CHRYS_VIES, ar25 N2) : vies perdues du niveau = sources d'induction de plus
            for v in h.get("vies", []) if os.environ.get("CHRYS_VIES") == "1" else []:
                va = _codes_c(v["lots"])
                if va:
                    vies.append((Trajectoire(v["grilles"], va), None, None))
            th, _ = induire([(tr, None, None), *vies], limite_s=reste(), anciennes=ancienne)
            ctrl = h.get("controle")  # E (CW-458) : objet contrôlé vu aux films, hypothèse prioritaire, tombe au rejeu
            if os.environ.get("CHRYS_P1_CONTROLE_FILMS") in ("1", "2") and ctrl is not None:
                th.hors_jeu = tr.exclues
                ok0 = rejeu(th, tr)[0]
                inf = {"couleur": ctrl, "libre": ok0, "n": len(a_)}
                if ok0 < len(a_):
                    th2, _ = induire([(tr, None, None), *vies], limite_s=reste(), anciennes=ancienne, controle=ctrl)
                    th2.hors_jeu = tr.exclues
                    inf["force"] = rejeu(th2, tr)[0]
                    if inf["force"] > ok0:
                        th, inf["adopte"] = th2, True
                self.infos["controle_films"] = inf
            return (prec, ancienne, tr, vies, th), tr, th
        if os.environ.get("CHRYS_PERCEPTION_PORTEFEUILLE") == "1":  # D (CW-316) : la perception qui prédit le mieux
            from chrysalide.arc3.logique.portefeuille import choisir
            prec, ancienne, tr, vies, th = choisir(percevoir, len(acts), self.infos)
        else:
            prec, ancienne, tr, vies, th = percevoir()[0]
        if debut and ancienne is not None:  # rien vu du niveau : réinduire sur 0 transition perd les lois (murs) ; la
            th = ancienne                    # théorie des niveaux gagnés telle quelle (sk01 N2 : plan à travers un mur)
            self.infos["releve_ancienne"] = True
        if vies:
            self.infos["vies"] = len(vies)
        # Le transfert est un prior révisable, jamais un ajout irrévocable.
        if ancienne is not None and rejeu(th, tr)[0] < len(tr.actions):
            froid, _ = induire([(tr, None, None)], limite_s=reste())
            if rejeu(froid, tr)[0] > rejeu(th, tr)[0]:
                th = froid
                self.infos["transfert_rejete"] = True
        if getattr(th, "jauge", ()):  # C (CCM-018-F) : réserve en vigueur = min(lecture de F, loi de jauge de C)
            from chrysalide.arc3.logique.economie_plan import resserrer
            self.infos["reserve_c"] = resserrer(th.jauge[0])
        self.tr = tr  # requis aussi par le fallback plan_langage
        th.hors_jeu = tr.exclues
        self.th_releve = th  # C (CCM-077-D) : théorie jugée par la porte de relève
        # candidates, de la plus fidèle au niveau courant à la plus hardie : la théorie induite ; la même sans les murs
        # supposés qui barrent son but (pour_but) ; la théorie du niveau précédent telle quelle. Chacune doit rejouer
        # exactement le niveau courant DANS LE SIMULATEUR DE C (tri interne) ; la porte de branche.py rejuge ensuite.
        cands = [th] + ([th.pour_but(th.but)] if th.but is not None else []) + ([ancienne] if ancienne else [])
        if ancienne is not None and _transfert():  # D (CW-234) : la théorie des niveaux réussis rejoue tout ce qui est vu
            ancienne.hors_jeu = tr.exclues           # du niveau courant → elle passe d'abord (même cohérence, plus
            ok_a, n_a, _ = rejeu(ancienne, tr)       # d'expérience : une réinduction sur peu de coups perd des lois)
            if ok_a == n_a:
                cands = ([ancienne] + ([ancienne.pour_but(ancienne.but)] if ancienne.but is not None else [])
                         + [c for c in cands if c is not ancienne])
                self.infos["ancienne_dabord"] = True
            else:  # couleurs changées d'un niveau à l'autre (ft09 N3) : théorie précédente RENOMMÉE (transfert.py)
                from chrysalide.arc3.logique.transfert import fusionner, transferer
                t2, m, ok_r = transferer(ancienne, tr, rejeu)
                th.hors_jeu = tr.exclues
                ok_th = rejeu(th, tr)[0]
                if m and ok_r > ok_th:
                    cands = [t2] + ([t2.pour_but(t2.but)] if t2.but is not None else []) + cands
                    self.infos["transfert_renomme"] = {str(a): b for a, b in m.items()}
                # CW-258 : FUSION (lois locales + lois anciennes non contredites, sans conjectures) si elle rejoue tout
                fus = fusionner(th, t2 if m else ancienne)
                fus.hors_jeu = tr.exclues
                if (os.environ.get("CHRYS_TRANSFERT_FUSION", "1") == "1" and fus != th
                        and rejeu(fus, tr)[0] == len(tr.actions)):
                    cands = [fus] + ([fus.pour_but(fus.but)] if fus.but is not None else []) + cands
                    self.infos["transfert_fusion"] = True
        vues = set(acts) | {a for t, _, f in prec for a in [*t.actions, f]}  # actions déjà jouées par l'agent
        offertes = sorted(a for a in vues if a in NOMS and a != 7)
        refus = []
        sim = _simulateur_exact(h)
        if sim is not None:  # C (CCM-190-B) : dynamique EXACTE fournie, but inféré ; portes faibles (1er coup joué, puis réobservé)
            self.porte_propre = True
            # actions du JEU (CCM-194-B) : `sim.actions()` si le simulateur les donne, sinon flèches et SPACE ; pas UNDO
            jeu = [a for a in (sim.actions() if hasattr(sim, "actions") else (1, 2, 3, 4, 5)) if a in NOMS and a != 7]
            r = _plan_exact(sim, th, tr, sorted(set(jeu) | set(offertes)) + _clics_offerts(th, tr), self.limite_plan, t0, b,
                            _buts_proposes(h))
            if r is None:
                self.infos["refus"] = "dynamique exacte : aucun but supposé atteignable"
                return None
            but, plan, inf = r
            self.infos.update(inf, but_suppose=str(but), origine="dynamique_exacte", porte1_c=True, porte2_c=True)
            return [_lot_c(a, tr) for a in plan], None
        for c in cands:
            c.hors_jeu = tr.exclues
            ok, n, _ = rejeu(c, tr)
            if ok < n:
                if c is ancienne:  # déclencheur contre_exemple : la théorie des niveaux réussis ne rejoue plus ce niveau
                    self.infos["ne_rejoue_plus"] = True
                r = _plan_partiel(self, c, tr, offertes, h, t0, b) if os.environ.get("CHRYS_PARTIEL") in ("1", "2") else None
                if r is not None:
                    return r
                refus.append("ne rejoue pas (C)" + (f" ; partiel : {self.infos.pop('partiel_refus')}"
                                                    if "partiel_refus" in self.infos else ""))
                continue
            self._couches = c.couches()
            prog, non = _exporter(c, tr.taille)
            if non:
                # TODO(CW-126) : poussée, autonomes, fond_solide, clics, reflets, annulation non exportés (export_langage.py)
                refus.append(f"non exporté : {non}")
                continue
            actions = offertes + (_clics_offerts(c, tr) if c.motif else [])
            if c.but is None:
                if os.environ.get("CHRYS_BUT_SUPPOSE") != "1":
                    refus.append("pas de but")
                    continue
                # D (après CW-196, PLAN 32) : buts candidats non réfutés (faux sur tous les états vus), dans l'ordre des
                # fréquences humaines du catalogue ; le 1er qui a un plan est joué (but SUPPOSÉ, revérifié coup par coup)
                r = _but_suppose(c, tr, actions, self.limite_plan, t0, b, _buts_proposes(h))
                if r is None:
                    refus.append("pas de but (aucun but supposé planifiable)")
                    continue
                c, plan, mondes = r
                self._couches = c.couches()
                prog, _ = _exporter(c, tr.taille)
                plan = _garde(self, c, tr, plan)
                if not plan:
                    refus.append("garde : " + self.infos["garde"])
                    continue
                self.tr = tr
                self.infos.update(mondes=mondes, theorie=c.texte(), **_mdl(c, tr), but_suppose=str(c.but), origine="but_suppose",
                                  **({"test_buts": c.test_buts} if getattr(c, "test_buts", None) else {}))
                return [_lot_c(a, tr) for a in plan], prog
            plan, mondes = planifier(c, monde_final(c, tr), tr.taille, actions, limite=self.limite_plan, deadline=t0 + b)
            plan = _garde(self, c, tr, plan) if plan else plan
            if plan == []:
                refus.append("garde : " + self.infos["garde"])
                continue
            if plan:
                self.tr = tr
                self.infos.update(mondes=mondes, theorie=c.texte(), **_mdl(c, tr), origine="planifier")
                return [_lot_c(a, tr) for a in plan], prog
            # CCM-076-C : la planification de la théorie de C n'a rien trouvé → recherche dans le LANGAGE guidée par le but,
            # puis par paliers (banc P0 : `but` 27/60 contre `largeur` 18/60), sous le budget du tour
            if os.environ.get("CHRYS_PLAN_LANGAGE", "1") == "1":
                r = _plan_langage(self, prog, h, offertes, reste())
                if r is not None:
                    self.tr = tr
                    self.infos.update(theorie=c.texte(), **_mdl(c, tr), origine="plan_langage")
                    return r, prog
            refus.append("pas de plan")
            if time.process_time() - t0 > b:
                break
        self.infos["refus"] = " ; ".join(refus)
        if "pas de but" in refus or "pas de plan" in refus:  # déclencheur sans_but : une théorie rejoue (C), aucun plan
            self.infos["sans_but"] = True
        return None

    def classes_inconnues(self, precedents, g0):
        from chrysalide.arc3.logique.faits import Trajectoire
        from chrysalide.arc3.logique.induction import classes_inconnues
        try:
            anc = theorie_precedente(precedents, budget_s())
            return None if anc is None else classes_inconnues(anc, Trajectoire([g0], []).etats[0])
        except Exception:  # noqa: BLE001 — clingo absent, perception impossible : inconnu
            return None

    # perception de C : la vraie grille, cases masquées (jauge) à -1 des deux côtés
    def scene(self, g):
        tr = self.tr
        h, w = tr.taille[1], tr.taille[0]
        # défi 4, étendu (CCM-175-B, dc22) : image DÉJÀ VUE du niveau → son état complété (décor sous le joueur, AMODAL),
        # sinon la porte partielle, recalée sur la perception brute, « révèle » un fond qui n'est pas là ; absent de la
        # perception allégée d'un ouvrier (etats vide) → perception de l'image
        etat = None
        if tr.etats and len(tr.cases) == len(tr.etats):
            if getattr(self, "_index_tr", None) is not tr:
                self._index_tr, self._index = tr, {}
                for t, c in enumerate(tr.cases):  # DERNIÈRE occurrence d'une image répétée : la mieux complétée
                    self._index[self._masquer(c).tobytes()] = t  # (ls20 : retour du joueur à sa case de départ)
            t = self._index.get(self.vue(g).tobytes())
            etat = tr.etats[t] if t is not None else None
        return Scene((h, w), tr.fond, tr.fond, [dict(_sprite(o), couche=getattr(self, "_couches", lambda c: 0)(o[0]))
                                                       for o in (etat if etat is not None else tr.etat(g))])

    def _masquer(self, c):
        c = np.array(c, dtype=np.int16)
        for r, q in self.tr.exclues:
            if 0 <= r < c.shape[0] and 0 <= q < c.shape[1]:
                c[r, q] = -1
        return c

    def vue(self, g):
        from chrysalide.arc3.logique.faits import cases
        tr = self.tr
        return self._masquer(cases(g, tr.s, tr.ox, tr.oy))

    def rendu(self, scene):
        h, w = scene.vue
        k = min(64 // w, 64 // h)
        gy, gx = (64 - h * k) // 2, (64 - w * k) // 2
        r = super().rendu(scene)[gy:gy + h * k:k, gx:gx + w * k:k]
        return self._masquer(np.where(r >= 16, r % 16, r))  # détails reclassés (faits.details) : vraie couleur


# ------------------------------------------------------------ CHRYS_TUTO : mini-tutoriel par niveau (E4 par_niveau v2, B)
TUTO_CALME, TUTO_BUDGET, TUTO_K = 8, 3, 10  # E4 : fin à 8 coups d'essai prédits sans surprise ou 3 h coups ; k théories


def tuto_budget(h=None, precedents=()):
    """CHRYS_TUTO_COUPS si posé ; sinon celui d'E4 = TUTO_BUDGET × h (coups humains du niveau, si le framework les montre) ;
    à défaut TUTO_BUDGET × coups joués au niveau précédent réussi (aucun oracle)."""
    try:
        return int(os.environ["CHRYS_TUTO_COUPS"])
    except (KeyError, ValueError):
        pass
    if h and os.environ.get("CHRYS_BUDGET") == "1":  # h seulement en développement (CW-086 : CHRYS_BUDGET éteint sur Kaggle)
        return TUTO_BUDGET * int(h)
    return TUTO_BUDGET * (len(precedents[-1]["lots"]) + 1) if precedents else 0


def _code_c(a):
    """Action de Franzen → action de C : 1..5, 7, ou ('clic', x, y) en pixels (MOUSE : row = y, col = x) ; None sinon."""
    n = nom_action(a)
    if n[0] == "MOUSE":
        return None if n[1] is None or n[2] is None else ("clic", int(n[2]), int(n[1]))
    return CODES.get(n[0])


# fréquence des formes de but chez les humains (catalogue de D, 789 jeux PuzzleScript) : All X on Y, No X, Some X on Y…
ORDRE_BUTS = {"copie": -1, "motif_rel": -1, "marques": -1, "modele": 1, "remplir": 0, "paires": 0, "absent": 1, "sortie": 2, "sortie_si": 2, "centre": 2, "emboite": 4, "ancre": 3}
MAX_BUTS_SUPPOSES = int(os.environ.get("CHRYS_BUTS_MAX", "16"))  # D (CW-458, CCM-097-D) : 0 = tous les candidats
MAX_BUTS_SUPPOSES = MAX_BUTS_SUPPOSES or 10_000


def _buts_proposes(h):
    """Hypothèses de but d'un proposeur (B, CW-228.2, format CCM-098-C) : `h["buts_proposes"]`, sinon le fichier JSON de
    CHRYS_BUTS ; liste ordonnée de noms de forme ("sortie") ou de formes ancrées (["sortie", 3, 9]) ; "indetermine" ignoré."""
    v = h.get("buts_proposes")
    if v is None and os.environ.get("CHRYS_BUTS"):
        import json
        from pathlib import Path
        try:
            v = json.loads(Path(os.environ["CHRYS_BUTS"]).read_text())
        except (OSError, ValueError):
            v = None
    return [x for x in (v or []) if x != "indetermine"]


def ordonner_proposes(cands, proposes):
    """Candidats cités par le proposeur d'abord, dans son ordre (forme seule : tous ceux de cette forme ; forme ancrée :
    ceux qui commencent ainsi), puis les autres dans leur ordre."""
    tete = []
    for p in proposes:
        cle = (p,) if isinstance(p, str) else tuple(p)
        tete += [x for x in cands if tuple(x[:len(cle)]) == cle and x not in tete]
    return tete + [x for x in cands if x not in tete]


def _candidats_buts(th, tr, proposes=()):
    """Buts candidats faux sur chaque état vu du niveau (sinon le niveau serait déjà fini), alternés par forme
    (ORDRE_BUTS), les hypothèses du proposeur d'abord."""
    from chrysalide.arc3.logique.induction import buts_candidats
    from chrysalide.arc3.logique.theorie import Theorie
    couleurs = {o[0] for e in tr.etats for o in e}
    cands = [x for x in buts_candidats(th, couleurs) if not any(Theorie._vrai(x, e) for e in tr.etats)]
    cands = _ordre_centre(cands, tr)
    # essai ALTERNÉ entre formes (ordre des fréquences), pas par blocs : sinon les « remplir », nombreux, prennent toutes
    # les places et « sortie » n'est jamais essayé (banc des décisions, CW-226.5 : 66 niveaux 1 bloqués ainsi)
    par_forme = {}
    for x in cands:
        par_forme.setdefault(x[0], []).append(x)
    from chrysalide.arc3 import memoire  # E (CW-410) : CHRYS_MEMOIRE=1 → fréquence inter-jeux d'abord ; éteint = inchangé
    cle = (lambda k: memoire.cle_forme(k, ORDRE_BUTS)) if memoire.actif() else (lambda k: (ORDRE_BUTS.get(k, 9), k))
    files = [par_forme[k] for k in sorted(par_forme, key=cle)]
    return ordonner_proposes([f[i] for i in range(max(map(len, files), default=0)) for f in files if i < len(f)], proposes)


def _ordre_centre(cands, tr):
    """E (CCM-046/047-E), écrit par C, sous CHRYS_BUT_CENTRE : buts `centre(a, b)` ordonnés. (1) écartés si b n'a aucun
    objet d'au plus 2 cases, ou a aucun d'au moins 3, dans le dernier état ; (2) reculés si a est dans la bande du bord, ou
    si le petit objet change ou touche la bande du bord (interface) ; (3) puis du plus loin au plus près du départ de
    l'acteur. Les autres formes ne bougent pas."""
    if os.environ.get("CHRYS_BUT_CENTRE", "0") != "1" or not tr.etats:
        return cands
    from chrysalide.arc3.logique.theorie import cells
    w, h = tr.taille
    fin, debut = tr.etats[-1], tr.etats[0]

    def cle(b):
        _, a, c = b
        petits = [o for o in fin if o[0] == c and len(o[1]) <= 2]
        grands = [o for o in fin if o[0] == a and len(o[1]) >= 3]
        if not petits or not grands:  # CCM-047-E : sans acteur d'au moins 3 cases, « centre » ne peut devenir vrai
            return None
        def interface(o):
            return (not all(o in e for e in tr.etats)
                    or any(x <= 1 or y <= 1 or x >= w - 2 or y >= h - 2 for x, y in cells(o)))
        def bord(o):  # CCM-047-E : un acteur dans la bande du bord est une interface (jauge), même s'il change
            return any(x <= 1 or y <= 1 or x >= w - 2 or y >= h - 2 for x, y in cells(o))
        dep = [o for o in debut if o[0] == a]
        ax, ay = (dep[0][2], dep[0][3]) if dep else (0, 0)
        loin = max(abs(o[2] - ax) + abs(o[3] - ay) for o in petits if not interface(o)) if any(
            not interface(o) for o in petits) else -1
        return (all(bord(o) for o in grands), loin < 0, -loin)
    centres = [b for b in cands if b[0] == "centre"]
    cles = {b: cle(b) for b in centres}
    gardes = iter(sorted((b for b in centres if cles[b] is not None), key=lambda b: cles[b]))
    return [next(gardes) if b[0] == "centre" else b for b in cands if b[0] != "centre" or cles[b] is not None]


def _simulateur_exact(h):
    """C (CCM-190-B, jour 1 de CW-280) : CHRYS_DYNAMIQUE_EXACTE = "module:fonction" ; fonction(historique) → simulateur
    EXACT de la dynamique au point courant, SANS règle de victoire (le but reste à inférer), ou None. Interface :
    `etat()` (état courant), `pas(etat, lot) → (etat2, perdu)` avec `lot` au format de l'agent ({"action": "UP"} ou
    {"action": "MOUSE", "row", "col"}), `image(etat)` (grille 64×64), `cle(etat)` (hachable) ; facultatif : `actions()`
    (codes de C offerts par le jeu, 1..5 ; défaut : flèches et SPACE)."""
    spec = os.environ.get("CHRYS_DYNAMIQUE_EXACTE")
    if not spec:
        return None
    import importlib
    mod, fn = spec.split(":")
    return getattr(importlib.import_module(mod), fn)(h)


def _plan_exact(sim, th, tr, actions, limite, t0, b, proposes=()):
    """Plan dans la dynamique EXACTE fournie (largeur), vers un but SUPPOSÉ (mêmes candidats que `_but_suppose`), jugé
    sur l'état PERÇU (image du simulateur → objets, même échelle que la trajectoire). CHRYS_TEST_BUTS=1 : choix par
    test actif (mêmes U, D, V que `_but_teste`). → (but, plan d'actions de C, infos) ou None."""
    from collections import deque

    from chrysalide.arc3.logique.faits import cases, objets
    from chrysalide.arc3.logique.theorie import Theorie, cells
    cands = _candidats_buts(th, tr, proposes)
    actifs = cands[:MAX_BUTS_SUPPOSES]  # mêmes buts cherchés qu'en référence (CCM-210-B : à 8, p050 et p081 perdus)
    if not actifs:
        return None
    vus_m = {}

    def monde(e):
        """Monde perçu, complété des objets du DÉPART aujourd'hui entièrement recouverts (CCM-202-B : le joueur qui
        couvre la sortie la cache au moment même de la victoire ; recouvert = inconnu, pas disparu)."""
        k = sim.cle(e)
        if k not in vus_m:
            m = objets(cases(sim.image(e), tr.s, tr.ox, tr.oy), tr.fond, tr.exclues)
            if depart_m:
                occ = {c for o in m for c in cells(o)}
                caches = [o for o in depart_m if o not in m and cells(o) <= occ]
                m = tuple(caches) + tuple(m)  # dessous : les objets visibles restent au-dessus
            vus_m[k] = m
        return vus_m[k]
    # une seule largeur pour tous les buts : le 1er état qui rend vrai chaque but donne son plan (le plus court)
    e0 = sim.etat()
    depart_m = ()
    depart_m = monde(e0)
    file, vus, plans, n = deque([(e0, [])]), {sim.cle(e0)}, {}, 0
    while file and n < limite and time.process_time() - t0 < b and len(plans) < len(actifs):
        e, ch = file.popleft()
        for a in actions:
            n += 1
            e2, perdu = sim.pas(e, _lot_c(a, tr))
            if perdu or e2 is None:
                continue
            k = sim.cle(e2)
            if k in vus:
                continue
            vus.add(k)
            m = monde(e2)
            for j, g in enumerate(actifs):
                if j not in plans and Theorie._vrai(g, m):
                    plans[j] = [*ch, a]
            file.append((e2, [*ch, a]))
    if not plans:
        return None
    infos = {"exact_noeuds": n, "exact_buts": len(actifs), "exact_plans": len(plans)}
    ordre = sorted(plans)
    if os.environ.get("CHRYS_TEST_BUTS") != "1" or len(ordre) == 1:
        j = ordre[0]
        return actifs[j], plans[j], infos
    # buts jugés sur chaque plan : les 8 premiers candidats, plus ceux qui ont un plan (comme `_but_teste`)
    juges = [i for i in range(len(actifs)) if i < TEST_ACTIFS or i in plans]
    w = [1.0 / (r + 1) if r in juges else 0.0 for r in range(len(actifs))]
    tot = sum(w)
    meilleur = None
    for j in ordre[:TEST_PLANS]:
        iss, e = [0] * len(actifs), e0
        for t, a in enumerate(plans[j], 1):
            e, _ = sim.pas(e, _lot_c(a, tr))
            m = monde(e)
            for i, g in enumerate(actifs):
                if not iss[i] and Theorie._vrai(g, m):
                    iss[i] = t
        par = {}
        for i, o in enumerate(iss):
            par[o] = par.get(o, 0.0) + w[i] / tot
        d = 1.0 - sum(v * v for v in par.values())
        v = sum(w[i] / tot for i, o in enumerate(iss) if o)
        u = (d + TEST_LAMBDA * v) / (1 + len(plans[j]))
        if meilleur is None or u > meilleur[0]:
            meilleur = (u, j, d, v)
    u, j, d, v = meilleur
    ref = ordre[0]  # mêmes garde-fous que `_but_teste` (CCM-149-C) : référence courte, test peu départageant, même 1er coup
    if len(plans[ref]) <= TEST_HORIZON or d < TEST_D_MIN or plans[j][:1] == plans[ref][:1]:
        j = ref
    infos["test_buts"] = {"U": round(u, 3), "D": round(d, 3), "V": round(v, 3), "info": int(j != ref)}
    return actifs[j], plans[j], infos


def _but_suppose(th, tr, actions, limite, t0, b, proposes=(), depart=None):
    """(théorie visant le but, plan, mondes) pour le 1er but candidat planifiable, ou None. Candidats : buts_candidats
    faux sur chaque état vu du niveau (sinon le niveau serait déjà fini), alternés par forme (ORDRE_BUTS), au plus 16 ;
    les hypothèses du proposeur (`proposes`, CCM-098-C) passent devant."""
    from chrysalide.arc3.logique.plan import planifier
    from chrysalide.arc3.logique.theorie import monde_final
    cands = _candidats_buts(th, tr, proposes)
    if os.environ.get("CHRYS_TEST_BUTS") == "1":
        return _but_teste(th, tr, actions, limite, t0, b, cands, depart)
    # E (CW-354.3, CCM-052-E), sous CHRYS_RECULER_FACILES : un but jamais vrai sur n ≥ 5 états vus, qu'un plan d'UN coup
    # atteindrait, est presque sûrement un artefact du modèle ; il est remis en fin de file (essayé en dernier)
    reculer = os.environ.get("CHRYS_RECULER_FACILES", "0") == "1" and len(tr.etats) > 5
    file, recules, en_attente = list(cands[:MAX_BUTS_SUPPOSES]), set(), None
    while file:
        x = file.pop(0)
        if time.process_time() - t0 > b:
            break
        tb = th.pour_but(x)
        plan, mondes = planifier(tb, monde_final(tb, tr) if depart is None else depart, tr.taille, actions, limite=limite,
                                 deadline=min(t0 + b, time.process_time() + max(0.03, (t0 + b - time.process_time())
                                              * (0.5 if ORDRE_BUTS.get(x[0], 9) < 0 else 1 / max(1, len(file) + 1)))))
        if plan and reculer and len(plan) == 1 and x not in recules:
            recules.add(x)
            en_attente = en_attente or (tb, plan, mondes)
            file.append(x)
            continue
        if plan:
            return tb, plan, mondes
    return en_attente


TEST_ACTIFS, TEST_PLANS, TEST_INFO_MAX, TEST_LAMBDA, TEST_HORIZON, TEST_D_MIN = 8, 4, 6, 1.0, 3, 0.25  # bornes de CW-280 (à tester, pas établies)
_INFO = {}  # niveau (hachage de sa 1re image) → coups d'information pure déjà joués


def _issues_plan(th, depart, taille, plan, buts):
    """Pour chaque but : 1er pas du plan (1-indexé) où il est VRAI dans l'état prédit (victoire prédite à ce pas), ou 0."""
    from chrysalide.arc3.logique.theorie import Theorie
    out, m = [0] * len(buts), depart
    for t, a in enumerate(plan, 1):
        m, _ = th.pas(m, a, taille)
        for j, g in enumerate(buts):
            if not out[j] and Theorie._vrai(g, m):
                out[j] = t
    return out


def _but_teste(th, tr, actions, limite, t0, b, cands, depart=None):
    """C (CW-280, variante C ; CHRYS_TEST_BUTS=1) : TEST ACTIF des buts. Buts actifs = les ≤ 8 premiers candidats non
    réfutés (un but vrai sur un état vu sans victoire est déjà écarté). Un plan par but (≤ 4 plans) ; chaque plan est
    jugé sur TOUS les buts actifs : issue o_j = pas où le but j prédit la victoire (0 : jamais). Désaccord
    D = 1 − Σ W_o² (poids de travail 1/(rang+1)), victoire prédite V, U = (D + λ·V) / (1 + coups). Le plan au meilleur U
    est joué ; s'il n'est pas celui du 1er but (référence), c'est un coup d'information, au plus 6 par niveau."""
    import hashlib

    from chrysalide.arc3.logique.plan import planifier
    from chrysalide.arc3.logique.theorie import monde_final
    essais = cands[:MAX_BUTS_SUPPOSES]  # mêmes buts essayés et même partage du budget que `_but_suppose` (référence)
    if not essais:
        return None
    m0 = monde_final(th, tr) if depart is None else depart
    plans = []
    for i, x in enumerate(essais):
        if len(plans) >= TEST_PLANS or time.process_time() - t0 > b:
            break
        if plans and (len(plans[0][2]) <= TEST_HORIZON or time.process_time() - t0 > 0.5 * b):
            break  # CCM-214-B (ft09 N3) : référence courte = déjà jouée ; tests seulement sur la 1re moitié du budget,
            # sinon le tour dépasse son budget et le plan de référence est perdu (« budget dépassé »)
        tb = th.pour_but(x)
        plan, mondes = planifier(tb, m0, tr.taille, actions, limite=limite,
                                 deadline=min(t0 + b, time.process_time() + max(0.03, (t0 + b - time.process_time())
                                              * (0.5 if ORDRE_BUTS.get(x[0], 9) < 0 else 1 / max(1, len(essais) - i)))))
        if plan:
            plans.append((i, tb, plan, mondes))
    if not plans:
        return None
    # buts ACTIFS (jugés sur chaque plan) : les 8 premiers candidats, plus ceux qui ont un plan
    actifs = [x for i, x in enumerate(essais) if i < TEST_ACTIFS or any(p[0] == i for p in plans)]
    plans = [(actifs.index(essais[i]), tb, plan, mondes) for i, tb, plan, mondes in plans]
    w = [1.0 / (r + 1) for r in range(len(actifs))]
    tot = sum(w)
    cle = hashlib.blake2b(np.asarray(tr.cases[0]).tobytes(), digest_size=8).hexdigest()
    info = _INFO.get(cle, 0)
    meilleur = None
    for i, tb, plan, mondes in plans:
        iss = _issues_plan(th, m0, tr.taille, plan, actifs)
        par = {}
        for j, o in enumerate(iss):
            par[o] = par.get(o, 0.0) + w[j] / tot
        d = 1.0 - sum(v * v for v in par.values())
        v = sum(w[j] / tot for j, o in enumerate(iss) if o)
        u = (d + TEST_LAMBDA * v) / (1 + len(plan))
        if meilleur is None or u > meilleur[0]:
            meilleur = (u, i, tb, plan, mondes, d, v)
    u, i, tb, plan, mondes, d, v = meilleur
    # pas de coup d'information quand : le plan de référence est court (c'est déjà un test ET une résolution), le meilleur
    # test départage peu (D < 0,25 : un coup qui n'informe presque pas), ou il commence par le même coup (CW-280)
    if len(plans[0][2]) <= TEST_HORIZON or d < TEST_D_MIN or plan[:1] == plans[0][2][:1]:
        _, tb, plan, mondes = plans[0]
        i = plans[0][0]
    if i != plans[0][0]:
        if info >= TEST_INFO_MAX:  # budget d'information épuisé : plan de référence (1er but planifiable)
            _, tb, plan, mondes = plans[0]
        else:
            _INFO[cle] = info + 1
            plan = plan[:1]  # coup d'information : on joue le 1er coup seulement, puis on réobserve
    tb.test_buts = {"buts_actifs": len(actifs), "plans": len(plans), "U": round(u, 3), "D": round(d, 3), "V": round(v, 3),
                    "info": _INFO.get(cle, 0)}
    return tb, plan, mondes


def _exporter(th, taille):
    """export_langage.exporter + règles du langage ajoutées par un proposeur (B, CCM-105/157-B) : CHRYS_REGLES_EXTRA = fichier
    JSON, liste de règles {nom, quand, alors, phase}. Les portes de la branche jugent le programme complété."""
    from chrysalide.arc3.logique.export_langage import exporter
    prog, non = exporter(th, taille)
    if os.environ.get("CHRYS_REGLES_EXTRA"):
        import json
        from pathlib import Path
        try:
            prog["regles"] = prog["regles"] + list(json.loads(Path(os.environ["CHRYS_REGLES_EXTRA"]).read_text()))
        except (OSError, ValueError, TypeError):
            pass
    return prog, non


def _mdl(th, tr):
    """C (CW-257 ; CHRYS_MDL=1) : longueur de description de la théorie retenue et du modèle nul « rien ne change ».
    `infos["mdl_comprime"]` peut remplacer le seuil sur le taux d'explication dans la porte partielle (branche, A)."""
    if os.environ.get("CHRYS_MDL") != "1":
        return {}
    from chrysalide.arc3.logique.mdl import comprime
    ok, total, nul = comprime(th, tr)
    return {"mdl": round(total, 1), "mdl_nul": round(nul, 1), "mdl_comprime": ok}


def _plan_partiel(moteur, c, tr, offertes, h, t0, b, k=3):
    """C (CW-235.1, modèle partiel autorisé à agir) : la théorie ne rejoue pas l'image entière, mais rejoue EXACTEMENT, pas
    à pas, le CONTRAT (positions des mobiles stables) sur tout l'historique → elle peut agir, sur un plan COURT : le
    plus long préfixe de ≤ k coups dont chaque prédiction est acceptée par la garde (relations démontrées seulement).
    Le reste du monde est déclaré inconnu, jamais masqué. Rend le plan ENTIER et son programme exporté (la porte 2 de la
    branche le déroule jusqu'au but simulé, A : CCM-222-A) ; seuls les `infos["garde_n"]` premiers coups sont à jouer
    (`infos["partiel"]`). → (lots, programme) ou None."""
    from chrysalide.arc3.logique.plan import planifier
    from chrysalide.arc3.logique.prediction import garder, rejeu_contrat
    from chrysalide.arc3.logique.theorie import rejeu
    okc, nc, premier, mob = rejeu_contrat(c, tr)
    # CHRYS_PARTIEL=1 : le contrat doit être exact sur tout l'historique ; =2 (CW-236, principe de Thomas) : aucune condition
    # globale, la théorie agit telle quelle et seule la garde, coup par coup et par relation, décide
    if os.environ.get("CHRYS_PARTIEL") != "2" and (not mob or okc < nc):
        moteur.infos["partiel_refus"] = "aucun mobile" if not mob else f"contrat {okc}/{nc} (1er écart t={premier})"
        return None
    moteur.infos["explique"] = {"image": rejeu(c, tr)[0], "contrat": okc, "transitions": nc}
    actions, r = offertes + (_clics_offerts(c, tr) if c.motif else []), None
    if c.but is not None:
        plan, mondes = planifier(c, c.avec_selection(tr.etats[-1], tr.actions), tr.taille, actions,
                                 limite=moteur.limite_plan, deadline=t0 + b)
        origine = "partiel"
    elif os.environ.get("CHRYS_BUT_SUPPOSE") == "1":
        r = _but_suppose(c, tr, actions, moteur.limite_plan, t0, b, _buts_proposes(h),
                         depart=c.avec_selection(tr.etats[-1], tr.actions))
        c, plan, mondes = r if r is not None else (c, None, 0)
        origine = "partiel_but_suppose"
    else:
        plan, mondes, origine = None, 0, "partiel"
    if not plan and os.environ.get("CHRYS_PLAN_LANGAGE_PARTIEL") == "1":  # B (CCM-165-B) : recherche dans le LANGAGE
        prog, _ = _exporter(c, tr.taille)                                    # (règles ajoutées comprises), plan court
        lots = _plan_langage(moteur, prog, h, offertes, max(0.5, t0 + b - time.process_time()), partiel=True,
                             clics=_clics_offerts(c, tr) if c.motif else _clics_objets(tr))
        moteur.infos["plan_langage_partiel"] = moteur.infos.get("plan_langage", [])[-2:] or "non lancé"
        if lots:
            moteur.tr = tr
            moteur.infos.update(theorie=c.texte(), **_mdl(c, tr), origine="plan_langage_partiel", partiel=True,
                                garde_n=min(3, len(lots)), plan_complet=len(lots))
            return lots, prog
    if not plan:
        if c.but is not None:
            moteur.infos["partiel_refus"] = f"but induit {c.but[0]} sans plan ({mondes} mondes)"
        elif os.environ.get("CHRYS_BUT_SUPPOSE") == "1":
            moteur.infos["partiel_refus"] = "aucun but supposé planifiable" + (" (aucun candidat)" if not _nb_candidats(c, tr) else "")
        else:
            moteur.infos["partiel_refus"] = "pas de but"
        return None
    garde, raison = garder(c, tr, plan, k)
    if not garde:
        moteur.infos["partiel_refus"] = f"garde : {raison}"
        return None
    prog, non = _exporter(c, tr.taille)
    moteur.tr = tr
    moteur.infos.update(mondes=mondes, theorie=c.texte(), **_mdl(c, tr), origine=origine, partiel=True, garde_n=len(garde),
                        garde=f"{len(garde)}/{len(plan)} coups gardés" + (f" ({raison})" if raison else ""),
                        contrat=sorted(mob), but_suppose=str(c.but), plan_complet=len(plan))
    moteur.infos["non_exporte"] = non
    return [_lot_c(a, tr) for a in plan], prog  # plan ENTIER (porte 2 de la branche) ; jouer garde_n coups


def _nb_candidats(th, tr):
    from chrysalide.arc3.logique.induction import buts_candidats
    from chrysalide.arc3.logique.theorie import Theorie
    couleurs = {o[0] for e in tr.etats for o in e}
    return sum(1 for x in buts_candidats(th, couleurs) if not any(Theorie._vrai(x, e) for e in tr.etats))


def _garde(moteur, th, tr, plan):
    """C (CW-224, CCM-090-C) : avec CHRYS_GARDE=k (k ≥ 1), `infos["garde_n"]` = longueur du plus long préfixe de ≤ k coups
    dont chaque prédiction enchaînée est acceptée par `prediction.predire` (relations démontrées seulement). Le plan est
    rendu ENTIER (la porte 2 doit pouvoir le dérouler jusqu'à la victoire simulée) ; c'est la branche qui ne joue que les
    `garde_n` premiers coups puis redemande. [] (refus) si le 1er coup est incertain. Éteint par défaut ; le chemin
    `plan_langage` n'est pas gardé (v1)."""
    k = int(os.environ.get("CHRYS_GARDE", "0") or 0)
    if k <= 0:
        return plan
    from chrysalide.arc3.logique.prediction import garder
    garde, raison = garder(th, tr, plan, k)
    moteur.infos["garde_n"] = len(garde)
    moteur.infos["garde"] = f"{len(garde)}/{len(plan)} coups gardés" + (f" ({raison})" if raison else "")
    return plan if garde else []


def _clics_offerts(th, tr):
    """N'offrir que des formes dont une bascule a été observée sous clic.
    Une même couleur dans la légende ne démontre pas qu'elle soit cliquable.
    """
    from chrysalide.arc3.logique.theorie import _boite, _contient
    supports = set()
    for t, action in enumerate(tr.actions):
        if not isinstance(action, tuple):
            continue
        apres = {(o[1], o[2], o[3]): o[0] for o in tr.etats[t+1]}
        for o in tr.etats[t]:
            c2 = apres.get((o[1], o[2], o[3]))
            if c2 is not None and c2 != o[0] and th.bascule.get(o[0]) == c2:
                supports.add(o[1])
    monde = tr.etats[-1]
    eligibles = [o for o in monde if o[0] in th.bascule and o[1] in supports]
    if th.zone is not None:
        eligibles = [o for o in eligibles if any(z[0] == th.zone and len(z[1]) > len(o[1])
                                               and _contient(_boite(z), _boite(o)) for z in monde)]
    return sorted({("clic", o[2] + min(o[1])[0], o[3] + min(o[1])[1]) for o in eligibles})


def _clics_objets(tr, n=60):
    """Clics candidats sans règle de clic apprise (jeu à clics, CCM-170-B) : une case par objet de l'état courant, si
    l'agent a déjà cliqué dans ce niveau ; au plus n."""
    if not any(isinstance(a, tuple) for a in tr.actions):
        return []
    return sorted({("clic", o[2] + min(o[1])[0], o[3] + min(o[1])[1]) for o in tr.etats[-1] if o[0] < 512})[:n]


_G_INSTALLE = []


def _backend_g():
    """CW-291/303 (G) : simulateur généré (0 écart, ×1,7) si CHRYS_BACKEND_TABLEAUX=1 ou 2 ; installé une fois. Éteint : rien."""
    if not _G_INSTALLE:
        from chrysalide.arc3 import sim_genere
        _G_INSTALLE.append(sim_genere.installer())


def _plan_langage(moteur, prog, h, offertes, budget, partiel=False, clics=()):
    """Plan cherché dans le langage (`plan_langage.planifier_langage`, recherche « but » puis « paliers ») depuis l'état courant
    obtenu par la porte 1 (scène et état caché rejoués) ; flèches et SPACE seulement. → lots de l'agent, ou None."""
    from chrysalide.arc3.logique.plan_langage import planifier_langage
    _backend_g()
    if partiel:  # CHRYS_PLAN_LANGAGE_PARTIEL (B, CCM-165-B) : scène PERÇUE à l'état courant, porte partielle de A
        r = porte_partielle(moteur, prog, h["grilles"], h["lots"])
        if r is None:
            return None
        interp, sc, taux, _ = r
        moteur.infos["taux_langage"] = round(taux, 3)
    else:
        ok = porte(moteur, prog, h["grilles"], h["lots"])
        if not ok:
            return None
        interp, sc = ok
    coups = [(NOMS[a], None, None) for a in offertes if NOMS.get(a) in ("UP", "DOWN", "LEFT", "RIGHT", "SPACE")]
    coups += [nom_action(_lot_c(c, moteur.tr)) for c in clics]  # clics (B, CCM-170-B : lp85 n'a que des clics)
    if not coups:
        moteur.infos.setdefault("plan_langage", []).append({"refus": "aucun coup"})
        return None
    for recherche in ("but", "paliers"):
        t1 = time.process_time()
        plan, inf = planifier_langage(prog, sc, coups, recherche=recherche, noeuds=20000, secondes=max(0.5, budget / 2),
                                      etat=getattr(interp, "etat", None))
        budget -= time.process_time() - t1
        moteur.infos.setdefault("plan_langage", []).append({"recherche": recherche, "plan": len(plan) if plan else None,
                                                            **{k: v for k, v in (inf or {}).items() if k in ("refus", "noeuds")}})
        if plan:
            moteur.infos["plan_langage_gagnant"] = recherche
            return [{"action": t[0]} if t[0] != "MOUSE" else {"action": "MOUSE", "row": t[1], "col": t[2]} for t in plan]
        if budget <= 0.5:
            break
    if os.environ.get("CHRYS_PORTEFEUILLE_G", "0") == "1" and budget > 0.5:
        # G (CW-429, CCM-054-G) : portefeuille macro_g puis largeur sur le reste du budget du tour (éteint par défaut)
        from chrysalide.arc3.logique.portefeuille_g import portefeuille
        plan, inf = portefeuille(prog, sc, getattr(interp, "etat", None), coups, budget)
        moteur.infos.setdefault("plan_langage", []).append({"recherche": "portefeuille_g", "plan": len(plan) if plan else None,
                                                            "gagnant": inf.get("gagnant")})
        if plan:
            moteur.infos["plan_langage_gagnant"] = "portefeuille_g"
            return [{"action": t[0]} if t[0] != "MOUSE" else {"action": "MOUSE", "row": t[1], "col": t[2]} for t in plan]
    return None


def _lot_c(a, tr):
    """Action de C → action de l'agent ; clic (case) → MOUSE au centre de la case, en pixels de l'image."""
    if isinstance(a, tuple):
        cx, cy = tr.camera[-1] if getattr(tr, "camera", None) else (0, 0)  # D (CHRYS_DEFILEMENT) : monde → écran
        return {"action": "MOUSE", "row": int(tr.oy + (a[2] - cy) * tr.s + tr.s // 2),
                "col": int(tr.ox + (a[1] - cx) * tr.s + tr.s // 2)}
    return {"action": NOMS[a]}


def _transfert():
    return os.environ.get("CHRYS_TRANSFERT", "0") == "1"


_ECHELLES = {}  # 1re image du niveau → échelle retenue (décidée une fois par niveau, dès 8 coups vus)


def _echelle_rejeu(grilles, acts, min_coups=8):
    """C (CW-254 ; CHRYS_ECHELLE_REJEU=1) : l'échelle déduite des blocs unis perd parfois les objets (anneau de r11l, cadre
    creux de lp85), parfois non (re86), et aucun critère d'image ne le prédit (CCM-125-C). On fait départager le REJEU :
    l'échelle 1 n'est retenue (et figée pour le niveau) que si sa théorie induite rejoue STRICTEMENT plus de transitions
    que celle de l'échelle déduite ; à égalité, l'échelle déduite est gardée (ar25 : égalité au début, 3 gagne ensuite)."""
    import hashlib

    from chrysalide.arc3.logique.faits import Trajectoire, echelle
    from chrysalide.arc3.logique.induction import induire
    from chrysalide.arc3.logique.theorie import rejeu
    g0 = np.asarray(grilles[0])
    cle = hashlib.blake2b(g0.tobytes(), digest_size=8).hexdigest()
    if cle in _ECHELLES:
        return _ECHELLES[cle]
    e = echelle(grilles)
    if len(acts) < min_coups:
        return e
    autres = [x for x in dict.fromkeys([echelle(grilles[:1]), (1, 0, 0)]) if x != e]  # 1re image du niveau (re86 :
    if not autres:                                                                     # 3 ; l'échantillon donne 4)
        return e
    scores = {}
    for ech in (e, *autres):
        tr = Trajectoire(grilles, acts, ech=ech)
        th, _ = induire([(tr, None, None)], limite_s=10)
        th.hors_jeu = tr.exclues
        scores[ech] = rejeu(th, tr)[0]
    meilleur = max(autres, key=lambda k: scores[k])
    if scores[meilleur] > scores[e]:  # STRICTEMENT mieux que l'échelle déduite : retenue (et figée) pour le niveau
        _ECHELLES[cle] = meilleur
        return meilleur
    return e  # égalité ou mieux à l'échelle déduite : on la garde, sans figer (ar25 : égalité au début, 3 gagne ensuite)


def _trajectoire_heritee(grilles, acts, prec):
    """Trajectoire du niveau courant. CHRYS_TRANSFERT=1 (D, CW-234 : ce qui PERSISTE d'un niveau à l'autre) : le
    masque d'interface (jauge, compteurs) appris aux niveaux réussis de même géométrie (échelle, origine) est ajouté au
    masque du niveau courant, trop court pour l'apprendre seul (T4 : la 1re erreur du niveau 2 est une case de jauge)."""
    from chrysalide.arc3.logique.faits import Trajectoire
    tr = Trajectoire(grilles, acts, ech=_echelle_rejeu(grilles, acts) if os.environ.get("CHRYS_ECHELLE_REJEU") == "1" else None)
    from chrysalide.arc3.logique.plan import poser_zone
    poser_zone(tr.etats)  # F (CHRYS_F_ZONE, CW-468) : zone observée du niveau courant ; éteint = rien
    if not _transfert() or not prec:
        return tr
    her = frozenset().union(*[p[0].exclues for p in prec if (p[0].s, p[0].ox, p[0].oy) == (tr.s, tr.ox, tr.oy)])
    return Trajectoire(grilles, acts, ech=(tr.s, tr.ox, tr.oy), exclues_heritees=her) if her - tr.exclues else tr


def _codes_c(lots):
    out = [_code_c(lot["actions"][0]) if len(lot["actions"]) == 1 else None for lot in lots]
    return None if any(a is None for a in out) else out


def _evenements_films(grilles, films, n, acts=()):
    """E (CW-441, CHRYS_FILMS_EVT) : pour chacun des n coups, `films.evenements(avant, film)` si le film du coup existe
    (CHRYS_FILMS=1 de D : un film par lot, aligné sur h["lots"]) ; None sinon. Films mal alignés → aucun événement."""
    from chrysalide.arc3 import films as F
    if len(films) != n:
        return [None] * n
    out = []
    for t in range(n):
        f = films[t]
        a = acts[t] if t < len(acts) else None
        clic = (a[1], a[2]) if isinstance(a, tuple) and a and a[0] == "clic" else None
        out.append(F.evenements(grilles[t], f, clic) if f else None)
    return out


def theorie_precedente(precedents, limite_s=60):
    """Théorie des niveaux réussis (comme `ancienne` de MoteurC) ; None si aucun niveau exploitable."""
    from chrysalide.arc3.logique.faits import Trajectoire
    from chrysalide.arc3.logique.induction import induire
    prec = []
    for p in precedents:
        pa, fin = _codes(p["lots"]), _codes([p["finale"]])
        if pa is not None and fin is not None:
            prec.append((Trajectoire(p["grilles"], pa), None, fin[0]))
    return induire(prec, limite_s=limite_s)[0] if prec else None


def genres_joues(precedents):
    """Genres d'action déjà joués aux niveaux réussis (E4 v2) : flèches, et (« clic », couleur du pixel cliqué)."""
    out = set()
    for p in precedents:
        for g, lot in zip(p["grilles"], [*p["lots"], p["finale"]], strict=False):
            for a in lot["actions"]:
                c = _code_c(a)
                if isinstance(c, int):
                    out.add(c)
                elif c is not None and len(lot["actions"]) == 1:
                    out.add(("clic", int(g[c[2]][c[1]])))
    return out


def _signature(th, m, a, buts, taille, fond):
    from chrysalide.arc3.logique.theorie import Theorie
    m2, _ = th.pas(m, a, taille)
    return th.rendu(m2, taille, fond).tobytes(), tuple(bool(Theorie._vrai(b, m2)) for b in buts), th.meurt(m2)


def _entropie(ths, m, a, buts, taille, fond):
    import math
    from collections import Counter
    c = Counter(_signature(th, m, a, buts, taille, fond) for th, _ in ths)
    n = sum(c.values())
    return -sum(v / n * math.log2(v / n) for v in c.values())


def _experience_contact(th, m, testees, sources):
    """Copie d'E4 (CW-081 a) : pousser l'objet contrôlé contre une couleur jamais vue bouger ; flèche sur une couleur sélectionnée."""
    from chrysalide.arc3.logique.theorie import cells
    controle = {c for c, _ in th.moves}
    bouge = set()
    for t, *_ in sources:
        for e0, e1 in zip(t.etats, t.etats[1:], strict=False):
            bouge |= {o[0] for o in set(e1) - set(e0)}
    occupe = {(x, y): o[0] for o in m for x, y in cells(o)}
    for o in m:
        if o[0] not in controle:
            continue
        for (c, a), (dx, dy) in th.moves.items():
            if c != o[0]:
                continue
            for x, y in cells(o):
                v = occupe.get((x + dx, y + dy))
                if v is not None and v not in controle and v not in bouge and v not in testees:
                    return a, v
    presentes = {o[0] for o in m}
    for c2 in th.bascule.values():
        if c2 in presentes and c2 not in controle:
            for a in (1, 2, 3, 4):
                if (c2, a) not in testees:
                    return a, (c2, a)
    return None


class Tutoriel:
    """Coups d'expérience du début d'un niveau k ≥ 2 (logique d'E4 `explorer`, politique par_niveau, tant que `tuto`) :
    1er coup au hasard ; puis, à chaque coup, théorie réinduite sur le niveau avec le prior `ancienne` ; action d'un genre
    jamais joué (ou flèche sans règle de mouvement jamais essayée dans cet état) ; sinon fin si TUTO_CALME coups d'essai
    prédits sans surprise ; sinon expérience de contact ; sinon coup le plus discriminant entre k théories (à égalité : genre
    le moins essayé, état neuf). Fin aussi au budget (tous coups du niveau comptés). `coup` → action de Franzen ou None."""

    def __init__(self, ancienne, inconnues, budget, jouees=(), fleches=True, clics=False, graine=0, limite_s=60):
        import random
        from collections import Counter
        self.anc, self.inconnues, self.budget, self.limite_s = ancienne, set(inconnues), budget, limite_s
        self.fleches, self.clics, self.rnd = fleches, clics, random.Random(graine)
        self.jouees, self.deja, self.testees, self.essais = set(jouees), set(), set(), Counter()
        self.calme, self.attendu1, self.journal, self.fin = 0, None, Counter(), None

    @classmethod
    def ouvrir(cls, precedents, g0, budget, limite_s=60, **kw):
        """→ (Tutoriel | None, classes inconnues) ; None si la théorie précédente connaît toutes les classes de g0."""
        from chrysalide.arc3.logique.faits import Trajectoire
        from chrysalide.arc3.logique.induction import classes_inconnues
        anc = theorie_precedente(precedents, limite_s)
        if anc is None:
            return None, set()
        inc = classes_inconnues(anc, Trajectoire([g0], []).etats[0])
        if not inc or budget <= 0:
            return None, inc
        return cls(anc, inc, budget, genres_joues(precedents), limite_s=limite_s, **kw), inc

    def _cands(self, tr):
        from chrysalide.arc3.logique.theorie import cells
        clics = sorted({("clic", x, y) for o in tr.etats[0] for x, y in cells(o)}) if self.clics else []
        return ([1, 2, 3, 4] if self.fleches else []) + clics or [("clic", 0, 0)]

    @staticmethod
    def _lot(tr, a):
        if isinstance(a, tuple):  # case → pixel du centre (en_pixels_cases d'E4) → MOUSE de Franzen
            return {"action": "MOUSE", "row": tr.oy + a[2] * tr.s + tr.s // 2, "col": tr.ox + a[1] * tr.s + tr.s // 2}
        return {"action": NOMS[a]}

    def coup(self, grilles, lots):
        try:
            return self._coup(grilles, lots)
        except Exception as e:  # noqa: BLE001 — clingo absent, perception impossible : le tutoriel s'arrête
            self.fin = f"erreur : {type(e).__name__}: {e}"[:200]
            return None

    def _coup(self, grilles, lots):
        from chrysalide.arc3.logique.faits import Trajectoire
        from chrysalide.arc3.logique.induction import buts_candidats, induire, induire_k
        from chrysalide.arc3.logique.theorie import Theorie, cells, egal
        acts = _codes_c(lots)
        if acts is None:
            self.fin = "lot multiple"
            return None
        if len(acts) >= self.budget:
            self.fin = "budget"
            return None
        if not acts:  # aucune observation du niveau : coup au hasard (E4 hasard_initial)
            tr0 = Trajectoire([grilles[-1]], [])
            self.journal["hasard_initial"] += 1
            return self._lot(tr0, self.rnd.choice(self._cands(tr0)))
        tn = Trajectoire(grilles, acts)
        sources = [(tn, None, None, None)]
        th0, _ = induire(sources, limite_s=self.limite_s, anciennes=self.anc)
        tr = Trajectoire([grilles[-1]], [], atomiques=tn.atomiques)
        m = tr.etats[0]
        cands = self._cands(tr)
        occ = {(x, y): o[0] for o in m for x, y in cells(o)}

        def genre(x):
            return ("clic", occ.get((x[1], x[2]))) if isinstance(x, tuple) else x
        self.jouees |= {x for x in acts if isinstance(x, int)}
        ctrl = {c for c, _ in th0.moves}
        neuves = [x for x in cands if genre(x) not in self.jouees]
        neuves += [x for x in cands if isinstance(x, int) and ctrl and all((c, x) not in th0.moves for c in ctrl)
                   and (m, x) not in self.deja and x not in neuves]
        if neuves:
            a = self.rnd.choice(neuves)
            self.jouees.add(genre(a))
            self.deja.add((m, a))
            self.journal["action_neuve"] += 1
            return self._lot(tr, a)
        if self.attendu1 is not None:
            surpris = self.attendu1.shape != tr.cases[0].shape or not egal(self.attendu1, tr.cases[0], tr.exclues)
            self.calme = 0 if surpris else self.calme + 1
            self.journal["tuto_surprises"] += surpris
            self.attendu1 = None
        if self.calme >= TUTO_CALME:
            self.fin = "calme"
            return None
        a_test = _experience_contact(th0, m, self.testees, sources)
        if a_test is not None:
            self.testees.add(a_test[1])
            self.journal["experience_contact"] += 1
            return self._lot(tr, a_test[0])
        vus = list(tn.etats)
        couleurs = {o[0] for e in vus for o in e}
        restants = [b for b in buts_candidats(th0, couleurs) if not any(Theorie._vrai(b, e) for e in vus)]
        ths = induire_k(sources, k=TUTO_K, limite_s=self.limite_s) or [(th0, None)]
        best = max((_entropie(ths, m, x, restants, tr.taille, tr.fond), -self.essais[genre(x)], (m, x) not in self.deja,
                    self.rnd.random(), x) for x in cands)
        a = best[4]
        self.essais[genre(a)] += 1
        self.deja.add((m, a))
        m1, _ = th0.pas(m, a, tr.taille)
        self.attendu1 = th0.rendu(m1, tr.taille, tr.fond)
        self.journal["tuto_coup"] += 1
        return self._lot(tr, a)


def _codes(lots):
    """Lots d'une action chacun, sans clic → codes de C (1..5, 7) ; sinon None."""
    out = []
    for lot in lots:
        if len(lot["actions"]) != 1:
            return None
        n = nom_action(lot["actions"][0])[0]
        if n not in CODES:
            return None
        out.append(CODES[n])
    return out
