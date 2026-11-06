# SPDX-License-Identifier: MIT-0
"""CHRYS_MOTEUR_PROCESSUS=1 (éteint par défaut ; sans effet si CHRYS_MOTEUR éteint) : le calcul du moteur formel tourne
dans un PROCESSUS ouvrier attitré au jeu, pour que son CPU (induction ASP, Python pur) ne tienne plus le GIL du harnais
(essai apparié pod, 20 jeux : 447 → 244 tours/h avec CHRYS_MOTEUR=1, moteur muet).

`MoteurDistant(moteur)` est un mandataire de même interface pour branche.py :
- `proposer` et `classes_inconnues` partent dans l'ouvrier ; le parent attend sur un tube (`poll` : GIL libéré) ;
- `scene`, `vue`, `rendu`, `attributs` (porte de rejeu, suivi coup par coup, diagnostic) restent locaux, sur l'instance
  d'origine dont la perception `tr` est recopiée allégée (sans les états du niveau) quand l'ouvrier en change ;
- tout autre attribut (budget, porte_propre, limite_plan…) est celui de l'instance locale ; `budget` et `limite_plan`
  sont renvoyés à l'ouvrier à chaque appel. Les caches du moteur (MoteurCle : rôles, carnets) vivent dans l'ouvrier.
Historique envoyé de façon INCRÉMENTALE : par clé (grilles, lots, films, precedents), seuls les éléments ajoutés depuis
l'envoi précédent partent (préfixe reconnu par identité d'objet ; sinon renvoi complet de la clé). Hypothèse : branche.py
ne modifie jamais en place un élément déjà envoyé (il ajoute ou recrée les listes).
Ouvrier = `python -m chrysalide.arc3.moteur_processus` (subprocess, deux tubes) plutôt que multiprocessing « spawn » :
spawn réimporte le `__main__` du harnais dans l'enfant. L'ouvrier reçoit l'instance d'origine picklée (état initial),
les variables CHRYS_* du parent à chaque appel, et sys.path du parent (PYTHONPATH).
Délai dur par appel CHRYS_MOTEUR_PROCESSUS_DELAI_S (défaut : 0,9 × CHRYS_GARDE_TOUR_S si > 0, sinon 600 s), attente
d'une place comprise : au-delà, l'ouvrier est tué (le résultat tardif n'arrive jamais), relancé au prochain appel avec
l'état initial (caches recalculés), et l'appel rend None (refus « délai processus »). Au plus CHRYS_MOTEUR_OUVRIERS
(défaut 2) calculs simultanés dans le processus parent (sémaphore, attente sans GIL)."""
import copy
import inspect
import os
import pickle
import subprocess
import sys
import threading
import time
import traceback
import weakref
from multiprocessing.connection import Connection

CLES = ("grilles", "lots", "films", "precedents")
REGLAGES = ("budget", "limite_plan")
_PROPRES = frozenset({"_local", "_h", "_init", "_envoye", "_verrou", "_fin", "infos", "cpu_hors_processus_s",
                      "mesures_processus"})
_sem, _sem_n, _sem_verrou = None, None, threading.Lock()


def delai_s():
    try:
        v = float(os.environ.get("CHRYS_MOTEUR_PROCESSUS_DELAI_S", "0") or 0)
    except ValueError:
        v = 0.0
    if v > 0:
        return v
    try:
        g = float(os.environ.get("CHRYS_GARDE_TOUR_S", "120"))
    except ValueError:
        g = 120.0
    return 0.9 * g if g > 0 else 600.0


def _semaphore():
    global _sem, _sem_n
    try:
        n = max(1, int(os.environ.get("CHRYS_MOTEUR_OUVRIERS", "2")))
    except ValueError:
        n = 2
    with _sem_verrou:
        if _sem is None or _sem_n != n:
            _sem, _sem_n = threading.BoundedSemaphore(n), n
        return _sem


def _env_chrys():
    return {k: v for k, v in os.environ.items() if k.startswith("CHRYS_")}


def _accepte(fn, nom):
    try:
        p = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return nom in p or any(x.kind is inspect.Parameter.VAR_KEYWORD for x in p.values())


class _Echec(Exception):
    pass


