# SPDX-License-Identifier: MIT-0
"""D (CW-452 / CW-463 / CW-464, règle de F `prise_de_main.porte_v4`) : PORTE V4 dans le harnais de Franzen, CHRYS_PORTE_V4=1
(éteint = Franzen inchangé). Au PREMIER tour du jeu, la v4 du paquet P1 (poussée, puis fantôme et inventeur ; JAMAIS
l'exploration générique) joue le jeu niveau après niveau, À TRAVERS les coups du vrai jeu de Franzen (`branche.step_env` :
mêmes coups comptés, même journal). Elle garde la main tant qu'elle reconnaît la scène ET gagne le niveau ; au premier
niveau non gagné, ses coups (sonde comprise) restent comptés et Franzen prend la main jusqu'à la fin du jeu, sans nouvelle
sonde. Réserve (CW-455) : la v4 peut reconnaître à tort une scène cachée ; c'est ce que la mesure au pod doit dire.
Paquet : CHRYS_PORTE_V4_PAQUET (dossier `GEL27_moteur_seul_v2`, celui de la mesure de F). Le module `jeux` du paquet est
remplacé, le temps de la porte, par la coquille ci-dessous (`environnement` / `jouer_action`), puis rétabli.
Journal : une ligne `{"source": "porte_v4", …}` par étape dans la trace de la branche (niveau, agent, victoire, coups)."""
import os
import sys
import threading
import time
import types
from pathlib import Path

NOMS = {0: "RESET", 1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 7: "UNDO"}
# A (24/10, P1 au pod) : les 10 jeux de Franzen sont des FILS d'un même processus et la porte retire / rétablit des modules
# dans `sys.modules` (partagé) : deux portes ouvertes ensemble s'effaçaient leurs modules (KeyError 'chrysalide.arc3', g50t
# perdu). Les portes passent donc UNE À LA FOIS ; l'attente est journalisée (coût du bras, CCM-327-B).
_VERROU = threading.Lock()


class _Image:
    def __init__(self, frame, levels_completed, state, available_actions):
        self.frame, self.levels_completed = frame, levels_completed
        self.state, self.available_actions = state, available_actions


class EnvFranzen:
    """Ce que `LaboP1` attend d'un environnement `arc_agi`, branché sur le jeu de Franzen en cours (pas de vrai RESET au
    départ : la partie est déjà au niveau 1, aucune action n'est dépensée)."""

    def __init__(self, b):
        self.b, self.niveaux, self.coups, self.etat = b, 0, 0, "NOT_FINISHED"

    def _dispo(self):
        d = getattr(self.b.s.current_frame(), "available_actions", None)
        return [int(getattr(a, "value", a)) for a in d] if d else [1, 2, 3, 4, 5, 6, 7]

    def _image(self):
        return _Image([self.b._grille()], self.niveaux, self.etat, self._dispo())

    def reset(self):
        return self._image()

    def jouer(self, a):
        if isinstance(a, (list, tuple)) and len(a) == 3:  # ('clic', x, y) → MOUSE, row = y, col = x
            act = {"action": "MOUSE", "row": int(a[2]), "col": int(a[1])}
        else:
            act = {"action": NOMS[int(a)]}
        self.b.en_plan = True  # attribution : coup du moteur (source « moteur » dans la trace), pas de Franzen
        try:
            p = self.b.step_env({"actions": [act]}) or {}
        finally:
            self.b.en_plan = False
        self.coups += 1
        if p.get("level_completed"):
            self.niveaux += 1
        st = str(p.get("state") or "")
        self.etat = ("WIN" if p.get("run_complete") or "WIN" in st else "GAME_OVER" if p.get("game_over") or "GAME_OVER"
                     in st else "NOT_FINISHED")
        return self._image()


def _coquille():
    m = types.ModuleType("chrysalide.arc3.logique.jeux")
    m.environnement = lambda jeu, dossier=None: m.ENV
    m.jouer_action = lambda env, a: env.jouer(a)
    return m


