# SPDX-License-Identifier: MIT-0
"""Garde-fou de soumission (D, CW-161) : repli Franzen PUR, pour le jeu en cours, sur toute exception de la branche.

Posé par scripts/arc3/patcher_garde.py à la place de `branche.creer` dans solver.py. Pour chaque jeu :
- `creer` qui lève → solveur rendu intact, jeu joué par Franzen seul ;
- `tour()` qui lève, ou `step_env` / `_execute_action` enveloppés qui lèvent APRÈS le vrai coup → le coup déjà joué est
  rendu tel quel (jamais rejoué), les méthodes d'origine du solveur sont remises, `solveur._chrys = None` ;
- une exception levée par le vrai coup lui-même (Franzen) n'est PAS avalée : elle remonte comme sans nous ;
- plafond de temps mural cumulé de la branche par jeu, CHRYS_GARDE_MUR_S (défaut 600 s) : au-delà, même repli ;
- délai DUR par appel de `tour()`, CHRYS_GARDE_TOUR_S (défaut 120 s ; 0 = sans) : `tour()` tourne dans un fil à part ; s'il
  ne rend pas la main à temps (CCM-164-A : `MoteurCle.proposer` peut dépasser 10 min), repli immédiat ; le calcul abandonné
  ne peut plus JOUER aucun coup (son `step_env` lève), il finit seul en arrière-plan.
Chaque repli écrit une ligne dans <CHRYS_DOSSIER>/garde.jsonl (jeu, cause, trace). Aucune exception = comportement de la
branche au point près (contrôle F-C2 : test_garde.py)."""
import json
import os
import threading
import time
import traceback
import types
from pathlib import Path

# porte_v4 importé UNE fois ici : la porte change sys.modules["chrysalide"] le temps de jouer ; un import au tour, hors
# verrou, pouvait alors tomber sur le `chrysalide` du paquet (test à 5 fils, 24/10)
from chrysalide.arc3 import branche, porte_v4, porte_v5


def _mur():
    try:
        return float(os.environ.get("CHRYS_GARDE_MUR_S", "600"))
    except ValueError:
        return 600.0


def _delai_tour():
    try:
        return float(os.environ.get("CHRYS_GARDE_TOUR_S", "120"))
    except ValueError:
        return 120.0


def creer(solveur, dossier=None, **k):
    g = Garde(solveur, dossier)
    return g if g.b is not None else None