def _tuer(h):
    with h["verrou"]:
        p, h["p"] = h["p"], None
        conns, h["conns"] = h["conns"], ()
    for c in conns:
        try:
            c.close()
        except OSError:
            pass
    if p is not None:
        try:
            p.kill()
            p.wait(timeout=10)
        except Exception:  # noqa: BLE001, S110 — déjà mort
            pass


class MoteurDistant:
    def __init__(self, moteur):
        d = self.__dict__
        d["_local"], d["_init"] = moteur, pickle.dumps(moteur, protocol=5)
        d["_h"] = {"p": None, "conns": (), "verrou": threading.Lock(), "ferme": False}
        d["_envoye"], d["_verrou"] = {}, threading.Lock()
        d["infos"], d["cpu_hors_processus_s"] = {}, 0.0
        d["mesures_processus"] = {"appels": 0, "demarrages": 0, "delais": 0, "morts": 0, "octets_envoyes": 0,
                                  "octets_max": 0, "octets_recus": 0, "attente_s": 0.0}
        d["_fin"] = weakref.finalize(self, _tuer, d["_h"])

    # ---------------------------------------------------------------- interface locale (légère)
    def __getattr__(self, nom):
        return getattr(self.__dict__["_local"], nom)

    def __setattr__(self, nom, v):
        if nom in _PROPRES:
            self.__dict__[nom] = v
        else:
            setattr(self._local, nom, v)

    def scene(self, g):
        return self._local.scene(g)

    def vue(self, g):
        return self._local.vue(g)

    def rendu(self, scene):
        return self._local.rendu(scene)

    def attributs(self, prog, scene):
        return self._local.attributs(prog, scene)

    # ---------------------------------------------------------------- interface distante (coûteuse)
    def proposer(self, historique, **kw):
        kw = {k: v for k, v in kw.items() if _accepte(self._local.proposer, k)}
        t0 = time.monotonic()
        try:
            rep = self._appel("proposer", historique, kw=kw)
        except _Echec as e:
            self.infos = {"refus": str(e), "cpu_s": round(time.monotonic() - t0, 3)}
            return None
        self.infos = rep["infos"]
        return rep["r"]

    def classes_inconnues(self, precedents, g0):
        t0 = time.monotonic()
        try:
            rep = self._appel("classes_inconnues", {"precedents": precedents}, g0=g0)
        except _Echec:
            self.cpu_hors_processus_s = time.monotonic() - t0
            return None
        self.cpu_hors_processus_s = rep["cpu_s"]
        return rep["r"]

    def fermer(self):
        """Tue l'ouvrier (sans prendre le verrou : un appel en attente, abandonné par la garde, finit sur None)."""
        self._h["ferme"] = True
        _tuer(self._h)

    # ---------------------------------------------------------------- mécanique
    def _demarrer(self):
        r1, w1 = os.pipe()  # parent → ouvrier
        r2, w2 = os.pipe()  # ouvrier → parent
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
        try:
            # nom du module tel qu'il est importé ICI : « chrysalide.arc3 » au dépôt, « inference.chrysalide_arc3 » dans le
            # harnais de Franzen (patcher_franzen.py renomme le paquet ; un nom écrit en dur ne s'y importerait pas)
            module = f"{__package__}.moteur_processus" if __package__ else "chrysalide.arc3.moteur_processus"
            p = subprocess.Popen([sys.executable, "-m", module, str(r1), str(w2)],
                                 pass_fds=(r1, w2), env=env, stdin=subprocess.DEVNULL)
        finally:
            os.close(r1)
            os.close(w2)
        with self._h["verrou"]:
            self._h["p"], self._h["conns"] = p, (Connection(w1, readable=False), Connection(r2, writable=False))
        self._envoye.clear()
        self.mesures_processus["demarrages"] += 1

    def _deltas(self, historique):
        d, nouveaux = {}, {}
        for k in CLES:
            if k not in historique:
                if k in self._envoye:
                    d[k] = ("absent",)
                    nouveaux[k] = None
                continue
            lst, anc = list(historique[k]), self._envoye.get(k)
            if anc is not None and len(anc) <= len(lst) and all(a is b for a, b in zip(anc, lst, strict=False)):
                if len(lst) > len(anc):
                    d[k] = ("ext", lst[len(anc):])
            else:
                d[k] = ("tout", lst)
            nouveaux[k] = lst
        return d, nouveaux

    def _appel(self, op, historique, **charge):
        with self._verrou:
            m, h, delai = self.mesures_processus, self._h, delai_s()
            fin = time.monotonic() + delai
            if h["ferme"]:
                raise _Echec("ouvrier fermé")
            sem = _semaphore()
            t0 = time.monotonic()
            if not sem.acquire(timeout=delai):
                m["delais"] += 1
                raise _Echec(f"délai processus dépassé ({delai:.0f} s, file d'attente)")
            m["attente_s"] += time.monotonic() - t0
            try:
                init = None
                if h["p"] is None or h["p"].poll() is not None:
                    _tuer(h)
                    self._demarrer()
                    init = self._init
                deltas, nouveaux = self._deltas(historique)
                loc = self._local
                msg = {"op": op, "init": init, "env": _env_chrys(), "deltas": deltas, **charge,
                       "reglages": {k: getattr(loc, k) for k in REGLAGES if hasattr(loc, k)}}
                data = pickle.dumps(msg, protocol=5)
                m["appels"] += 1
                m["octets_envoyes"] += len(data)
                m["octets_max"] = max(m["octets_max"], len(data))
                try:
                    cin, cout = h["conns"]
                    cin.send_bytes(data)
                    if not cout.poll(max(0.0, fin - time.monotonic())):
                        m["delais"] += 1
                        _tuer(h)
                        raise _Echec(f"délai processus dépassé ({delai:.0f} s)")
                    brut = cout.recv_bytes()
                except (EOFError, OSError, ValueError) as e:
                    m["morts"] += 1
                    _tuer(h)
                    raise _Echec(f"ouvrier mort : {type(e).__name__}") from e
            finally:
                sem.release()
            m["octets_recus"] += len(brut)
            rep = pickle.loads(brut)
            for k, v in nouveaux.items():
                if v is None:
                    self._envoye.pop(k, None)
                else:
                    self._envoye[k] = v
            if "erreur" in rep:  # état de l'ouvrier incertain : relancé neuf au prochain appel
                _tuer(h)
                raise RuntimeError(f"moteur distant : {rep['erreur']}\n{rep.get('trace', '')}")
            if "tr" in rep:
                self._local.tr = rep["tr"]
            return rep


