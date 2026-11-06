# SPDX-License-Identifier: MIT-0
"""PORTE V5 (décision Thomas 30/10, contrat E_PORTE5 de Codex), CHRYS_PORTE5=1, éteinte = Franzen inchangé. La v4 du paquet
tourne dans un processus enfant par ouverture : plus de sys.modules partagé ni de verrou global. Le parent reste seul à jouer
(branche.step_env, coups comptés et attribués au moteur) ; une réponse périmée, une action non offerte, un délai ou un plantage
rendent la main sans coup de plus. Ouvertures : au 1er tour du jeu, puis une fois par niveau après CHRYS_STAGNATION_COUPS coups
sans progrès. La main revient aussi à la défaite (jamais de RESET), au budget du niveau, à l'écart de prédiction non réexpliqué
(CHRYS_PORTE5_STRICT=1 seulement, comparateur dans l'enfant), aux sondes épuisées (idem), et à la répétition d'un même coup depuis une même image
sans progrès, hors bordure où vivent les compteurs : seuil empirique, pas une preuve de cycle (empreinte complète journalisée).
Réglages : CHRYS_PORTE_V4_PAQUET, CHRYS_PORTE5_ENFANTS (enfants simultanés, 10 = flux LLM), CHRYS_PORTE5_BUDGET (coups par niveau, 150),
CHRYS_PORTE5_REPET_MAX (3), CHRYS_PORTE5_ATTENTE_S (calcul d'un coup, 90), CHRYS_PORTE5_MUR_S (ouverture, 300),
CHRYS_PORTE5_STRICT (0 = variante empirique, décision Thomas 30/10 15 h 10 : écarts et sondes journalisés sans couper, aucune
prétention prédictive ; 1 = protocole strict du 13 h 25, gardé pour après le 2/11, certificat de réparation encore défectueux,
revue a210a97c), CHRYS_PORTE5_SONDES (coups d'expérience par partie en strict, 4, jamais réarmés)."""
import hashlib
import json
import os
import select
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from pathlib import Path

ENFANT = Path(__file__).with_name("porte_v5_enfant.py")
_QUOTA = None
_QUOTA_FIL = threading.Lock()
BORD = 4  # comme Moniteur : le pourtour porte les compteurs
ENV_ENFANT = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")


def _reglage(nom, defaut):
    try:
        return type(defaut)(os.environ.get(f"CHRYS_PORTE5_{nom}", defaut))
    except ValueError:
        return defaut


def _quota():
    global _QUOTA
    with _QUOTA_FIL:
        if _QUOTA is None:
            _QUOTA = threading.BoundedSemaphore(max(1, _reglage("ENFANTS", 10)))
        return _QUOTA


def empreinte(grille):
    return hashlib.sha256(json.dumps(grille, separators=(",", ":")).encode()).hexdigest()[:16]


class Lecteur:
    """Lignes JSON d'un enfant, avec échéance (aucun fil : le fil du jeu attend son seul enfant)."""

    def __init__(self, proc):
        self.fd, self.tampon = proc.stdout.fileno(), b""

    def lire(self, delai):
        fin = time.monotonic() + delai
        while b"\n" not in self.tampon:
            reste = fin - time.monotonic()
            if reste <= 0 or not select.select([self.fd], [], [], reste)[0]:
                return {"t": "delai"}
            bloc = os.read(self.fd, 65536)
            if not bloc:
                return {"t": "mort"}
            self.tampon += bloc
        ligne, self.tampon = self.tampon.split(b"\n", 1)
        try:
            return json.loads(ligne)
        except ValueError:
            return {"t": "illisible"}


