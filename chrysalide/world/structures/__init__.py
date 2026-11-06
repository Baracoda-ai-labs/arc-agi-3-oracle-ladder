"""Gabarits structurels : 3 par famille. Chaque gabarit construit ses entités, faits, règles et outils,
calcule `expected` par exécution (engine.py) et fournit les réponses de politiques triviales sans mémoire."""
from chrysalide.world.schema import Entity, Fact, Rule, Tool


class Ctx:
    """Monde en construction partagé par les gabarits."""

    def __init__(self, rng, namer):
        self.rng, self.namer = rng, namer
        self.entities, self.facts, self.rules, self.tools = [], [], [], []
        self._n = {}

    def _id(self, prefix):
        self._n[prefix] = self._n.get(prefix, 0) + 1
        return f"{prefix}{self._n[prefix]:05d}"

    def entity(self, kind, **attrs) -> Entity:
        e = Entity(self._id("E"), self.namer.make(kind), kind, attrs)
        self.entities.append(e)
        return e

    def fact(self, subject, predicate, obj, valid_from=None, valid_to=None, source_id="S_registre", reliability="fiable") -> Fact:
        f = Fact(self._id("F"), subject, predicate, obj, valid_from, valid_to, source_id, reliability)
        self.facts.append(f)
        return f

    def rule(self, name, version, valid_from, valid_to, body) -> Rule:
        r = Rule(self._id("R"), name, version, valid_from, valid_to, body)
        self.rules.append(r)
        return r

    def tool(self, name, kind, params, description) -> Tool:
        t = Tool(self._id("T"), name, kind, params, description)
        self.tools.append(t)
        return t


def draft(family, sid, inputs, expected, verifier_id, facts, skills, answer_type, context, qparams, trivial):
    return {"family": family, "structure_id": sid, "inputs": inputs, "expected": expected, "verifier_id": verifier_id,
            "requires_facts": [f.id for f in facts], "requires_skills": skills, "answer_type": answer_type,
            "context": context, "qparams": qparams, "trivial": trivial}


def last_number(lines):
    import re
    nums = [int(n) for line in lines for n in re.findall(r"-?\d+", line)]
    return nums[-1] if nums else 0
