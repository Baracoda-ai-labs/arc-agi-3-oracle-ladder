# SPDX-License-Identifier: MIT-0
"""F (CW-444, substitution d'oracle) : `diag4.py` (4 bras A/B/C/D, écrit pour le niveau 1) rejoué au niveau k > 1, sans
toucher à diag4. Le jeu est amené au début du niveau k par le préfixe enregistré (`plafonds.env_au_niveau`) ; une
enveloppe d'environnement rend « début du niveau k » au RESET et décale `levels_completed` de k − 1, pour que les tests
« niveau gagné » de diag4 (levels_completed > 0) restent justes. D (P0) appelle `plafonds.p0(jeu, k)` et capture le plan
vérifié dans le vrai jeu (`verifier_plan`).
Usage : uv run python experiments/oracle/oracle_niveau.py <k> <jeu,jeu…> <sortie.json>"""
import copy
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE / "experiments/instrument"), str(RACINE / "experiments/T3.0"), str(RACINE / "experiments/T3.1")]
import diag4
import plafonds


class Cadre:
    def __init__(self, f, decalage):
        self._f, self._d = f, decalage

    def __getattr__(self, nom):
        if nom in ("_f", "_d"):  # copie : l'objet est reconstruit avant que _f existe
            raise AttributeError(nom)
        return getattr(self._f, nom)

    @property
    def levels_completed(self):
        return self._f.levels_completed - self._d


class EnvNiveau:
    """Environnement au début du niveau k ; copiable (deepcopy copie l'environnement interne)."""

    def __init__(self, env, f0, decalage):
        self._env, self._f0, self._d = env, f0, decalage

    def reset(self):
        return Cadre(self._f0, self._d)

    def step(self, *a, **kw):
        f = self._env.step(*a, **kw)
        return None if f is None else Cadre(f, self._d)

    def __getattr__(self, nom):
        if nom in ("_env", "_f0", "_d"):
            raise AttributeError(nom)
        return getattr(self._env, nom)


_BASE = {}


def environnement_k(k):
    def env(gid, dossier=None):
        if gid not in _BASE:
            e, f = plafonds.env_au_niveau(gid, k)
            if e is None:
                raise RuntimeError(f"niveau {k} non atteint par le préfixe")
            _BASE[gid] = (e, f)
        e, f = _BASE[gid]
        return EnvNiveau(copy.deepcopy(e), f, k - 1)
    return env


def plan_D_k(k):
    """Plan P0 capturé comme dans diag4 (coups passés à `plafonds.jouer`), mais au niveau k : les coups joués sur le
    DERNIER environnement créé par `env_au_niveau` (celui du rejeu de vérification), moins ceux de son préfixe."""
    def plan_D(gid):
        joues, crees = {}, []
        oj, oe = plafonds.jouer, plafonds.env_au_niveau

        def jouer(env, c):
            joues.setdefault(id(env), []).append(c)
            return oj(env, c)

        def env_au_niveau(g, kk):
            e, f = oe(g, kk)
            if e is not None:
                crees.append((e, len(joues.get(id(e), []))))  # garde la référence : id stable
            return e, f
        plafonds.jouer, plafonds.env_au_niveau = jouer, env_au_niveau
        r = {}
        try:
            for rech in ("but", "paliers"):
                joues.clear()
                crees.clear()
                r = plafonds.p0(gid, k, 1000000, 600, rech)
                if r.get("gagne") and crees:
                    e, n = crees[-1]
                    return list(joues.get(id(e), [])[n:]), rech, r
        finally:
            plafonds.jouer, plafonds.env_au_niveau = oj, oe
        return None, None, r
    return plan_D


def main():
    k, jeux, sortie = int(sys.argv[1]), sys.argv[2].split(","), Path(sys.argv[3])
    diag4.environnement = environnement_k(k)
    diag4.plan_D = plan_D_k(k)
    res = json.loads(sortie.read_text()) if sortie.exists() else {}
    for gid in jeux:
        t0 = time.time()
        try:
            res[gid] = {**diag4.diag(gid, 40, 0), "niveau": k}
        except Exception as e:  # noqa: BLE001 — échec compté
            import traceback
            res[gid] = {"jeu": gid, "niveau": k, "plantage": f"{type(e).__name__}: {e}",
                        "pile": traceback.format_exc()[-800:], "secondes": round(time.time() - t0, 1)}
        r = res[gid]
        print(gid, k, {c: (r.get(c) or {}).get("gagne") for c in "ABCD"}, r.get("plantage", ""), flush=True)
        sortie.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