class Porte5:
    def __init__(self, b):
        self.b, self.depart_fait, self.niveaux_tentes = b, False, set()
        self.sondes, self.obs = 0, 0  # sondes de toute la partie ; numéro de la dernière observation envoyée à un enfant
        self.dossier = Path(os.environ.get("CHRYS_DOSSIER", "chrysalide_runs")) / "porte_v5" / str(getattr(b, "jeu", "jeu"))

    def _dispo(self):
        d = getattr(self.b.s.current_frame(), "available_actions", None)
        return [int(getattr(a, "value", a)) for a in d] if d else [1, 2, 3, 4, 5, 6, 7]

    def _etat(self, etat="NOT_FINISHED"):
        self.obs += 1
        return {"grille": self.b._grille(), "niveaux": self.b.moniteur.niveau, "etat": etat, "dispo": self._dispo(),
                "obs": self.obs, "sondes": max(0, _reglage("SONDES", 4) - self.sondes)}

    def _refus(self, m, envoye, grille, t0):
        """Contrôle du parent juste avant de jouer, même pour une action déjà tamponnée : rien n'est délégué à l'enfant."""
        if time.monotonic() - t0 >= _reglage("MUR_S", 300.0):
            return "delai"
        st = str(getattr(self.b.s.current_frame(), "state", ""))
        if "GAME_OVER" in st or "WIN" in st:
            return "etat terminal"
        act = m.get("action") or {}
        offert = 6 if act.get("action") == "MOUSE" else {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5, "UNDO": 7}.get(act.get("action"))
        if (m.get("niveau"), m.get("obs")) != (self.b.moniteur.niveau, envoye["obs"]) or m.get("niveau") != envoye["niveaux"]:
            return "proposition refusee"
        if m.get("sha") != empreinte(grille) or offert not in self._dispo():
            return "proposition refusee"
        if _reglage("STRICT", 0) == 1 and m.get("sonde") and self.sondes >= _reglage("SONDES", 4):
            return "sondes epuisees"
        return None

    def tour(self):
        """→ True si la porte a joué au moins un coup."""
        m = self.b.moniteur
        if "GAME_OVER" in str(getattr(self.b.s.current_frame(), "state", "")):
            return False  # partie à relancer par Franzen : rien à ouvrir
        if not self.depart_fait:
            motif = "depart"
        else:
            try:
                seuil = int(os.environ.get("CHRYS_STAGNATION_COUPS", "0"))
            except ValueError:
                seuil = 0
            if seuil <= 0 or m.actions_niveau < seuil or m.niveau in self.niveaux_tentes:
                return False
            motif = "stagnation"
        quota = _quota()
        if not quota.acquire(blocking=False):  # saturé : Franzen continue, on retentera au tour suivant, sans file d'attente
            self.b._noter({"t": time.time(), "source": "porte_v5", "quota": motif})
            return False
        self.depart_fait = True
        self.niveaux_tentes.add(m.niveau)  # une tentative par niveau, preuves inchangées ensuite
        try:
            res = self._ouvrir(motif)
        finally:
            quota.release()
        self.niveaux_tentes.add(m.niveau)  # le niveau où la porte a rendu la main compte aussi
        return res["coups"] > 0

    def _ouvrir(self, motif):
        b, t0 = self.b, time.monotonic()
        paquet = Path(os.environ.get("CHRYS_PORTE_V4_PAQUET", ""))
        res = {"motif": motif, "niveaux": 0, "coups": 0, "raison": "?", "ecarts": None, "reparations": None, "sondes": 0}
        if not (paquet / "livraison_p1/code/agent_p1/jouer.py").exists():
            res["raison"] = "paquet introuvable"
            b._noter({"t": time.time(), "source": "porte_v5", "fin": res})
            return res
        out = self.dossier / f"{motif}_{b.moniteur.niveau}_{uuid.uuid4().hex[:8]}"  # jamais partagé entre parties
        out.mkdir(parents=True, exist_ok=True)
        budget, repet_max = _reglage("BUDGET", 150), _reglage("REPET_MAX", 3)
        env = {k: os.environ[k] for k in ENV_ENFANT if k in os.environ} | {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
        with open(out / "enfant.err", "ab") as err:
            proc = subprocess.Popen([sys.executable, "-I", str(ENFANT), str(paquet), str(out), str(budget), str(_reglage("STRICT", 0))],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=err, env=env, cwd=out, start_new_session=True)
        lecteur, vus, coups_niveau = Lecteur(proc), Counter(), 0
        try:
            envoye = self._etat()
            proc.stdin.write((json.dumps(envoye) + "\n").encode())
            proc.stdin.flush()
            while True:
                reste = _reglage("MUR_S", 300.0) - (time.monotonic() - t0)
                m = lecteur.lire(min(_reglage("ATTENTE_S", 90.0), max(reste, 0.0)))
                if m.get("t") in ("niveau", "ecart"):
                    b._noter({"time": time.time(), "source": "porte_v5", **m})
                    continue
                if m.get("t") == "fini":
                    res.update(raison=m.get("raison"), ecarts=m.get("ecarts"), reparations=m.get("reparations"))
                    break
                if m.get("t") != "action":
                    res["raison"] = {"delai": "delai", "mort": "enfant mort", "illisible": "reponse illisible"}.get(m.get("t"), "protocole")
                    break
                act = m.get("action") or {}
                grille = b._grille()
                refus = "proposition refusee" if m.get("n") != res["coups"] + 1 else self._refus(m, envoye, grille, t0)
                if refus:
                    res["raison"] = refus
                    break
                cle = (empreinte([r[BORD:-BORD] for r in grille[BORD:-BORD]]), json.dumps(act, sort_keys=True))
                vus[cle] += 1
                if vus[cle] > repet_max:
                    res.update(raison="repetition sans progres", image_complete=empreinte(grille), image_decoupee=cle[0])
                    break
                if coups_niveau >= budget:
                    res["raison"] = "budget"
                    break
                b.en_plan = True  # attribution : coup du moteur
                try:
                    p = b.step_env({"actions": [act]}) or {}
                finally:
                    b.en_plan = False
                res["coups"] += 1
                coups_niveau += 1
                if m.get("sonde"):
                    self.sondes += 1
                    res["sondes"] += 1
                st = str(p.get("state") or "")
                etat = ("WIN" if p.get("run_complete") or "WIN" in st else
                        "GAME_OVER" if p.get("game_over") or "GAME_OVER" in st else "NOT_FINISHED")
                if p.get("level_completed"):
                    res["niveaux"] += 1
                    if os.environ.get("CHRYS_PORTE5_SONDES_PAR") == "niveau":
                        self.sondes = 0  # une victoire réelle, jamais un écart, rouvre le budget
                    vus.clear()
                    coups_niveau = 0
                envoye = self._etat(etat)
                proc.stdin.write((json.dumps(envoye) + "\n").encode())
                proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            res["raison"] = f"enfant coupe : {e!r}"[:200]
        finally:
            proc.kill()  # jamais le SDK : l'enfant n'en a pas
            proc.wait()
            for f in (proc.stdin, proc.stdout):
                try:
                    f.close()
                except OSError:
                    pass
        b.restituer_auto()  # sans moteur, _au_modele n'est jamais appelé : la porte rend elle-même ses coups au LLM
        res["secondes"] = round(time.monotonic() - t0, 1)
        b._noter({"t": time.time(), "source": "porte_v5", "fin": res})
        return res
