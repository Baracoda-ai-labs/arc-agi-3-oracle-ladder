"""Choix d'expériences sans les jouer : prédictions des hypothèses survivantes, séparation, coût, risque, valeur de plan.

Trois politiques comparables (brief §5) :
  'aleatoire'    : candidat tiré au hasard (graine fixée et journalisée) ;
  'gain_info'    : maximise entropie de la partition des hypothèses / coût ;
  'risque_plan'  : (gain + beta * valeur_plan + gamma * transfert) / coût - rho * risque.
Coût = borne haute du coût en jauge (Economie.cost_upper) ; un candidat non admissible par la jauge est exclu.
Règle de non-dépense : si toutes les hypothèses ayant un plan proposent la même prochaine action, on joue le plan
sans expérience dédiée (l'observation du plan départage gratuitement).
"""
import math, random

PARAMS = dict(beta=1.0, gamma=0.2, rho=5.0, eps=0.5)


def _partition(obs_par_h, poids):
    groupes = {}
    for h, o in obs_par_h.items():
        groupes.setdefault(o, 0.0); groupes[o] += poids[h]
    tot = sum(groupes.values()) or 1.0
    return -sum((w / tot) * math.log2(w / tot) for w in groupes.values() if w > 0), len(groupes)


def evaluer_candidat(seq, modeles, etats, poids, plan_ref=None, economie=None):
    """modeles/etats/poids : dict h -> ... . Rend un dict décrivant la sequence tronquée au 1er pas discriminant."""
    traj = {h: modeles[h].simuler_seq(etats[h], seq)[0] for h in modeles}
    k_disc = None; info = 0.0; ngr = 1
    for k in range(len(seq)):
        obs = {h: (traj[h][k] if k < len(traj[h]) else ('mort',)) for h in modeles}
        H, n = _partition(obs, poids)
        if n > 1:
            k_disc, info, ngr = k, H, n
            break
    pref = seq if k_disc is None else seq[:k_disc + 1]
    risque = sum(poids[h] for h in modeles if any(o == ('mort',) for o in traj[h][:len(pref)]))
    risque /= (sum(poids.values()) or 1.0)
    cout = economie.cost_upper(pref) if economie is not None and economie.valid else float(len(pref))
    admissible = economie.admissible(pref) if economie is not None and economie.valid else True
    vp = 0.0
    if plan_ref:
        c = 0
        for a, b in zip(pref, plan_ref):
            if a != b:
                break
            c += 1
        vp = c / max(1, len(pref))
    return dict(seq=list(pref), k_disc=k_disc, info=info, groupes=ngr, risque=risque, cout=cout,
                admissible=admissible, valeur_plan=vp)


def candidats(modeles, etats, plans, nav_cibles, profondeur=2):
    out = []
    for h, p in plans.items():
        if p:
            out.append(('plan:' + h, list(p)))
    base = list(range(1, 6))
    seqs = [[a] for a in base] + ([[a, b] for a in base for b in base] if profondeur >= 2 else [])
    out += [('primitif', s) for s in seqs]
    out += [('nav:' + str(c), s) for c, s in nav_cibles]
    return out


def choisir(mode, modeles, etats, poids, plans, nav_cibles, economie, plan_ref=None, transfert=None,
            graine=0, params=PARAMS):
    evals = []
    for nom, seq in candidats(modeles, etats, plans, nav_cibles):
        e = evaluer_candidat(seq, modeles, etats, poids, plan_ref, economie)
        e['nom'] = nom
        if not e['admissible'] or not e['seq']:
            continue
        evals.append(e)
    if not evals:
        return None, []
    if mode == 'aleatoire':
        rng = random.Random(graine)
        return rng.choice(evals), evals
    disc = [e for e in evals if e['k_disc'] is not None and e['risque'] < 1.0]
    if mode == 'gain_info':
        if not disc:
            return None, evals
        return max(disc, key=lambda e: (e['info'] / (e['cout'] + params['eps']), -e['cout'])), evals
    # risque_plan
    def u(e):
        tr = (transfert or {}).get(e['nom'], 0.0)
        return (e['info'] + params['beta'] * e['valeur_plan'] + params['gamma'] * tr) / (e['cout'] + params['eps']) \
            - params['rho'] * e['risque']
    pool = disc or [e for e in evals if e['valeur_plan'] > 0]
    if not pool:
        return None, evals
    return max(pool, key=lambda e: (u(e), -e['cout'])), evals