# -------------------------------------------------------------------- côté ouvrier
def _allege(tr):
    """Perception sans les états du niveau (scene/vue/rendu n'ont besoin que d'échelle, fond, masque, classes)."""
    if tr is None:
        return None
    c = copy.copy(tr)
    for a in ("cases", "etats", "actions"):
        if a in vars(c):
            setattr(c, a, [])
    return c


def _appliquer_env(env):
    for k in [k for k in os.environ if k.startswith("CHRYS_") and k not in env]:
        del os.environ[k]
    os.environ.update(env)


def principal(fd_in, fd_out):
    cin, cout = Connection(fd_in, writable=False), Connection(fd_out, readable=False)
    moteur, store, dernier_tr = None, {}, None
    while True:
        try:
            msg = pickle.loads(cin.recv_bytes())
        except (EOFError, OSError):
            return
        try:
            if msg.get("init") is not None:
                moteur, store, dernier_tr = pickle.loads(msg["init"]), {}, None
            _appliquer_env(msg["env"])
            for k, d in msg["deltas"].items():
                if d[0] == "absent":
                    store.pop(k, None)
                elif d[0] == "tout":
                    store[k] = list(d[1])
                else:
                    store.setdefault(k, []).extend(d[1])
            for k, v in msg["reglages"].items():
                setattr(moteur, k, v)
            t0 = time.process_time()
            if msg["op"] == "proposer":
                r = moteur.proposer({k: list(store[k]) for k in CLES if k in store}, **msg["kw"])
            else:
                r = moteur.classes_inconnues(list(store.get("precedents", [])), msg["g0"])
            rep = {"r": r, "infos": dict(getattr(moteur, "infos", {}) or {}), "cpu_s": time.process_time() - t0}
            tr = getattr(moteur, "tr", None)
            if tr is not dernier_tr:
                rep["tr"], dernier_tr = _allege(tr), tr
        except Exception as e:  # noqa: BLE001 — renvoyée au parent, qui la relève comme le moteur local
            rep = {"erreur": f"{type(e).__name__}: {e}", "trace": traceback.format_exc(limit=8)}
        cout.send_bytes(pickle.dumps(rep, protocol=5))


if __name__ == "__main__":
    principal(int(sys.argv[1]), int(sys.argv[2]))
