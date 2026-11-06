# SPDX-License-Identifier: MIT-0
"""Branchement de l'architecture Chrysalide (archi.py) dans le solveur de Franzen (framework/solver.py).

Deux points seulement, posés par scripts/arc3/patcher_franzen.py :
  1. à la construction du solveur : `self._chrys = branche.creer(self)` -> None si aucun interrupteur CHRYS_* n'est
     allumé ; le solveur est alors strictement celui de Franzen (contrôle F-C2) ;
  2. dans la boucle, juste avant `self.analyzer.analyze(...)` : `if self._chrys is not None and self._chrys.tour(): continue`
     -> si le routeur a un réflexe, le coup est joué par `step_env` SANS appel au modèle.
`step_env` est enveloppé pour que TOUT coup (modèle ou réflexe) passe par le moniteur ; un niveau réussi enregistre son
journal comme réflexe. Unité d'action = un lot `{"actions": [...]}` tel que le modèle l'a envoyé.
CHRYS_GRAPHE=1 (voie 2 b) : chaque lot devient une arête du graphe des transitions (graphe.py) ; après un game over, le
niveau repart et la branche rejoue SANS modèle le plus court chemin connu vers l'état d'avant le lot fatal, en vérifiant
chaque pas (état observé ≠ état prévu → abandon, le modèle reprend). Priorité au retour sur les réflexes.
CHRYS_MOTEUR=1 (P2 de CW-126, moteur.py) : à chaque tour, le moteur formel reçoit les images et lots du niveau courant
(+ niveaux réussis) ; s'il rend (plan, programme) ET que le programme rejoue exactement chaque image observée du niveau
(porte, interpréteur de A) ET que le plan déroulé dans ce programme finit en victoire simulée (porte 2, porte_but,
CW-138 ; sinon refus, déclencheur sans_but ; plan tronqué au coup gagnant), le plan est joué sans modèle, image prédite contre image observée après chaque coup ; à la
1re divergence le plan est abandonné et le modèle reprend. Ordre : retour (GRAPHE) > plan du moteur > réflexes.
CHRYS_TUTO=1 (sans effet si CHRYS_MOTEUR éteint) : au début d'un niveau k ≥ 2, si la théorie des niveaux réussis ignore
des classes de la 1re image (classes_inconnues de C), mini-tutoriel d'E4 (moteur.Tutoriel) : coups d'expérience joués sans
modèle ni porte, comptés à part (source « tuto ») ; ensuite porte + plan, sinon modèle. Une fois par niveau.
Déclencheurs (CW-133, CHRYS_MOTEUR seulement) : chaque fois que la main revient au modèle, la raison est nommée
(DECLENCHEURS, priorité dans cet ordre : contre_exemple, sans_but, classe_inconnue, debut_jeu, filet), comptée, posée sur
les lignes « modele » de la trace, et passée au rappel `rappels[raison]` (point d'extension : son texte éventuel est ajouté
à la consigne du tour par outils_repl.ligne_tour ; rappels par défaut muets = comportement inchangé). La théorie qui a
passé la porte est suivie coup par coup, quel que soit le joueur (`suivi`) : si elle cesse de prédire l'image → contre-
exemple. P10 (CW-134) : ses attributs d'état (moteur.attributs) vont en une ligne exacte à la consigne (_chrys_etat).
CHRYS_BOUCLE=1 (V1 de CW-162/163, sans effet si CHRYS_MOTEUR éteint) : au blocage (contre_exemple, sans_but, sans plan),
avant de rendre la main au modèle, jusqu'à CHRYS_BOUCLE_TOURS (3) tours de diagnostic à étages (diagnostic.py) → action
de l'étage → portes ; budget par blocage CHRYS_BOUCLE_CPU_S (60) et CHRYS_BOUCLE_COUPS (10) coups d'expérience ; au-delà,
le modèle comme en V0. Éteint : comportement V0 au point près."""
import json
import os
import time
import types
from pathlib import Path

from chrysalide.arc3.archi import MemoireReflexes, Moniteur, Routeur, Verificateur, actif
from chrysalide.arc3.graphe import Graphe, etat

INTERRUPTEURS = ("MONITEUR", "REFLEXES", "ROUTEUR", "VERIF", "GRAPHE", "BUDGET", "MOTEUR", "PORTE_V4", "PORTE5")  # PORTE_V4 : porte_v4.py ; PORTE5 : porte_v5.py
DECLENCHEURS = ("debut_jeu", "contre_exemple", "classe_inconnue", "sans_but", "filet")


def rappel_neutre(branche, raison, nouveau):
    """Rappel par défaut d'un déclencheur : aucune consigne (le modèle joue le tour comme aujourd'hui). Un rappel rend un
    texte (ajouté à la consigne du tour) ou None ; `nouveau` = la raison change depuis le tour modèle précédent."""


def creer(solveur, dossier=None, moteur=None, rappels=None):
    if not any(actif(n) for n in INTERRUPTEURS):
        return None
    return Branche(solveur, dossier, moteur, rappels)


def _evenement(lot, payload, fin, mort, sans_effet):
    """D (CW-324 P0, charte : observations complètes) : UN événement par coup, jamais fusionné : « reset » (RESET
    volontaire, préfixes), « victoire » (fin de partie gagnée), « mort », « niveau » (niveau réussi, la partie continue),
    « coup_sans_effet », « coup »."""
    if any(str(a.get("action")).upper() == "RESET" for a in lot["actions"]):
        return "reset"
    if payload.get("run_complete") or payload.get("state") == "WIN":
        return "victoire"
    if mort:
        return "mort"
    if fin:
        return "niveau"
    return "coup_sans_effet" if sans_effet else "coup"


def _payload_auto(p):
    """Copie du résultat d'un coup joué sans Franzen, actions marquées « (auto) » (rendu par son résumé de séquence)."""
    q = dict(p)
    if isinstance(q.get("executed_actions"), list):
        q["executed_actions"] = [f"{a} (auto)" for a in q["executed_actions"]]
    if q.get("action_display"):
        q["action_display"] = f"{q['action_display']} (auto)"
    q.setdefault("executed", True)
    return q


def _compacter(film, plafond=64):
    """D (CHRYS_FILMS) : film d'un coup → liste de tableaux uint8 (h × w), images consécutives identiques retirées, au plus
    `plafond` images régulièrement espacées (la première et la dernière gardées) ; None s'il reste moins de 2 images."""
    if not film:
        return None
    import numpy as np
    out = []
    for f in film:
        a = np.asarray(f, dtype=np.uint8)
        if not out or not np.array_equal(a, out[-1]):
            out.append(a)
    if len(out) > plafond:
        out = [out[round(k * (len(out) - 1) / (plafond - 1))] for k in range(plafond)]
    return out if len(out) > 1 else None


