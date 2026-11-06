"""Filtrage, déduplication par classes d'équivalence observationnelle, et score configurable.

score(H) = erreur_obs(H) + lambda * complexite(H) + mu * incoherence(H)
  erreur_obs = w_transition * #transition + w_rendu * #rendu + w_perception * #non_lu
  incoherence = désaccords internes (route latente incohérente entre vies) + pas non prédictibles / 10
Coefficients par défaut : une erreur de transition vaut 10 bits (lambda=0.1 => 1 bit de description = 0.1 erreur).
Une hypothèse n'est jamais « prouvée » par son rang : le statut reste 'survivante' tant qu'aucune
intervention discriminante n'a été jouée et vérifiée sur des données non utilisées pour l'inventer.
"""
from collections import defaultdict
from .simulation import simuler

PARAMS = dict(w_transition=1.0, w_rendu=0.5, w_perception=0.2, lam=0.1, mu=1.0)


def evaluer(hyps, objet, lignes, model, t_invention, params=PARAMS, portes_initiales=()):
    """Simule chaque hypothèse sur TOUTES les transitions ; sépare erreurs sur données d'invention (t <= t_invention)
    et sur données de validation (t > t_invention)."""
    for h in hyps:
        preds, err, nonp, expl = simuler(h.programme, objet, lignes, model, portes_initiales)
        h.__dict__['predictions'] = preds
        h.contredit = err; h.non_predit = nonp; h.explique = expl
        h.__dict__['err_invention'] = [e for e in err if e[0] <= t_invention]
        h.__dict__['err_validation'] = [e for e in err if e[0] > t_invention]
        nt = sum(e[1] == 'transition' for e in err); nr = sum(e[1] == 'rendu' for e in err)
        inc = h.__dict__.get('incoherence_route', 0) + len(nonp) / 10
        h.score = params['w_transition'] * nt + params['w_rendu'] * nr + params['lam'] * h.cout + params['mu'] * inc
        if err:
            h.statut = 'rejetee'
            e = err[0]
            h.preuve_rejet = dict(t=e[0], categorie=e[1], predit=e[2], observe=e[3],
                                  jeu_de_donnees='invention' if e[0] <= t_invention else 'validation')
        else:
            h.statut = 'survivante'
    return hyps


def classes_equivalence(hyps):
    """Regroupe les survivantes aux prédictions identiques sur toutes les données enregistrées."""
    cl = defaultdict(list)
    for h in hyps:
        if h.statut == 'survivante':
            cl[tuple(map(str, h.__dict__['predictions']))].append(h)
    out = []
    for sig, membres in cl.items():
        membres.sort(key=lambda h: (h.score, h.id))
        out.append(dict(representant=membres[0], membres=membres, score=membres[0].score))
    out.sort(key=lambda c: c['score'])
    return out


def sensibilite(hyps, objet, lignes, model, t_invention, grille=None):
    """Rang du représentant de tête pour une grille de (lambda, mu) ; signale les inversions."""
    grille = grille or [(l, m) for l in (0.01, 0.1, 0.5, 1.0, 2.0) for m in (0.0, 1.0, 5.0)]
    res = []
    for lam, mu in grille:
        p = dict(PARAMS, lam=lam, mu=mu)
        evaluer(hyps, objet, lignes, model, t_invention, p)
        cl = classes_equivalence(hyps)
        tete = cl[0]['representant'] if cl else None
        res.append(dict(lam=lam, mu=mu, n_survivantes=sum(h.statut == 'survivante' for h in hyps),
                        tete=tete.id if tete else None, tete_effet=tete.programme['effet'] if tete else None,
                        tete_destruction=tete.programme['destruction'] if tete else None))
    evaluer(hyps, objet, lignes, model, t_invention, PARAMS)
    return res
