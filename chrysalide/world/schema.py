"""Schéma d'un monde synthétique (plan 3.1 §3.1). Tout est sérialisable en JSON."""
from dataclasses import asdict, dataclass, field

RELIABILITY = ("fiable", "instruction", "témoignage")  # ordre d'autorité décroissant


@dataclass
class Entity:
    id: str
    name: str
    kind: str  # personne, societe, lieu, devise, produit, fonction, source, etape
    attrs: dict = field(default_factory=dict)


@dataclass
class Fact:
    id: str
    subject: str
    predicate: str
    object: str | int
    valid_from: int | None  # année ou jour, inclus
    valid_to: int | None  # exclu ; None = toujours valide
    source_id: str
    reliability: str


@dataclass
class Rule:
    id: str
    name: str
    version: int
    valid_from: int | None
    valid_to: int | None
    body: dict  # mini-langage interprété par engine.py


@dataclass
class Tool:
    id: str
    name: str
    kind: str  # taux_change, registre, fonction
    params: dict
    description: str


@dataclass
class Task:
    id: str
    family: str  # A outils/code, B règles et faits temporels, C composition/planification
    structure_id: str
    inputs: dict
    expected: object
    verifier_id: str
    requires_facts: list
    requires_skills: list
    answer_type: str  # int, str, code
    prompt: str  # énoncé complet de l'oracle : contexte + question + format
    question: str  # question seule (condition « sans contexte »)
    context: list  # lignes de contexte (faits, règles, outils)
    trivial: dict  # réponses des politiques sans mémoire, calculées par code


def to_dict(obj):
    return asdict(obj)