def jouer(b, budget=150, max_niveaux=20):
    """Joue la porte v4 sur la partie de la branche b, une porte à la fois dans le processus (verrou).
    → dict(niveaux gagnés, coups, raison, attente_s). N'élève jamais."""
    t = time.monotonic()
    with _VERROU:
        attente = round(time.monotonic() - t, 1)
        res = _jouer_seul(b, budget, max_niveaux, attente)
    return res


def _jouer_seul(b, budget, max_niveaux, attente=0.0):
    paquet = Path(os.environ.get("CHRYS_PORTE_V4_PAQUET", ""))
    if not (paquet / "livraison_p1/code/agent_p1/jouer.py").exists():
        b._noter({"t": time.time(), "source": "porte_v4", "refus": f"paquet introuvable : {paquet}"})
        return {"niveaux": 0, "coups": 0, "raison": "paquet introuvable"}
    chemins = [str(paquet), str(paquet / "livraison_p1/code"), str(paquet / "references/astra4/livraison_astra4/ajouts")]
    sauve = {k: v for k, v in sys.modules.items() if k == "chrysalide" or k.startswith(("chrysalide.", "agent_p1",
                                                                                        "boucle_v4"))}
    for k in sauve:
        del sys.modules[k]
    sys.path[:0] = chemins
    env = EnvFranzen(b)
    out = Path(os.environ.get("CHRYS_DOSSIER", "chrysalide_runs")) / "porte_v4" / str(getattr(b, "jeu", "jeu"))
    res = {"niveaux": 0, "coups": 0, "raison": "?"}
    t0 = time.monotonic()
    try:
        import chrysalide.arc3.logique as _logique  # le `chrysalide` DU PAQUET (réduit ou complet)
        coq = _coquille()
        coq.ENV = env
        sys.modules["chrysalide.arc3.logique.jeux"] = coq
        _logique.jeux = coq
        import agent_p1.jouer as J
        from agent_p1.journal import Journal
        from agent_p1.labo import LaboP1
        j = Journal(out, "journal_porte", {"jeu": str(getattr(b, "jeu", "")), "budget": budget, "paquet": str(paquet)})
        lab = LaboP1(str(getattr(b, "jeu", "jeu")), 1, None, out / "N1" / "partie")
        for niveau in range(1, max_niveaux + 1):
            od = out / f"N{niveau}"
            r = None
            try:
                r = J.essai_poussee(lab, od, budget, j)
                if not lab.won and len(lab.rows) < budget and not lab.partie_gagnee:
                    if lab.finished:
                        lab.reset_apres_defaite()
                    r = J.essai_fantome(lab, od, budget, j, out / "bibliotheque.json") or r
            except Exception as e:  # noqa: BLE001 — la v4 qui plante rend la main, jamais d'exception vers Franzen
                r = {"agent": "exception", "victoire": False, "raison": repr(e)[:200]}
            b._noter({"t": time.time(), "source": "porte_v4", "niveau": niveau, "agent": (r or {}).get("agent"),
                      "victoire": bool(lab.won), "coups": len(lab.rows), "raison": (r or {}).get("raison")})
            if not lab.won:
                res["raison"] = "non reconnu" if r is None else "non gagné"
                break
            res["niveaux"] += 1
            if lab.partie_gagnee:
                res["raison"] = "partie gagnée"
                break
            lab = lab.next_level(out / f"N{niveau + 1}" / "partie")
    except Exception as e:  # noqa: BLE001
        res["raison"] = f"erreur : {e!r}"[:200]
    finally:
        for k in [k for k in sys.modules if k == "chrysalide" or k.startswith(("chrysalide.", "agent_p1", "boucle_v4"))]:
            del sys.modules[k]
        sys.modules.update(sauve)
        for c in chemins:
            if c in sys.path:
                sys.path.remove(c)
    res["coups"] = env.coups
    res["attente_s"] = attente
    b._noter({"t": time.time(), "source": "porte_v4", "fin": res, "secondes": round(time.monotonic() - t0, 1)})
    return res
