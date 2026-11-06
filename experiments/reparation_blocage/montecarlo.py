"""NMCS niveau 1 et témoin aléatoire ; simulateur et heuristique fournis par le moteur."""
import random
import time


def chercher(initial, actions, pas, gagne, perd, note, profondeur, secondes,
             graine=0, methode='nmcs', transitions_max=100000):
    if methode not in ('nmcs', 'aleatoire'):
        raise ValueError(methode)
    rng = random.Random(graine)
    debut = time.process_time()
    deadline = debut + secondes
    transitions = 0
    meilleur, valeur = None, None

    class Budget(Exception):
        pass

    def avancer(etat, action):
        nonlocal transitions
        if transitions >= transitions_max or time.process_time() >= deadline:
            raise Budget
        transitions += 1
        return pas(etat, action)

    def evaluer(etat, suite):
        return (int(gagne(etat)), -len(suite) if gagne(etat) else note(etat))

    def garder(etat, suite):
        nonlocal meilleur, valeur
        v = evaluer(etat, suite)
        if valeur is None or v > valeur:
            valeur, meilleur = v, list(suite)
        return v

    def rollout(etat, suite, vus):
        suite, vus = list(suite), set(vus)
        while len(suite) < profondeur and not gagne(etat) and not perd(etat):
            essais = list(actions)
            rng.shuffle(essais)
            for a in essais:
                nouveau = avancer(etat, a)
                if nouveau not in vus and not perd(nouveau):
                    etat = nouveau
                    vus.add(etat)
                    suite.append(a)
                    break
            else:
                break
        return garder(etat, suite), suite

    try:
        if gagne(initial):
            return [], {'transitions': 0, 'cpu_s': 0, 'victoire_simulee': True}
        while time.process_time() < deadline and transitions < transitions_max:
            if methode == 'aleatoire':
                rollout(initial, [], {initial})
            else:
                etat, prefixe, vus = initial, [], {initial}
                retenue, score_retenu = None, None
                while len(prefixe) < profondeur and not gagne(etat):
                    for a in actions:
                        prochain = avancer(etat, a)
                        if prochain in vus or perd(prochain):
                            continue
                        score, suite = rollout(prochain, prefixe + [a], vus | {prochain})
                        if score_retenu is None or score > score_retenu:
                            retenue, score_retenu = suite, score
                    if retenue is None or len(retenue) <= len(prefixe):
                        break
                    a = retenue[len(prefixe)]
                    etat = avancer(etat, a)
                    prefixe.append(a)
                    vus.add(etat)
                    garder(etat, prefixe)
            if valeur and valeur[0]:
                break
    except Budget:
        pass
    return (meilleur if valeur and valeur[0] else None), {
        'transitions': transitions, 'cpu_s': time.process_time() - debut,
        'victoire_simulee': bool(valeur and valeur[0]), 'methode': methode, 'graine': graine}