class Branche:
    def __init__(self, solveur, dossier=None, moteur=None, rappels=None):
        self.s = solveur
        d = Path(dossier or os.environ.get("CHRYS_DOSSIER", "chrysalide_runs"))
        d.mkdir(parents=True, exist_ok=True)
        run = getattr(getattr(solveur, "game", None), "game_run", None)  # Franzen : self.game.game_run.game_id
        jeu = str(getattr(run, "game_id", None) or "jeu")
        self.jeu, self.trace = jeu, d / f"{jeu}_trace.jsonl"
        self.moniteur = Moniteur()
        self.memoire = MemoireReflexes(d / f"{jeu}_reflexes.json")
        self.routeur = Routeur(self.memoire, self.moniteur)
        self.verif = Verificateur(self.memoire, self.routeur)
        self.g_depart, self.journal_niveau, self.en_reflexe = self._grille(), [], False
        self.graphe = Graphe() if actif("GRAPHE") else None
        self.cible, self.attendu, self.en_route, self.n_route, self.n_surprises = None, None, False, 0, 0
        self.moteur, self.en_plan, self.en_tuto, self.mt = None, False, False, None  # CHRYS_MOTEUR éteint : aucune ligne « moteur » ne s'exécute (F-C2)
        self.bc_m, self.bc, self.en_boucle, self.dernier = None, None, False, {}  # CHRYS_BOUCLE éteint : aucune boucle
        if actif("MOTEUR"):  # import paresseux : éteint, moteur.py et ses dépendances ne sont même pas chargés
            from chrysalide.arc3.moteur import MoteurC
            if moteur is None and actif("MOTEUR_CLE"):  # chaîne ls20 de C en modules (CW-145, CCM-042-C) ; porte faible
                from chrysalide.arc3.logique.moteur_cle import MoteurCle
                moteur = MoteurCle()
            self.moteur = moteur if moteur is not None else MoteurC()
            if actif("MOTEUR_PROCESSUS"):  # calcul du moteur hors du processus du harnais (GIL), moteur_processus.py
                from chrysalide.arc3.moteur_processus import MoteurDistant
                self.moteur = MoteurDistant(self.moteur)
            self.budget_1er = float(os.environ.get("CHRYS_MOTEUR_BUDGET1_S", "120"))  # CW-154 : 1er appel d'un niveau
            self.niv_appele = -1
            self.hist, self.precedents, self.plan, self.vu = {"grilles": [self._grille()], "lots": [], "films": []}, [], None, 0
            self.m = {"appels": 0, "refus_porte": 0, "plans": 0, "tours": 0, "coups_plan": 0, "divergences": 0, "cpu_s": 0.0,
                      # CW-138 / Tycho : (a) rejeu exact (porte 1), (b) but compris (porte 2 : plan gagnant en simulation),
                      # plans joués jusqu'au bout ET niveau réellement gagné ; (c) coups par niveau, comparés hors agent
                      "porte1_ok": 0, "porte1_refus": 0, "porte2_ok": 0, "porte2_refus": 0, "plans_gagnants_reels": 0}
            if getattr(self.moteur, "porte_propre", False):  # CW-154 (1) : portes FAIBLES du moteur, comptées à part
                self.m.update({"porte1_c_ok": 0, "porte1_c_refus": 0, "porte2_c_ok": 0, "porte2_c_refus": 0,
                               "coups_porte_faible": 0, "niveaux_porte_faible": 0})
            self.par_niveau, self.niv_coups, self.niv_plan = [], 0, 0  # coups (tous joueurs) et coups de plan du niveau
            # déclencheurs (CW-133) : théorie vérifiée suivie, contre-exemple vu dans le niveau, dernières infos du moteur,
            # classes inconnues du niveau, raison du dernier tour modèle, comptes ; coups = actions jouées (tous joueurs)
            self.suivi, self.contre, self.infos_m, self.inconnues, self.inc_vu, self.raison = None, False, {}, set(), 0, None
            self.declencheurs, self.n_coups = dict.fromkeys(DECLENCHEURS, 0), 0
            self.rappels = {r: rappel_neutre for r in DECLENCHEURS} | dict(rappels or {})
            if actif("TUTO"):  # CHRYS_TUTO : niveau déjà examiné (nombre de niveaux réussis), tutoriel en cours, compteurs
                self.tuto, self.tuto_vu = None, 0
                self.mt = {"tuto_niveaux": 0, "tuto_coups": 0, "tuto_classes": 0}
            if actif("BOUCLE"):  # V1 (CW-162/163) : diagnostic à étages puis boucle avant de rendre la main au modèle
                from chrysalide.arc3 import diagnostic
                self.dg = diagnostic
                self.bc_lim = {"tours": int(os.environ.get("CHRYS_BOUCLE_TOURS", "3")),
                               "cpu_s": float(os.environ.get("CHRYS_BOUCLE_CPU_S", "60")),
                               "coups": int(os.environ.get("CHRYS_BOUCLE_COUPS", "10"))}
                self.bc_m = {"blocages": 0, "boucles_tentees": 0, "boucles_reussies": 0, "boucle_cpu_s": 0.0,
                             "boucle_coups": 0, "diagnostics": {"par_etage": {}, "par_test": {}}}
                self.bc_vus, self.bc_echecs = set(), set()  # états bloqués déjà vus ; (niveau, raison) déjà échoués
        self._step_original = solveur.step_env
        self.evenements, self.n_vie, self.hist_films_dernier = [], 0, None  # D (CW-324 P0) : journal des événements
        self.payloads_auto = []  # D (CHRYS_HISTORIQUE_FIDELE) : résultats des coups joués sans Franzen depuis son tour
        self.par_action = None
        if self.moteur is not None and hasattr(solveur, "_execute_action"):  # CW-166 : les FILMS, coup par coup
            self.par_action = []
            ex_orig = solveur._execute_action

            def _ex(_s, *a, **k):
                p = ex_orig(*a, **k)
                rec = getattr(solveur, "animation_record", None)  # ARC3_ANIMATION : images intermédiaires de l'action
                film = rec.get("chain") if isinstance(rec, dict) else None
                self.par_action.append((self._grille(), [list(map(list, f)) for f in film] if film else None))
                return p
            solveur._execute_action = types.MethodType(_ex, solveur)
        # enveloppe : le modèle passe aussi par ici. Liée au SOLVEUR (MethodType), car l'agent de Franzen retrouve le
        # solveur par `step_env.__self__` pour y poser son garde-fou d'actions sans effet.
        solveur.step_env = types.MethodType(lambda _s, arguments: self.step_env(arguments), solveur)

    def _grille(self):
        return [list(r) for r in self.s.current_frame().grid]

    def step_env(self, arguments):
        if "actions" not in arguments and "action" not in arguments:
            return self._step_original(arguments)  # requêtes d'animation : rien à observer
        g0, niv0 = self._grille(), self.moniteur.niveau
        payload = self._step_original(arguments)
        if not isinstance(payload, dict) or not payload.get("executed", True):
            return payload
        lot = {"actions": arguments.get("actions") or [{k: arguments.get(k) for k in ("action", "row", "col")}]}
        fin, mort = bool(payload.get("level_completed")), bool(payload.get("game_over"))
        e = self.moniteur.observer(g0, lot, self._grille(), level_completed=fin, game_over=mort)
        conforme = self.verif.verifier(e) if self.en_reflexe else True
        if self.graphe is not None:
            s0, s1 = etat(g0, niv0), etat(self._grille(), self.moniteur.niveau)
            self.graphe.noter(s0, json.dumps(lot, sort_keys=True), s1, mort=mort)
            if self.en_route and s1 != self.attendu:  # vérification pas à pas du chemin rejoué
                conforme, self.cible, self.n_surprises = False, None, self.n_surprises + 1
            if mort:
                self.cible = s0
            elif fin:
                self.cible = None
        if self.moteur is not None:
            conforme = self._suivre_moteur(lot, fin, mort) and conforme
        source = ("route" if self.en_route else "reflexe" if self.en_reflexe else "moteur" if self.en_plan
                  else "tuto" if self.en_tuto else "boucle" if self.en_boucle else "modele")
        if self.bc is not None and source in ("tuto", "boucle"):  # coups d'expérience de la boucle (budget)
            self.bc["coups"] += len(lot["actions"])
            self.bc_m["boucle_coups"] += len(lot["actions"])
        ev = _evenement(lot, payload, fin, mort, e["sans_effet"])
        ligne = {"t": time.time(), "source": source, "lot": lot,
                 "sans_effet": e["sans_effet"], "fin_niveau": fin, "game_over": mort, "conforme": conforme,
                 "evenement": ev, "niveau": niv0, "vie": self.n_vie}
        if self.hist_films_dernier is not None:
            ligne["images"] = len(self.hist_films_dernier)
        self.evenements.append({k: ligne[k] for k in ("evenement", "niveau", "vie")} | {"source": source})
        if "1" in (os.environ.get("CHRYS_HISTORIQUE_FIDELE"), os.environ.get("CHRYS_APRES_VICTOIRE")):
            # D (charte : historique fidèle ; CW-332 : implicite sous « après victoire ») : coups joués pour Franzen
            if source == "modele":
                self.payloads_auto = []  # Franzen a joué : son propre résumé fait foi
            elif isinstance(payload, dict):
                self.payloads_auto.append(_payload_auto(payload))
        if ev in ("mort", "reset"):
            self.n_vie += 1
        elif ev in ("niveau", "victoire"):
            self.n_vie = 0
        if self.moteur is not None and source == "modele":
            ligne["declencheur"] = self.raison  # CW-133 : pourquoi le modèle a la main
        self._noter(ligne)
        self.journal_niveau.append(e)
        if fin:
            if actif("REFLEXES"):
                self.memoire.enregistrer(self.g_depart, self.journal_niveau, provenance={"jeu": self.jeu,
                                         "niveau": self.moniteur.niveau, "t": time.time()})
            self.g_depart, self.journal_niveau = self._grille(), []
        elif mort:
            self.g_depart, self.journal_niveau = self._grille(), []  # le niveau repart de zéro
        return payload

    def budget(self):
        """CHRYS_BUDGET (CW-080.5) : coups humains de référence h du niveau courant et coups déjà joués a, lus dans le
        `game_run` du framework ; None si le moteur les cache (`base_actions_per_level` absent)."""
        run = getattr(getattr(self.s, "game", None), "game_run", None)
        base = getattr(run, "base_actions_per_level", None)
        if not base:
            return None
        k = int(getattr(run, "levels_completed", 0) or 0)
        faits = list(getattr(run, "actions_per_level", None) or [])
        if k >= len(base):
            return None
        return {"niveau": k + 1, "h": int(base[k]), "a": int(faits[k]) if k < len(faits) else 0}

    def _styles_moteur(self):
        """D (CW-285, CHRYS_STYLES=1) : le sélecteur de styles règle le moteur pour ce tour ; False = style explorateur."""
        from chrysalide.arc3 import styles
        if not styles.actif():
            return True
        if getattr(self, "styles", None) is None:
            self.styles = styles.Selecteur()
        return self.styles.moteur_actif(len(self.precedents), self._grille(), self.m["divergences"],
                                        en_plan=self.plan is not None)

    def tour(self):
        """True si un coup a été joué sans le modèle (la boucle du solveur passe alors au tour suivant)."""
        if actif("BUDGET"):
            analyseur = getattr(self.s, "analyzer", None)
            if analyseur is not None:
                analyseur._chrys_budget = self.budget()
        if self.graphe is not None and self.cible is not None:
            s = etat(self._grille(), self.moniteur.niveau)
            chemin = None if s == self.cible else self.graphe.replay_to(s, self.cible)
            if not chemin:
                self.cible = None  # arrivé (ou plus de chemin connu) : le modèle reprend la main
            else:
                self.attendu, self.en_route = self.graphe.prevision(s, chemin[0]), True
                try:
                    self.step_env(json.loads(chemin[0]))
                finally:
                    self.en_route = False
                self.n_route += 1
                return True
        if self.moteur is not None and self._styles_moteur() and self._tour_moteur():
            return True
        decision, lot = self.routeur.decider(self._grille())
        if decision != "reflexe":
            if self.moteur is not None:
                if self.bc_m is not None and self._boucle():
                    return True
                self._au_modele()
            return False
        self.en_reflexe = True
        try:
            self.step_env(lot)
        finally:
            self.en_reflexe = False
        return True

    # ------------------------------------------------------------ CHRYS_MOTEUR
    def _suivre_moteur(self, lot, fin, mort):
        """Après chaque coup exécuté : historique du niveau tenu à jour ; pendant un plan, image prédite contre image observée.
        → False si le coup du plan a divergé (plan abandonné)."""
        import numpy as np

        from chrysalide.arc3.moteur import nom_action
        conforme = True
        pa, self.par_action = (self.par_action, []) if self.par_action is not None else (None, None)
        film1 = None  # D (CHRYS_FILMS, CW-306) : film d'un coup SIMPLE (Franzen : animation_record ; banc : solveur.film)
        if os.environ.get("CHRYS_FILMS") == "1" and len(lot["actions"]) == 1:
            film1 = _compacter(pa[0][1] if pa and len(pa) == 1 else getattr(self.s, "film", None))
        self.hist_films_dernier = film1
        if pa is not None and (len(lot["actions"]) < 2 or len(pa) != len(lot["actions"])):
            pa = None  # lot d'une action, ou exécution partielle ambiguë : on garde la transition entière
        if self.bc is not None and self.en_plan:  # un plan a passé les portes pendant la boucle : le moteur reprend
            self._fermer_boucle(True, "plan")
        self.n_coups += len(lot["actions"])
        self.niv_coups += len(lot["actions"])
        self.niv_plan += len(lot["actions"]) if self.en_plan else 0
        if not self.en_plan:
            self.attendre_modele = False  # le modèle (ou un autre joueur) a joué : le moteur peut reprendre
            self.plan = None  # un autre (modèle, retour, réflexe) a joué : le plan n'est plus à jour
        if self.suivi is not None:  # la théorie vérifiée prédit chaque coup, quel que soit le joueur (CW-133)
            prog, sc = self.suivi["prog"], self.suivi["scene"]
            observe = "niveau" if fin else "defaite" if mort else None
            try:
                for a in lot["actions"]:
                    prog.step(sc, nom_action(a))
                prevu = sc.issue
                cases = None
                if fin:
                    juste = prevu in ("niveau", "victoire")
                else:
                    rd, vu = np.asarray(self.moteur.rendu(sc)), np.asarray(self.moteur.vue(self._grille()))
                    juste = prevu is None and not mort and np.array_equal(rd, vu)
                    if not juste and rd.shape == vu.shape:  # CCM-085-C : cases fausses (ligne, colonne, prédit, observé)
                        cases = [[int(y), int(x), int(rd[y, x]), int(vu[y, x])] for y, x in zip(*np.nonzero(rd != vu))][:30]
            except Exception:  # noqa: BLE001 — prédiction impossible = divergence (le modèle reprend)
                prevu, juste, cases = "erreur", False, None
            if not juste:
                self.suivi, self.contre = None, True  # déclencheur contre_exemple
                if self.en_plan:
                    conforme = False
                    self.m["divergences"] += 1
                    self._noter({"t": time.time(), "source": "moteur", "divergence": True, "lot": lot,
                                 "pas": self.plan["pas"], "longueur": len(self.plan["actions"]), "prevu": prevu,
                                 "observe": observe, "origine": self.plan.get("origine"), "cases": cases})
                    self.plan = None
                else:
                    self._noter({"t": time.time(), "source": "moteur", "ne_rejoue_plus": True, "lot": lot,
                                 "prevu": prevu, "observe": observe})
        if fin:
            gagnant = bool(self.en_plan and self.plan is not None and self.plan["pas"] >= len(self.plan["actions"]))
            self.m["plans_gagnants_reels"] += gagnant
            faible = bool(self.en_plan and self.plan is not None and self.plan.get("faible"))
            if faible:  # CW-154 (3) : « niveau gagné sous porte faible », dit en clair
                self.m["niveaux_porte_faible"] = self.m.get("niveaux_porte_faible", 0) + 1  # clé absente si le moteur n'a pas `porte_propre` (CCM-194-B)
            self.par_niveau.append({"niveau": len(self.precedents) + 1, "coups": self.niv_coups,
                                    "coups_plan": self.niv_plan, "plan_gagnant": gagnant,
                                    "cpu_moteur_s": round(self.m["cpu_s"] - getattr(self, "niv_cpu0", 0.0), 3),  # CW-174
                                    **({"mode": "boucle" if getattr(self, "niv_boucle", False) else "rapide"}
                                       if self.bc is not None or getattr(self, "bc_m", None) is not None else {}),
                                    **({"porte_faible": faible} if "niveaux_porte_faible" in self.m else {})})
            if pa:  # CW-166 : transitions intermédiaires du lot gagnant, puis la finale d'une seule action
                for act, (g, film) in zip(lot["actions"][:-1], pa[:-1], strict=True):
                    self.hist["grilles"].append(g)
                    self.hist["lots"].append({"actions": [act]})
                    self.hist.setdefault("films", []).append(film)
                self.precedents.append({**self.hist, "finale": {"actions": [lot["actions"][-1]]}})
            else:
                self.precedents.append({**self.hist, "finale": lot})
            self.inconnues = set()
        if mort and not fin and os.environ.get("CHRYS_VIES") == "1" and self.hist["lots"]:
            # D (ar25 N2) : les vies perdues du niveau restent des exemples pour l'induction (sans le coup mortel) ;
            # les 5 dernières, oubliées au niveau suivant
            v = {"grilles": self.hist["grilles"], "lots": self.hist["lots"]}
            self.vies = ([*getattr(self, "vies", []), v])[-5:]
        elif fin:
            self.vies = []
        if fin or mort:
            if self.bc is not None:
                self._fermer_boucle(False, "niveau fini" if fin else "game over")
            self.niv_coups, self.niv_plan, self.niv_boucle, self.niv_cpu0 = 0, 0, False, self.m["cpu_s"]
            self.hist, self.plan, self.vu = {"grilles": [self._grille()], "lots": [], "films": []}, None, 0
            self.suivi, self.contre, self.infos_m = None, False, {}
            if self.mt is not None and self.tuto is not None:  # niveau fini ou perdu : le tutoriel s'arrête
                self._fin_tuto("niveau fini" if fin else "game over")
        elif pa:  # CW-166 : un lot de n actions = n transitions d'une action, chacune avec son film
            for act, (g, film) in zip(lot["actions"], pa, strict=True):
                self.hist["grilles"].append(g)
                self.hist["lots"].append({"actions": [act]})
                self.hist.setdefault("films", []).append(film)
        else:
            self.hist["grilles"].append(self._grille())
            self.hist["lots"].append(lot)
            if self.par_action is not None or os.environ.get("CHRYS_FILMS") == "1":
                self.hist.setdefault("films", []).append(film1)
        return conforme

    def _tour_moteur(self):
        """True si un coup du plan du moteur a été joué (sans modèle). Le moteur n'est appelé que si le niveau a au moins
        une transition observée, nouvelle depuis le dernier appel (la porte ne juge jamais sur un historique vide)."""
        if self.mt is not None and self._tour_tuto():
            return True
        if self.mt is None and self.precedents and not self.hist["lots"] and self.inc_vu != len(self.precedents):
            self.inc_vu = len(self.precedents)  # sans tutoriel : classes inconnues du niveau, une fois (CW-133)
            t0 = time.process_time()
            self.inconnues = set(self.moteur.classes_inconnues(list(self.precedents), self._grille()) or ())
            self.m["cpu_s"] += time.process_time() - t0 + getattr(self.moteur, "cpu_hors_processus_s", 0.0)
        if getattr(self, "attendre_modele", False):
            return False  # un coup du moteur est resté sans effet : le modèle joue d'abord
        cap = float(os.environ.get("CHRYS_MOTEUR_CPU_JEU_S", "0") or 0)  # E2E4 : 22 min de CPU moteur sur 60 (ls20)
        if cap > 0 and self.m["cpu_s"] >= cap:
            if not self.m.get("plafond_cpu_atteint"):
                self.m["plafond_cpu_atteint"] = 1
                self._noter({"t": time.time(), "source": "moteur", "plafond_cpu_jeu": cap, "cpu_s": self.m["cpu_s"]})
            return False  # plafond CPU du jeu atteint : Franzen seul jusqu'à la fin de la partie
        # D (CW-424) : sous CHRYS_RELEVE, UN appel au début du niveau qui suit des niveaux finis (aucun coup du niveau vu) :
        # la porte de C juge la vie gagnante des `precedents`, pas l'historique du niveau
        releve_debut = (os.environ.get("CHRYS_RELEVE") == "1" and self.precedents and not self.hist["lots"]
                        and getattr(self, "releve_appel", None) != len(self.precedents))
        if self.plan is None and (len(self.hist["lots"]) > self.vu or releve_debut):
            if releve_debut:
                self.releve_appel = len(self.precedents)
            self.vu = len(self.hist["lots"])
            self.m["appels"] += 1
            faible_possible = getattr(self.moteur, "porte_propre", False)
            if faible_possible and hasattr(self.moteur, "budget"):  # CW-154 : 120 s au 1er appel du niveau, puis le défaut
                self.moteur.budget = self.budget_1er if self.niv_appele != len(self.precedents) else None
                self.niv_appele = len(self.precedents)
            r = self.moteur.proposer({"grilles": list(self.hist["grilles"]), "lots": list(self.hist["lots"]),
                                      "films": list(self.hist.get("films", [])), "precedents": list(self.precedents),
                                      "vies": list(getattr(self, "vies", [])), "jeu": self.jeu})
            infos = dict(getattr(self.moteur, "infos", {}) or {})
            self.infos_m = infos
            self.m["cpu_s"] += float(infos.get("cpu_s", 0.0))
            if faible_possible and r is not None and r[1] is None:  # programme non exportable : portes propres du moteur
                return self._plan_faible(r, infos)
            self._examiner(r, infos)
        return self._jouer_plan()

    def _examiner(self, r, infos, extra=None):
        """Portes 1 et 2 sur une proposition du moteur (r = (plan, programme) ou None) ; pose self.plan si elles passent."""
        from chrysalide.arc3.moteur import porte, porte_but
        self.infos_m = infos
        ok = r is not None and porte(self.moteur, r[1], self.hist["grilles"], self.hist["lots"])
        if r is not None and not ok and r[0] and r[1] is not None and os.environ.get("CHRYS_PARTIEL", "0") not in ("", "0"):
            return self._examiner_partiel(r, infos, extra)
        if r is not None and not ok:
            self.m["refus_porte"] += 1
            self.m["porte1_refus"] += 1
            self.contre = True  # déclencheur contre_exemple : la théorie proposée ne rejoue pas le niveau
        if ok:
            self.m["porte1_ok"] += 1
            self.suivi, self.contre = {"prog": ok[0], "scene": ok[1]}, False  # théorie vérifiée, suivie coup par coup
        p2, issue = None, None
        if ok and r[0]:  # porte 2 (CW-138) : le plan doit gagner dans la simulation, sinon le but n'est pas compris
            n, issue = porte_but(self.moteur, r[1], self.hist["grilles"], self.hist["lots"], r[0])
            p2 = n is not None
            self.m["porte2_ok" if p2 else "porte2_refus"] += 1
            if p2:
                self.m["plans"] += 1
                self.plan = {"actions": list(r[0])[:n], "pas": 0,  # tronqué au coup gagnant simulé
                             "origine": infos.get("origine") or type(self.moteur).__name__}
                if infos.get("garde_n"):  # CW-224 (C, CHRYS_GARDE=k) : prise de main courte, seuls les coups prédits sûrs
                    self.plan["actions"] = self.plan["actions"][:max(1, int(infos["garde_n"]))]
                    self.plan["court"] = True
            else:
                self.infos_m["sans_but"] = True  # déclencheur sans_but : théorie qui rejoue, plan non gagnant
        # dernier jugement, lu par le diagnostic de CHRYS_BOUCLE (sans effet sinon)
        self.dernier = {"r_none": r is None, "porte1": None if r is None else bool(ok), "porte2": p2, "faible": False,
                        "plan": bool(r is not None and r[0])}
        self._noter({"t": time.time(), "source": "moteur", "appel": True, "transitions": self.vu,
                     "plan": len(r[0]) if ok else None, "porte": None if r is None else bool(ok),
                     "porte2": p2, "issue_simulee": issue, "plan_joue": len(self.plan["actions"]) if p2 else None,
                     "cpu_s": infos.get("cpu_s"), "refus": infos.get("refus"), **(extra or {}),
                     **{k: v for k, v in infos.items() if k.startswith("cle_") or k in ("porte1_c", "porte2_c", "refus_cle")}})

    def _examiner_partiel(self, r, infos, extra=None):
        """CW-236 : théorie PARTIELLE autorisée à agir. Porte 1 = taux d'explication (rejeu recalé) ≥ CHRYS_PARTIEL_SEUIL
        (0,5) ; porte 2 = le plan, déroulé depuis la scène perçue, finit sur le but ; plan court (≤ CHRYS_PARTIEL_COUPS = 3,
        ou garde_n de C), suivi coup par coup : tout écart rend la main à l'explorateur et devient un contre-exemple."""
        from chrysalide.arc3.moteur import porte_but_partielle, porte_partielle
        seuil = float(os.environ.get("CHRYS_PARTIEL_SEUIL", "0.5"))
        n, issue, taux = porte_but_partielle(self.moteur, r[1], self.hist["grilles"], self.hist["lots"], r[0])
        self.m["partiel_appels"] = self.m.get("partiel_appels", 0) + 1
        p1 = taux >= seuil
        if os.environ.get("CHRYS_MDL") == "1" and "mdl_comprime" in infos:
            # CW-271 / CCM-133-C : critère sans seuil, la théorie comprime mieux que « rien ne change » (MDL)
            p1 = bool(infos["mdl_comprime"])
        self.m["porte1_partielle_ok" if p1 else "porte1_partielle_refus"] = self.m.get(
            "porte1_partielle_ok" if p1 else "porte1_partielle_refus", 0) + 1
        p2 = p1 and n is not None
        if p2:
            pp = porte_partielle(self.moteur, r[1], self.hist["grilles"], self.hist["lots"])
            self.suivi, self.contre = {"prog": pp[0], "scene": pp[1]}, False  # suivi depuis la scène perçue
            k = int(infos.get("garde_n") or os.environ.get("CHRYS_PARTIEL_COUPS", "3"))
            self.m["plans"] += 1
            self.m["plans_partiels"] = self.m.get("plans_partiels", 0) + 1
            self.plan = {"actions": list(r[0])[:min(n, max(1, k))], "pas": 0, "court": True, "partiel": True,
                         "origine": infos.get("origine") or type(self.moteur).__name__}
        else:
            self.contre = not p1
            if p1:
                self.infos_m["sans_but"] = True
        self.dernier = {"r_none": False, "porte1": p1, "porte2": p2, "faible": False, "plan": True}
        self._noter({"t": time.time(), "source": "moteur", "appel": True, "partiel": True, "transitions": self.vu,
                     "taux_explication": round(taux, 3), "mdl": infos.get("mdl"), "mdl_nul": infos.get("mdl_nul"),
                     "plan": len(r[0]), "porte2": p2, "issue_simulee": issue,
                     "plan_joue": len(self.plan["actions"]) if p2 else None, "cpu_s": infos.get("cpu_s"),
                     "refus": infos.get("refus"), **(extra or {})})

    def _jouer_plan(self):
        if self.plan is None:
            return False
        if os.environ.get("CHRYS_INSPECT") == "1":
            # D (CW-357) : Franzen garde la main ; le plan prêt devient une OPTION versionnée qu'il lit par inspect_options()
            self.option = {"actions": list(self.plan["actions"][self.plan["pas"]:]), "but": not self.plan.get("court"),
                           "version": len(getattr(self.s, "history_entries", None) or [])}
            self._noter({"t": time.time(), "source": "moteur", "option": len(self.option["actions"])})
        if "1" in (os.environ.get("CHRYS_CALCULE_SANS_JOUER"), os.environ.get("CHRYS_INSPECT")):
            # D (charte, CCM-289-A : contrôle à charge égale) : le moteur a TOUT calculé (induction, portes, plan) comme en
            # H1, mais ne joue jamais ; le plan est noté puis jeté, Franzen joue, le moteur est redemandé après sa transition
            self.m["plans_non_joues"] = self.m.get("plans_non_joues", 0) + 1
            self._noter({"t": time.time(), "source": "moteur", "plan_non_joue": len(self.plan["actions"])})
            self.plan, self.vu = None, len(self.hist["lots"])
            return False
        a = self.plan["actions"][self.plan["pas"]]
        if os.environ.get("CHRYS_CONSENSUS") == "1" and self.plan["pas"] == 0:  # CW-251 : avant le 1er coup du plan
            from chrysalide.arc3.exploration import consensus
            t0 = time.process_time()
            avis, n, k = consensus(self.hist, a, k=int(os.environ.get("CHRYS_CONSENSUS_K", "4")))
            self.m["cpu_s"] += time.process_time() - t0
            self.m[f"consensus_{avis}"] = self.m.get(f"consensus_{avis}", 0) + 1
            self._noter({"t": time.time(), "source": "moteur", "consensus": avis, "predictions": n, "theories": k})
            if avis in ("apprendre", "reviser"):  # désaccord : on n'agit pas, l'explorateur (départage) joue d'abord
                self.plan, self.vu = None, len(self.hist["lots"])
                return False
        self.plan["pas"] += 1
        court = bool(self.plan.get("court"))
        self.en_plan = True
        try:
            self.step_env({"actions": [a]})
        finally:
            self.en_plan = False
        self.m["tours"] += 1
        self.m["coups_plan"] += 1
        fini = self.plan is not None and self.plan["pas"] >= len(self.plan["actions"])
        if fini:
            self.plan = None
        if self.plan is None and not (fini and court):
            self.vu = len(self.hist["lots"])  # plan fini ou divergence : le modèle joue avant tout nouvel appel
        # plan court (garde) fini sans divergence : le moteur est redemandé au tour suivant, sur l'historique réel
        return True

    def _plan_faible(self, r, infos):
        """CW-154 : plan sous porte FAIBLE (porte1_c : positions observées prédites ; porte2_c : plan qui finit sur le but
        dans le modèle du moteur). Seul le 1er coup est joué : le moteur est redemandé après chaque coup sur l'historique
        réel, si bien qu'un coup démenti par le vrai jeu fait tomber porte1_c et rend la main au LLM (condition 2)."""
        p1, p2 = bool(infos.get("porte1_c")), bool(infos.get("porte2_c"))
        # CW-177.1 (règle adoptée) : porte2_c ET aucune surprise SUR LE CHEMIN du plan (clé du moteur, si elle existe),
        # au lieu d'« aucun coup démenti dans tout le niveau » ; la revérification coup par coup reste la sûreté.
        chemin = infos.get("chemin_sans_surprise_c")
        p1 = p1 or bool(chemin)
        self.dernier = {"r_none": False, "porte1": p1, "porte2": p2 if p1 else None, "faible": True, "plan": bool(r[0])}
        _k = "porte1_c_ok" if p1 else "porte1_c_refus"
        self.m[_k] = self.m.get(_k, 0) + 1  # clé absente sans `porte_propre` (CCM-194-B)
        if p1:
            _k = "porte2_c_ok" if p2 else "porte2_c_refus"
            self.m[_k] = self.m.get(_k, 0) + 1
        self._noter({"t": time.time(), "source": "moteur", "appel": True, "transitions": self.vu, "porte_faible": True,
                     "porte1_c": p1, "porte2_c": p2, "chemin_sans_surprise_c": chemin,
                     "plan": len(r[0]) if r[0] else 0, "cpu_s": infos.get("cpu_s"),
                     "refus": infos.get("refus"), **{k: v for k, v in infos.items() if k.startswith("cle_") or k == "refus_cle"}})
        if not (p1 and p2 and r[0]):
            self.contre = not p1
            if p1:
                self.infos_m["sans_but"] = True
            return False
        self.m["plans"] += 1
        self.m["coups_porte_faible"] = self.m.get("coups_porte_faible", 0) + 1  # clé absente si le moteur n'a pas `porte_propre` (CCM-194-B)
        self.plan = {"actions": list(r[0])[:1], "pas": 0, "faible": True}
        a = self.plan["actions"][0]
        self.plan["pas"] = 1
        g_avant = self._grille()
        self.en_plan = True
        try:
            self.step_env({"actions": [a]})
        finally:
            self.en_plan = False
        self.m["tours"] += 1
        self.m["coups_plan"] += 1
        self.plan = None  # redemandé au tour suivant, sur la nouvelle transition réelle
        if self._grille() == g_avant:
            # E2E4 (18/10) : un plan qui pousse contre un mur ne « contredit » rien et passait la porte faible à chaque
            # appel (484 fois DOWN sans effet sur ls20). Un coup du moteur SANS EFFET est donc une divergence : la main
            # revient au modèle, et le moteur ne reprend qu'après un coup du modèle.
            self.m["divergences"] += 1
            self.m["faible_sans_effet"] = self.m.get("faible_sans_effet", 0) + 1
            self.attendre_modele, self.contre = True, True
            self._noter({"t": time.time(), "source": "moteur", "divergence": True, "sans_effet": True, "lot": {"actions": [a]}})
        return True

    def _tour_tuto(self):
        """CHRYS_TUTO : True si un coup d'expérience a été joué (sans modèle, hors porte). Ouverture une seule fois par
        niveau k ≥ 2, avant toute transition du niveau ; ensuite le moteur reprend avec ces observations."""
        from chrysalide.arc3.moteur import Tutoriel, budget_s, tuto_budget
        if self.precedents and not self.hist["lots"] and self.tuto_vu != len(self.precedents):
            self.tuto_vu = len(self.precedents)
            b = tuto_budget((self.budget() or {}).get("h"), self.precedents)
            fl, cl = self._actions_offertes()
            self.tuto, inc = Tutoriel.ouvrir(list(self.precedents), self._grille(), b, limite_s=budget_s(),
                                             fleches=fl, clics=cl)
            self.inconnues = set(inc)  # déclencheur classe_inconnue si le tutoriel n'a pas suffi (CW-133)
            if self.tuto is not None:
                self.mt["tuto_niveaux"] += 1
                self.mt["tuto_classes"] += len(inc)
                self._noter({"t": time.time(), "source": "tuto", "ouverture": True, "niveau": len(self.precedents) + 1,
                             "classes": sorted(int(c) for c in inc), "budget": b})
        if self.tuto is None:
            return False
        a = self.tuto.coup(list(self.hist["grilles"]), list(self.hist["lots"]))
        if a is None:
            self._fin_tuto(self.tuto.fin)
            return False
        self.en_tuto = True
        try:
            self.step_env({"actions": [a]})
        finally:
            self.en_tuto = False
        self.mt["tuto_coups"] += 1
        return True

    # ------------------------------------------------------------ CHRYS_BOUCLE (V1, CW-162/163)
    def _raison_blocage(self):
        """Blocage = contre_exemple, sans_but, ou moteur sans plan dans son budget ; None sinon (pas de boucle)."""
        r = self._declencheur()
        if r in ("contre_exemple", "sans_but"):
            return r
        refus = str(self.infos_m.get("refus") or "")
        return "sans_plan" if self.infos_m.get("sans_plan") or "pas de plan" in refus or "budget" in refus else None

    def _boucle(self):
        """True si la boucle a joué un coup sans modèle (expérience, tutoriel, ou 1er coup d'un plan qui passe les portes).
        Un état bloqué (niveau, raison, transitions) n'ouvre qu'une boucle ; un (niveau, raison) déjà échoué n'en ouvre
        plus. Au-delà de BOUCLE_TOURS tours, BOUCLE_CPU_S s ou BOUCLE_COUPS coups : main au modèle (V0)."""
        if self.bc is None:
            raison = self._raison_blocage()
            if raison is None:
                return False
            niv, cle = len(self.precedents), (len(self.precedents), raison, len(self.hist["lots"]))
            if cle in self.bc_vus:
                return False
            self.bc_vus.add(cle)
            self.bc_m["blocages"] += 1
            if (niv, raison) in self.bc_echecs:
                return False
            self.bc = {"niveau": niv, "raison": raison, "tours": 0, "cpu": 0.0, "coups": 0, "file": []}
            self.bc_m["boucles_tentees"] += 1
            self.niv_boucle = True  # CW-169 : ce niveau sort du mode rapide
            self._noter({"t": time.time(), "source": "boucle", "ouverture": True, "raison": raison, "niveau": niv + 1})
        bc, lim = self.bc, self.bc_lim
        while True:
            if bc["file"] and bc["coups"] < lim["coups"]:
                a = bc["file"].pop(0)
                self.en_boucle = True
                try:
                    self.step_env({"actions": [a]})
                finally:
                    self.en_boucle = False
                return True
            bc["file"] = []
            motif = ("tours" if bc["tours"] >= lim["tours"] else "cpu" if bc["cpu"] >= lim["cpu_s"]
                     else "coups" if bc["coups"] >= lim["coups"] else None)
            if motif is not None:
                self._fermer_boucle(False, f"budget {motif}")
                return False
            bc["tours"] += 1
            t0 = time.process_time()
            try:
                issue = self._tour_boucle(bc)
            finally:
                dt = time.process_time() - t0
                bc["cpu"] += dt
                self.bc_m["boucle_cpu_s"] += dt
            if issue == "plan":
                return self._jouer_plan()  # 1er coup du plan : _suivre_moteur ferme la boucle en réussite
            if issue == "faible":
                return True  # coup déjà joué par _plan_faible
            if issue == "tuto" and self._tour_tuto():
                return True

    def _contexte(self, bc):
        return {"branche": self, "moteur": self.moteur, "grilles": list(self.hist["grilles"]),
                "lots": list(self.hist["lots"]), "precedents": list(self.precedents), "raison": bc["raison"],
                "contre": self.contre, "suivi": self.suivi is not None, "dernier": dict(self.dernier),
                "infos": dict(self.infos_m), "inconnues": set(self.inconnues), "tuto": self.mt is not None,
                "tour": bc["tours"], "cpu_restant_s": max(0.0, self.bc_lim["cpu_s"] - bc["cpu"]),
                "coups_restants": max(0, self.bc_lim["coups"] - bc["coups"])}

    def _tour_boucle(self, bc):
        """Un tour : diagnostic → action de l'étage → jugement. → "plan" | "faible" | "tuto" | None (tour sans succès)."""
        ctx = self._contexte(bc)
        etage, test, det = self.dg.diagnostic(ctx)
        d = self.bc_m["diagnostics"]
        e = "aucun" if etage is None else str(etage)
        d["par_etage"][e] = d["par_etage"].get(e, 0) + 1
        if test is not None:
            k = f"{etage}:{test}"
            d["par_test"][k] = d["par_test"].get(k, 0) + 1
        nom, res = self.dg.agir(etage, ctx)
        self._noter({"t": time.time(), "source": "boucle", "diagnostic": True, "tour": bc["tours"], "etage": etage,
                     "test": test, "action": nom, "details": {k: v for k, v in det.items() if k != "resultats"},
                     "resultats": [f"{x['etage']}:{x['test']}={x['statut']}" for x in det["resultats"]]})
        if res is None:
            return None
        if res.get("tuto"):
            return "tuto" if self._ouvrir_tuto_boucle(ctx["coups_restants"]) else None
        if res.get("experience"):
            bc["file"] = list(res["experience"])[:ctx["coups_restants"]]
            return None
        if "proposition" in res:
            r, infos = res["proposition"], dict(res.get("infos") or {})
            if getattr(self.moteur, "porte_propre", False) and r is not None and r[1] is None:
                return "faible" if self._plan_faible(r, infos) else None
            self._examiner(r, infos, extra={"boucle": bc["tours"], "etage": etage})
            return "plan" if self.plan is not None else None
        return None

    def _ouvrir_tuto_boucle(self, reste):
        """Étage 5 : mini-tutoriel rouvert pour au plus `reste` coups (CHRYS_TUTO seulement)."""
        from chrysalide.arc3.moteur import Tutoriel, budget_s
        if self.mt is None or self.tuto is not None or not self.precedents or reste <= 0:
            return False
        fl, cl = self._actions_offertes()
        self.tuto, inc = Tutoriel.ouvrir(list(self.precedents), self.hist["grilles"][0],
                                         len(self.hist["lots"]) + reste, limite_s=budget_s(), fleches=fl, clics=cl)
        if self.tuto is None:
            return False
        self._noter({"t": time.time(), "source": "tuto", "ouverture": True, "boucle": True,
                     "niveau": len(self.precedents) + 1, "classes": sorted(int(c) for c in inc), "budget": reste})
        return True

    def _fermer_boucle(self, reussie, motif):
        bc, self.bc = self.bc, None
        if reussie:
            self.bc_m["boucles_reussies"] += 1
        else:
            self.bc_echecs.add((bc["niveau"], bc["raison"]))
        self._noter({"t": time.time(), "source": "boucle", "fin": motif, "reussie": reussie, "raison": bc["raison"],
                     "tours": bc["tours"], "cpu_s": round(bc["cpu"], 3), "coups": bc["coups"]})

    def _declencheur(self):
        """Raison pour laquelle le modèle reprend la main (CW-133), dans l'ordre de priorité."""
        if self.contre:
            return "contre_exemple"  # divergence d'un plan, théorie suivie qui ne prédit plus, refus de la porte
        if self.suivi is not None or self.infos_m.get("sans_but"):
            return "sans_but"  # théorie vérifiée (porte, ou rejeu de C) mais aucun plan vers un but
        if self.inconnues:
            return "classe_inconnue"  # niveau aux classes inconnues de la théorie précédente (après le tutoriel)
        if self.infos_m.get("ne_rejoue_plus"):
            return "contre_exemple"  # la théorie des niveaux réussis ne rejoue pas ce niveau
        if not self.precedents:
            return "debut_jeu"  # aucun niveau réussi, aucune théorie
        return "filet"  # pas de théorie vérifiée : Franzen comme aujourd'hui

    def restituer_auto(self):
        """D (CHRYS_HISTORIQUE_FIDELE) : le résumé de séquence que Franzen lira décrit les coups joués POUR lui
        (suffixés « (auto) »), pas sa propre séquence précédente, qui n'explique plus le plateau courant."""
        analyseur = getattr(self.s, "analyzer", None)
        if self.payloads_auto and analyseur is not None and hasattr(analyseur, "_summarize_step_sequence"):
            resume = analyseur._summarize_step_sequence(self.payloads_auto)
            if resume:
                analyseur._last_step_summary = resume
                self._resume_auto = resume
                self._garder_resume(analyseur)
            self.payloads_auto = []

    def _garder_resume(self, analyseur):
        """Coups joués avant le tout 1er tour de Franzen : sa mise en route de session efface le résumé (vu au pod, 30/10).
        Une seule fois : après cette mise en route, on remet le résumé s'il a été effacé."""
        origine = getattr(analyseur, "_ensure_session", None)
        if origine is None or "_ensure_session" in vars(analyseur):
            return

        def ensure(*a, **k):
            del analyseur._ensure_session
            r = origine(*a, **k)
            if analyseur._last_step_summary is None:
                analyseur._last_step_summary = self._resume_auto
            return r
        analyseur._ensure_session = ensure

    def _au_modele(self):
        """Le modèle va jouer le tour : raison nommée, comptée, rappel du déclencheur, consignes exactes pour l'analyseur."""
        r = self._declencheur()
        nouveau, self.raison = r != self.raison, r
        self.declencheurs[r] += 1
        consigne = self.rappels.get(r, rappel_neutre)(self, r, nouveau)
        analyseur = getattr(self.s, "analyzer", None)
        self.restituer_auto()
        if analyseur is not None and os.environ.get("CHRYS_INSPECT") == "1":  # D (CW-357) : ce que sait le moteur
            from chrysalide.arc3.inspect_franzen import etat_pour_franzen
            analyseur._chrys_inspect = etat_pour_franzen(self)
        if analyseur is not None:  # lus par outils_repl.ligne_tour (CHRYS_MOTEUR allumé seulement)
            analyseur._chrys_consigne = consigne or None
            analyseur._chrys_etat = self.ligne_etat()

    def ligne_etat(self):
        """P10 (CW-134) : une ligne exacte, attributs d'état de la théorie vérifiée à l'état courant ; None sans attribut."""
        if self.suivi is None:
            return None
        try:
            att = self.moteur.attributs(self.suivi["prog"], self.suivi["scene"])
        except Exception:  # noqa: BLE001 — moteur sans attributs lisibles : rien n'est affiché
            return None
        if not att:
            return None
        return ("State attributes of the verified theory (it replays every frame of this level exactly): "
                + ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in att.items()) + ".")

    def _fin_tuto(self, raison):
        self._noter({"t": time.time(), "source": "tuto", "fin": raison, "journal": dict(self.tuto.journal)})
        self.tuto = None

    def _actions_offertes(self):
        """(flèches, clics) : `available_actions` de l'image si le framework la donne ; sinon flèches, et clics seulement si
        l'agent a déjà cliqué dans ce jeu (observé, aucun oracle)."""
        dispo = getattr(self.s.current_frame(), "available_actions", None)
        if dispo:
            ids = {int(getattr(a, "value", a)) for a in dispo}
            return bool(ids & {1, 2, 3, 4}), 6 in ids
        lots = [lot for p in self.precedents for lot in [*p["lots"], p["finale"]]] + list(self.hist["lots"])
        return True, any(str(a.get("action", "")).upper() in ("MOUSE", "ACTION6") for lot in lots for a in lot["actions"])

    def bilan(self):
        b = {"jeu": self.jeu, "coups_sans_llm": self.routeur.n_sans_llm, "deliberations": self.routeur.n_deliberations,
             "reflexes_invalides": self.verif.n_invalides, "reflexes": len(self.memoire.reflexes),
             "signatures_mortes": len(self.moniteur.morts), "coups_route": self.n_route, "surprises": self.n_surprises}
        if self.moteur is not None:  # CHRYS_MOTEUR : tours servis, coups joués par plan, divergences, temps CPU
            b.update({f"moteur_{k}": round(v, 3) if isinstance(v, float) else v for k, v in self.m.items()})
            if getattr(self, "styles", None) is not None:  # D (CW-285) : tranches jouées par style
                b["moteur_styles"] = self.styles.journal[-200:]
            # CW-133 : tours modèle par raison ; part des actions jouées par le plan du moteur ; jetons générés par le
            # modèle (ToolAgent.generated_tokens de Franzen) par niveau réussi, None si inconnus ou aucun niveau réussi
            jetons = getattr(getattr(self.s, "analyzer", None), "generated_tokens", None)
            b.update({"declencheurs": dict(self.declencheurs),
                      "part_coups_moteur": round(self.m["coups_plan"] / self.n_coups, 3) if self.n_coups else None,
                      "jetons_llm_par_niveau_gagne": round(int(jetons) / len(self.precedents), 1)
                      if isinstance(jetons, (int, float)) and self.precedents else None,
                      # Tycho (c) : pas d'optimum dans l'agent (aucun oracle) ; un banc compare coups_plan_par_niveau
                      # (par niveau réussi : coups joués, dont coups de plan, plan gagnant ou non) aux optimums BFS
                      "coups_sur_optimum": None, "coups_plan_par_niveau": [dict(x) for x in self.par_niveau]})
            mp = getattr(self.moteur, "mesures_processus", None)  # CHRYS_MOTEUR_PROCESSUS : appels, octets, délais
            if mp is not None:
                b["moteur_processus"] = {k: round(v, 3) if isinstance(v, float) else v for k, v in mp.items()}
        if self.mt is not None:  # CHRYS_TUTO : niveaux tutorés, coups d'expérience (hors moteur_coups_plan), classes inconnues
            b.update(self.mt)
        if self.bc_m is not None:  # CHRYS_BOUCLE : blocages, boucles tentées / réussies, coût, diagnostics par étage et test
            b.update({k: round(v, 3) if isinstance(v, float) else v for k, v in self.bc_m.items() if k != "diagnostics"})
            b["diagnostics"] = {k: dict(v) for k, v in self.bc_m["diagnostics"].items()}
        return b

    def _noter(self, x):
        """Journal : ne doit JAMAIS faire tomber l'agent (E2E4 : des clés non textuelles dans les infos du moteur ont levé
        TypeError et planté la partie). Clés converties en texte, valeurs inconnues en repr ; toute erreur est avalée."""
        def propre(v):
            if isinstance(v, dict):
                return {str(k): propre(w) for k, w in v.items()}
            if isinstance(v, (list, tuple, set)):
                return [propre(w) for w in v]
            return v if isinstance(v, (str, int, float, bool)) or v is None else repr(v)[:200]
        try:
            ligne = json.dumps(propre(x), ensure_ascii=False)
            with open(self.trace, "a", encoding="utf-8") as f:
                f.write(ligne + "\n")
        except Exception:  # noqa: BLE001, S110 — un journal en échec ne coûte qu’une ligne
            pass