class Garde:
    def __init__(self, solveur, dossier=None):
        self.s, self.b, self.mur, self.cause, self.coupe = solveur, None, 0.0, None, False
        self.releve_ferme = None  # CHRYS_RELEVE : numéro du niveau où la relève a été refusée (plus d'appel jusqu'au suivant)
        self.dossier = Path(dossier or os.environ.get("CHRYS_DOSSIER", "chrysalide_runs"))
        self.st0 = solveur.step_env
        self.ex0 = getattr(solveur, "_execute_action", None)
        self._fait = {}  # résultat du VRAI coup de l'appel en cours (step / ex) : rendu tel quel si la suite lève

        def pre_step(_s, arguments):
            if self.coupe:  # calcul abandonné après délai : il ne joue plus rien
                raise RuntimeError("CHRYSALIDE garde : branche coupée (délai), coup refusé")
            self._fait["step_entre"] = True
            p = self.st0(arguments)
            self._fait["step"] = (p,)
            return p
        solveur.step_env = types.MethodType(pre_step, solveur)
        if self.ex0 is not None:
            def pre_ex(_s, *a, **kw):
                if self.coupe:
                    raise RuntimeError("CHRYSALIDE garde : branche coupée (délai), action refusée")
                p = self.ex0(*a, **kw)
                self._fait["ex"] = (p,)
                return p
            solveur._execute_action = types.MethodType(pre_ex, solveur)
        t = time.monotonic()
        try:
            self.b = branche.creer(solveur, dossier)
        except Exception as e:  # noqa: BLE001 — branche impossible à construire : Franzen seul
            self.b = None
            self._noter("creer", e)
        if self.b is None:
            self._remettre()
            return
        self.mur += time.monotonic() - t
        st_b, ex_b = solveur.step_env, getattr(solveur, "_execute_action", None)

        def step(_s, arguments):
            if self.b is None:
                return self.st0(arguments)
            self._fait.pop("step", None)
            self._fait.pop("step_entre", None)
            t0 = time.monotonic()
            try:
                return st_b(arguments)
            except Exception as e:
                if "step" in self._fait:  # le vrai coup a été joué : on le rend, jamais rejoué
                    self._desactiver("step_env", e)
                    return self._fait["step"][0]
                if self._fait.get("step_entre"):
                    raise  # c'est le coup de Franzen qui a levé : comme sans nous
                self._desactiver("step_env", e)
                return self.st0(arguments)
            finally:
                self._compter(t0)
        solveur.step_env = types.MethodType(step, solveur)
        if ex_b is not None and self.ex0 is not None:
            def ex(_s, *a, **kw):
                if self.b is None:
                    return self.ex0(*a, **kw)
                self._fait.pop("ex", None)
                try:
                    return ex_b(*a, **kw)
                except Exception as e:
                    if "ex" not in self._fait:
                        raise  # levée par le vrai coup (Franzen)
                    self._desactiver("_execute_action", e)
                    return self._fait["ex"][0]
            solveur._execute_action = types.MethodType(ex, solveur)

    def tour(self):
        if self.b is None:
            return False
        if os.environ.get("CHRYS_PORTE5") == "1":  # enfant isolé, parent seul joueur (porte_v5.py)
            t0 = time.monotonic()
            try:
                if getattr(self, "p5", None) is None:
                    self.p5 = porte_v5.Porte5(self.b)
                if self.p5.tour():
                    return True
            except Exception as e:  # noqa: BLE001
                self._noter("porte_v5", e)
            finally:
                self._compter(t0)
            if self.b is None:
                return False
        if os.environ.get("CHRYS_PORTE_V4") == "1" and not getattr(self, "porte_faite", False):
            # D (CW-463/464, règle de F) : au 1er tour du jeu, la v4 du paquet joue tant qu'elle reconnaît et gagne ;
            # ensuite Franzen seul jusqu'à la fin du jeu. Fil principal, une seule fois ; une erreur rend la main.
            self.porte_faite = True
            t0 = time.monotonic()
            try:
                if porte_v4.jouer(self.b).get("coups", 0) > 0:
                    return True
            except Exception as e:  # noqa: BLE001
                self._noter("porte_v4", e)
            finally:
                self._compter(t0)
            if self.b is None:
                return False  # aucun coup joué par la porte : le tour continue comme sans elle
        if not self._stagne():  # CW-261 : le moteur ne prend la main que si Franzen stagne sur le niveau
            return False
        if not self._apres_victoire():  # CW-332 (c) : seulement après un niveau gagné par Franzen lui-même
            return False
        if not self._releve():  # CW-401 / CW-412.2 : relève conditionnelle, une seule décision au début du niveau
            return False
        t0, delai, b = time.monotonic(), _delai_tour(), self.b
        self.appels0 = (getattr(b, "m", None) or {}).get("appels")
        try:
            if delai <= 0:
                return self._releve_vu(bool(b.tour()))
            r = {}

            def appel():
                try:
                    r["v"] = bool(b.tour())
                except Exception as e:  # noqa: BLE001 — relevée dans le fil du jeu
                    r["e"] = e
            fil = threading.Thread(target=appel, daemon=True, name="chrysalide_tour")
            fil.start()
            fil.join(delai)
            if fil.is_alive():
                self.coupe = True
                self._desactiver("delai_tour", None)
                return False
            if "e" in r:
                raise r["e"]
            return self._releve_vu(r["v"])
        except Exception as e:  # noqa: BLE001
            self._desactiver("tour", e)
            return False
        finally:
            self._compter(t0)

    def bilan(self):
        return self.b.bilan() if self.b is not None else {"garde_repli": self.cause}

    def __getattr__(self, nom):  # le reste (bilan, moniteur…) : celui de la branche
        b = self.__dict__.get("b")
        if b is None:
            raise AttributeError(nom)
        return getattr(b, nom)

    def _apres_victoire(self):
        """CHRYS_APRES_VICTOIRE=1 (CW-332, politique (c) « finir plus court après une victoire de Franzen ») : le moteur
        n'est consulté que si le DERNIER niveau terminé du jeu l'a été par Franzen (source « modele » du journal des
        événements de la branche). Au niveau 1, ou après un niveau fini par le moteur, Franzen joue seul : il apprend la
        mécanique en jouant (échec ft09 de D, CCM-054-D). Le budget et les défaites : garde de F (CHRYS_ECONOMIE)."""
        if os.environ.get("CHRYS_APRES_VICTOIRE") != "1":
            return True
        fin = next((e for e in reversed(getattr(self.b, "evenements", None) or [])
                    if e.get("evenement") in ("niveau", "victoire")), None)
        return fin is not None and fin.get("source") == "modele"

    def _niveau(self):
        return sum(1 for e in getattr(self.b, "evenements", None) or [] if e.get("evenement") in ("niveau", "victoire"))

    def _releve(self):
        """CHRYS_RELEVE=1 (CW-401, C + D ; implique la politique « après victoire ») : au niveau qui suit une victoire de
        Franzen, le moteur n'est consulté qu'AU DÉBUT (aucun coup de Franzen encore joué sur ce niveau) ou pendant SON plan
        en cours. S'il refuse (porte de confiance fermée, plan trop long : côté moteur, C) ou s'il rend la main (première
        divergence), plus AUCUN appel jusqu'au niveau suivant : Franzen joue seul, sans attendre le moteur (le coût de M0)."""
        if os.environ.get("CHRYS_RELEVE") != "1":
            return True
        fin = next((e for e in reversed(getattr(self.b, "evenements", None) or [])
                    if e.get("evenement") in ("niveau", "victoire")), None)
        if fin is None or fin.get("source") != "modele":
            return False
        niv = self._niveau()
        if self.releve_ferme == niv:
            return False
        depuis = []
        for e in reversed(getattr(self.b, "evenements", None) or []):
            if e.get("evenement") in ("niveau", "victoire"):
                break
            depuis.append(e)
        if any(e.get("source") == "modele" for e in depuis):  # Franzen a déjà joué sur ce niveau : trop tard
            self.releve_ferme = niv
            return False
        if any(e.get("source") == "moteur" for e in depuis) and getattr(self.b, "plan", None) is None:
            self.releve_ferme = niv  # le plan du moteur est fini ou abandonné (divergence) : la main revient à Franzen
            return False
        return True

    def _releve_vu(self, joue):
        """Ferme la relève du niveau seulement après un VRAI appel du moteur qui n'a rien joué (refus noté par le moteur),
        jamais sur un False sans appel (CW-424 : la branche n'appelait pas le moteur sur un niveau sans coup)."""
        appele = (getattr(self.b, "m", None) or {}).get("appels") != getattr(self, "appels0", None)
        if os.environ.get("CHRYS_RELEVE") == "1" and not joue and appele:
            self.releve_ferme = self._niveau()
        return joue

    def _stagne(self):
        """CHRYS_STAGNATION_COUPS = N > 0 (CW-261, D) : prise de main seulement après N actions sur le niveau courant sans
        le finir (Franzen stagne). Le moteur continue d'OBSERVER chaque coup (step_env), il ne propose rien avant. 0 = toujours."""
        try:
            seuil = int(os.environ.get("CHRYS_STAGNATION_COUPS", "0"))
        except ValueError:
            seuil = 0
        n = getattr(getattr(self.b, "moniteur", None), "actions_niveau", None)
        return seuil <= 0 or n is None or n >= seuil

    def _compter(self, t0):
        self.mur += time.monotonic() - t0
        if self.b is not None and self.mur > _mur():
            self._desactiver("mur", None)

    def _remettre(self):
        self.s.step_env = self.st0
        if self.ex0 is not None:
            self.s._execute_action = self.ex0
        a = getattr(self.s, "analyzer", None)
        for k in ("_chrys_budget", "_chrys_etat", "_chrys_consigne"):  # plus aucune ligne de la branche à la consigne
            if a is not None and getattr(a, k, None) is not None:
                setattr(a, k, None)

    def _desactiver(self, cause, e):
        if self.b is not None:
            try:
                bilan = self.b.bilan()
            except Exception:  # noqa: BLE001
                bilan = None
            fermer = getattr(getattr(self.b, "moteur", None), "fermer", None)  # CHRYS_MOTEUR_PROCESSUS : ouvrier tué
            self.b = None
            if fermer is not None:
                try:
                    fermer()
                except Exception:  # noqa: BLE001, S110 — le repli compte plus que l'ouvrier
                    pass
            self._noter(cause, e, bilan)
        self._remettre()
        self.s._chrys = None

    def _noter(self, cause, e, bilan=None):
        self.cause = cause
        jeu = getattr(getattr(getattr(self.s, "game", None), "game_run", None), "game_id", None)  # comme branche.py
        ligne = {"t": time.time(), "jeu": str(jeu), "cause": cause, "mur_s": round(self.mur, 3),
                 "erreur": repr(e) if e is not None else None,
                 "trace": traceback.format_exc(limit=8) if e is not None else None, "bilan": bilan}
        print(f"CHRYSALIDE garde : repli Franzen ({cause}) jeu={jeu} {ligne['erreur']}", flush=True)
        try:
            self.dossier.mkdir(parents=True, exist_ok=True)
            with open(self.dossier / "garde.jsonl", "a") as f:
                f.write(json.dumps(ligne, default=str) + "\n")
        except Exception:  # noqa: BLE001, S110 — disque plein, droits : le repli compte plus que la trace
            pass
