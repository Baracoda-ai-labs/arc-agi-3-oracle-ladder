# SPDX-License-Identifier: MIT-0
"""D (CW-316, décision de Thomas) : PERCEPTION RÉVISABLE PAR LA PRÉDICTION (CHRYS_PERCEPTION_PORTEFEUILLE=1, éteint).
Au lieu d'allumer un découpage pour tous les jeux, MoteurC perçoit et induit sous 2 à 3 CONFIGURATIONS des drapeaux de
perception existants, et garde celle dont la théorie (1) rejoue le mieux l'historique, puis (2) prédit le mieux les
dernières transitions quand on l'induit SANS elles (prédiction à un pas, recalée). Égalité → la configuration de base
(le moteur actuel). La configuration retenue reste posée dans l'environnement jusqu'au prochain appel (la porte de la
branche perçoit alors comme l'induction). CHRYS_PORTEFEUILLE_CONFIGS="DESOUDER=1;FORMES=0" remplace la liste par défaut
(la base, toujours première, n'y figure pas)."""
import os

CONFIGS = ({"CHRYS_DESOUDER": "1"}, {"CHRYS_FORMES": "0"})
_BASE = {}  # valeurs d'origine des clés touchées (mémorisées au 1er appel)


def configs():
    s = os.environ.get("CHRYS_PORTEFEUILLE_CONFIGS")
    if not s:
        return [{}, *CONFIGS]
    out = [{}]
    for bloc in s.split(";"):
        kv = dict(x.split("=", 1) for x in bloc.split(",") if "=" in x)
        out.append({(k if k.startswith("CHRYS_") else "CHRYS_" + k): v for k, v in kv.items()})
    return out


def _poser(cfg, cles):
    for k in cles:
        _BASE.setdefault(k, os.environ.get(k))
    for k in cles:
        v = cfg.get(k, _BASE[k])
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def choisir(percevoir, n_actions, infos, held=None):
    """percevoir(k) → (resultat, tr, th) : perception + induction sur les k premières transitions (k = None : toutes).
    → le résultat de la meilleure configuration. infos["portefeuille"] = scores par configuration."""
    from chrysalide.arc3.logique.theorie import rejeu
    cs = configs()
    cles = {k for c in cs for k in c}
    m = held if held is not None else max(1, min(5, n_actions // 4))
    meilleur, scores = None, []
    for i, cfg in enumerate(cs):
        _poser(cfg, cles)
        res, tr, th = percevoir(None)
        th.hors_jeu = tr.exclues
        ok, n, _ = rejeu(th, tr)
        pred = None
        if n_actions > m + 1:
            _, _, th_k = percevoir(n_actions - m)
            th_k.hors_jeu = tr.exclues
            pred = rejeu(th_k, tr, debut=n_actions - m, libre=False)[0]
        sc = (ok / max(1, n), (pred or 0) / m)
        scores.append({"config": cfg, "rejeu": [ok, n], "prediction": [pred, m]})
        if meilleur is None or sc > meilleur[0]:
            meilleur = (sc, i, res)
    _poser(cs[meilleur[1]], cles)
    infos["portefeuille"] = {"retenue": cs[meilleur[1]], "scores": scores}
    return meilleur[2]
