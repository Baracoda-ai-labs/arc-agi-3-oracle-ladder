"""ATMS Horn borné : labels minimaux et nogoods, sans diagnostic causal automatique."""
import copy
from itertools import product


class LimiteATMS(RuntimeError):
    pass


def minimaux(contextes):
    retenus = set()
    for c in sorted(set(contextes), key=lambda x: (len(x), sorted(x))):
        if not any(r <= c for r in retenus):
            retenus.add(c)
    return retenus


class ATMS:
    FAUX = '__contradiction__'

    def __init__(self, limite=4096):
        self.limite = limite
        self.hypotheses, self.faits = set(), set()
        self.justifications, self.interdits = [], set()
        self.labels, self.nogoods = {}, set()

    def _modifier(self, operation):
        ancien = copy.deepcopy(self.__dict__)
        try:
            operation()
            self._calculer()
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(ancien)
            raise

    def supposer(self, nom):
        if nom in self.faits or nom == self.FAUX:
            raise ValueError('Hypothese incompatible avec un fait ou le noeud faux')
        self._modifier(lambda: self.hypotheses.add(nom))
        return nom

    def fait(self, nom):
        if nom in self.hypotheses:
            raise ValueError('Une hypothese ne peut devenir un fait')
        self._modifier(lambda: self.faits.add(nom))
        return nom

    def justifier(self, conclusion, antecedents):
        if conclusion in self.hypotheses:
            raise ValueError('Consequent hypothese interdit dans cet ATMS Horn')
        justification = (conclusion, tuple(antecedents))
        if justification not in self.justifications:
            self._modifier(lambda: self.justifications.append(justification))

    def interdire(self, contexte):
        c = frozenset(contexte)
        if not c <= self.hypotheses:
            raise ValueError('Hypothese inconnue')
        self._modifier(lambda: self.interdits.add(c))

    def _calculer(self):
        noeuds = self.hypotheses | self.faits | {self.FAUX}
        for c, aa in self.justifications:
            noeuds.update((c, *aa))
        if len(noeuds) + len(self.justifications) > self.limite:
            raise LimiteATMS('Trop de noeuds ou justifications')
        labels = {n: set() for n in noeuds}
        for h in self.hypotheses:
            labels[h] = {frozenset({h})}
        for f in self.faits:
            labels[f] = {frozenset()}
        operations = 0
        change = True
        while change:
            change = False
            for c, aa in self.justifications:
                nouveaux = set(labels[c])
                for combinaison in product(*(labels[a] for a in aa)):
                    operations += 1
                    if operations > self.limite * 16:
                        raise LimiteATMS('Propagation bornee ; aucun resultat partiel accepte')
                    nouveaux.add(frozenset().union(*combinaison))
                    if len(nouveaux) > self.limite:
                        raise LimiteATMS('Trop de contextes')
                nouveaux = minimaux(nouveaux)
                if nouveaux != labels[c]:
                    labels[c], change = nouveaux, True
        nogoods = minimaux(self.interdits | labels[self.FAUX])
        self.nogoods = nogoods
        self.labels = {n: {e for e in ee if not any(g <= e for g in nogoods)}
                       for n, ee in labels.items()}

    def tient(self, noeud, contexte):
        contexte = frozenset(contexte)
        if not contexte <= self.hypotheses:
            raise ValueError('Hypothese inconnue')
        return not any(g <= contexte for g in self.nogoods) and any(
            e <= contexte for e in self.labels.get(noeud, ()))

    def rapport(self):
        return {'labels': {n: [sorted(e) for e in sorted(ee, key=lambda e: (len(e), sorted(e)))]
                           for n, ee in sorted(self.labels.items())},
                'nogoods': [sorted(e) for e in sorted(self.nogoods, key=lambda e: (len(e), sorted(e)))]}
