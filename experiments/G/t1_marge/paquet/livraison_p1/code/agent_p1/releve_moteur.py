"""C (CW-454/455/456, T1) : relève de MoteurC DANS l'exploration générique de P1, derrière `CHRYS_P1_MOTEUR`
(absent = P1 inchangé ; `observe` = le moteur propose, ne joue jamais ; `joue` = il joue son plan sous la porte).

Déclenchement : à 40, 80 et 120 coups du niveau, une fois chacun (jamais deux fois la même tentative). Historique = les
40 derniers coups de la vie en cours (après le dernier RESET) : une induction sur toute l'exploration de P1 ne rejoue
presque jamais (T1a, CCM-330-C). Budget CPU par appel : `CHRYS_P1_MOTEUR_CPU` (30 s) ; P1 ne fait qu'attendre ce calcul.

ENTONNOIR (schéma de B, CCM-306-B), une ligne de journal `{"type": "moteur", "etape": …}` à chaque étape franchie :
occasion → historique → theorie → but → plan → autorise → intervention → resultat.

PORTE (CW-455/456), écrite dans la ligne `autorise` :
- `replay_errors` : erreurs de rejeu de la fenêtre par le programme exporté (porte de rejeu de la branche) ;
- `goal_status` : `hypothese` (but supposé) ou `induit` ; `victoire_observee` si un niveau de ce jeu a déjà été gagné ;
- `untested_interactions_on_plan` : interactions du plan (action, et couleur de la case visée pour un clic) jamais
  observées dans la fenêtre (CCM-333-C : au pixel près, la 1re version refusait les plans gagnants de ft09) ;
- `planned_actions`, `resource_margin` (coups restants au budget du niveau), `first_action_prediction` (image prédite
  après le 1er coup, en nombre de cases qui changent).
Autorisé si : rejeu de la fenêtre sans erreur, au plus 1 interaction non étayée, plan dans la marge. Le but SUPPOSÉ est
permis (CW-455 : « de préférence » déjà vu gagner) et noté comme tel.

INTERVENTION : le plan est joué coup par coup ; chaque image observée est comparée à l'image prédite par le programme.
1re divergence, mort ou plan fini sans victoire → arrêt, P1 reprend sur l'état réel (la transition fausse reste dans
l'historique de P1). Victoire → `victoire_moteur` (attribution `gagnant = "moteur"`)."""
import os
import time

import numpy as np

NOMS = {1: 'UP', 2: 'DOWN', 3: 'LEFT', 4: 'RIGHT', 5: 'SPACE', 7: 'UNDO'}
DECLENCHEURS = (40, 80, 120)
FENETRE = 40


def _lot(a):
    if isinstance(a, (list, tuple)) and len(a) == 3:  # ('clic', x, y) → MOUSE row = y, col = x
        return {'actions': [{'action': 'MOUSE', 'row': int(a[2]), 'col': int(a[1])}]}
    return {'actions': [{'action': NOMS.get(a, str(a))}]}


def _vers_p1(c):
    return ('clic', int(c[1]), int(c[2])) if isinstance(c, tuple) else int(c)


def tenter(ex, mode):
    """→ 'victoire_moteur' si le plan du moteur gagne le niveau, sinon None (P1 continue)."""
    from chrysalide.arc3.moteur import MoteurC, _code_c, nom_action, porte
    lab, j = ex.lab, ex.j
    k, niv = len(lab.rows), lab.level
    log = lambda etape, **kw: j.ecrire('moteur', etape=etape, niveau=niv, coup=k, mode=mode, **kw)  # noqa: E731
    log('occasion')
    debut = max((t + 1 for t, r in enumerate(lab.rows) if r['action'] == 0), default=0)
    acts = [r['action'] for r in lab.rows[debut:]][-FENETRE:]
    imgs = lab.images[debut:k + 1][-(len(acts) + 1):]
    if len(acts) < 2:
        return None
    grilles, lots = [np.asarray(g).tolist() for g in imgs], [_lot(a) for a in acts]
    log('historique', coups=len(acts))
    m = MoteurC(budget=float(os.environ.get('CHRYS_P1_MOTEUR_CPU', '30')))
    t0 = time.process_time()
    r = m.proposer({'grilles': grilles, 'lots': lots, 'precedents': []})
    cpu = round(time.process_time() - t0, 2)
    refus = m.infos.get('refus') or ''
    if 'ne rejoue pas' in refus and not r:
        return None
    log('theorie', cpu_s=cpu)
    if not r and 'pas de but' in refus:
        return None
    log('but', but=m.infos.get('but_suppose') or m.infos.get('theorie', '')[-60:], origine=m.infos.get('origine'))
    if not r:
        log('sans_plan', refus=refus[:120], cpu_s=cpu)
        return None
    plan = [_vers_p1(_code_c(x if 'action' in x else x['actions'][0])) for x in r[0]]
    log('plan', longueur=len(plan), cpu_s=cpu)
    p = porte(m, r[1], grilles, lots) if r[1] else None
    def inter(a, im):  # interaction = (action, couleur de la case visée) ; un clic exact au pixel près serait trop strict
        if isinstance(a, (list, tuple)) and len(a) == 3:
            return ('clic', int(np.asarray(im)[int(a[2]), int(a[1])]))
        return a
    vues = {inter(a, im) for a, im in zip(acts, imgs)}
    gate = dict(replay_errors=0 if p is not None else 'echec', goal_status='hypothese' if m.infos.get('origine') == 'but_suppose'
                else 'induit', victoire_observee=niv > 1, untested_interactions_on_plan=sum(inter(a, imgs[-1]) not in vues for a in plan),
                planned_actions=len(plan), resource_margin=150 - k - len(plan), first_action_prediction=None)
    if p is not None:
        try:
            import copy
            prog1, sc1 = copy.deepcopy(p)
            avant = np.asarray(m.rendu(sc1))
            prog1.step(sc1, nom_action(r[0][0] if 'action' in r[0][0] else r[0][0]['actions'][0]))
            gate['first_action_prediction'] = int((np.asarray(m.rendu(sc1)) != avant).sum())
        except Exception:  # noqa: BLE001
            gate['first_action_prediction'] = 'erreur'
    autorise = p is not None and gate['untested_interactions_on_plan'] <= 1 and gate['resource_margin'] >= 0
    if autorise and os.environ.get('CHRYS_P1_MARGE') == '1':  # G (CW-457, bras « marge ») : plan ≤ moitié de la marge
        autorise = gate['planned_actions'] <= gate['resource_margin'] / 2
    log('autorise' if autorise else 'refuse', **gate)
    if not autorise or mode != 'joue':
        return None
    prog, sc = p
    log('intervention', longueur=len(plan))
    for i, (a, x) in enumerate(zip(plan, r[0])):
        lab.play(a, 'moteur_t1')
        ex.t1_coups = getattr(ex, 't1_coups', 0) + 1
        if lab.won:
            log('resultat', issue='victoire', coups=i + 1)
            return 'victoire_moteur'
        try:
            prog.step(sc, nom_action(x if 'action' in x else x['actions'][0]))
            juste = sc.issue is None and np.array_equal(np.asarray(m.rendu(sc)), np.asarray(m.vue(lab.image.tolist())))
        except Exception:  # noqa: BLE001 — prédiction impossible = divergence
            juste = False
        if lab.finished or not juste:
            log('resultat', issue='mort' if lab.finished else 'divergence', coups=i + 1)
            return None
    log('resultat', issue='plan_fini_sans_victoire', coups=len(plan))
    return None
