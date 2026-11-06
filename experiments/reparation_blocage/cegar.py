"""CEGAR existentiel sur graphe fini : concretisation puis séparation du bloc fautif."""
import time
from collections import deque


def chercher(graphe, initial, buts, cles=None, complet=False, iterations=100, secondes=1):
    debut = time.process_time()
    etats = set(graphe)
    if initial not in etats or not set(buts) <= etats:
        raise ValueError('Etat initial ou buts absents du graphe')
    if any(cible not in etats for arcs in graphe.values() for cible in arcs.values()):
        raise ValueError('Toute cible doit etre representee, meme comme frontiere vide')
    # Séparer les buts garantit que concrétiser jusqu'au dernier bloc atteint bien le but.
    groupes = {}
    for s in graphe:
        cle = (s in buts, cles[s] if cles is not None else None)
        groupes.setdefault(cle, set()).add(s)
    blocs = list(groupes.values())
    journal = []
    statut, plan = 'budget', None
    for _ in range(iterations):
        if time.process_time() - debut >= secondes:
            break
        bloc = {s: i for i, ss in enumerate(blocs) for s in ss}
        arcs = {i: set() for i in range(len(blocs))}
        for s, aa in graphe.items():
            for a, t in aa.items():
                arcs[bloc[s]].add((a, bloc[t]))
        origine = bloc[initial]
        file = deque([(origine, [], [origine])])
        vus = {origine}
        chemin = None
        while file:
            if time.process_time() - debut >= secondes:
                break
            courant, actions, parcours = file.popleft()
            if blocs[courant] & set(buts):
                chemin = actions, parcours
                break
            for a, b in sorted(arcs[courant], key=repr):
                if b not in vus:
                    vus.add(b)
                    file.append((b, actions + [a], parcours + [b]))
        if chemin is None:
            statut = ('budget' if time.process_time() - debut >= secondes else
                      'inaccessible_dans_modele' if complet else 'inconnu_graphe_tronque')
            break
        actions, parcours = chemin
        possibles = {initial}
        for i, a in enumerate(actions):
            suivants = {graphe[s][a] for s in possibles if a in graphe[s]
                        and bloc[graphe[s][a]] == parcours[i + 1]}
            if not suivants:
                # Le bloc contient d'autres états qui fournissent un arc impossible depuis ce préfixe.
                b = parcours[i]
                reste = blocs[b] - possibles
                if not reste or not possibles:
                    raise AssertionError('Raffinement non strict')
                journal.append({'pas_fallacieux': i + 1, 'bloc_taille': len(blocs[b]),
                                'separation': [len(possibles), len(reste)]})
                blocs[b] = possibles
                blocs.append(reste)
                break
            possibles = suivants
        else:
            if not possibles & set(buts):
                raise AssertionError('But non concretise')
            statut, plan = 'plan_concret_verifie', actions
            break
    return plan, {'statut': statut, 'raffinements': journal, 'blocs': len(blocs),
                  'etats_concrets': len(etats), 'graphe_complet': complet,
                  'preuve_sur_jeu_reel': False, 'cpu_s': time.process_time() - debut}
