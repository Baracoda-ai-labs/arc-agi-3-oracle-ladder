"""Adaptateur du graphe compilé existant ; aucune nouvelle sémantique de jeu."""
import time
from collections import deque

from chrysalide.arc3.logique.plan_langage import cle_complete
from chrysalide.arc3.sim_rapide import cloner


def proposer(pc, scene, actions, secondes, noeuds=500):
    if __package__:
        from .cegar import chercher
    else:
        from cegar import chercher
    debut = time.process_time()
    initial = cle_complete(scene, pc.etat)
    etats = {initial: cloner(scene, pc.etat)}
    graphe, buts, file = {initial: {}}, set(), deque([initial])
    complet = True
    while file:
        if time.process_time() - debut >= secondes * .7:
            complet = False
            break
        cle = file.popleft()
        sc0, etat0 = etats[cle]
        if sc0.issue in ('niveau', 'victoire'):
            buts.add(cle)
        if sc0.issue is not None:
            continue
        for action in actions:
            if time.process_time() - debut >= secondes * .7:
                complet = False
                break
            sc, pc.etat = cloner(sc0, etat0)
            pc.step(sc, action)
            cible = cle_complete(sc, pc.etat)
            if cible not in etats:
                if len(etats) >= noeuds:
                    complet = False
                    continue
                etats[cible] = (sc, pc.etat)
                graphe[cible] = {}
                file.append(cible)
                if sc.issue in ('niveau', 'victoire'):
                    buts.add(cible)
            graphe[cle][action] = cible
    cpu_graphe = time.process_time() - debut
    plan, infos = chercher(graphe, initial, buts, complet=complet,
                          secondes=max(0, secondes - cpu_graphe))
    return plan, {**infos, 'cpu_graphe_s': cpu_graphe, 'backend': 'ProgrammeCompile',
                  'limite_etats': noeuds, 'construction_concrete_prealable': True}
