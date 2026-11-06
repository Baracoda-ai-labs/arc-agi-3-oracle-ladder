"""Vues du catalogue existant et contrôles SHACL réels, en diagnostic seulement."""
import importlib.metadata
import json
from pathlib import Path
from urllib.parse import quote

from pyshacl import validate
from rdflib import RDF, SKOS, XSD, BNode, Graph, Literal, Namespace
from rdflib.collection import Collection

ICI = Path(__file__).resolve().parent
EX = Namespace('urn:chrysalide:')
SH = Namespace('http://www.w3.org/ns/shacl#')


def noeud(categorie, nom):
    return EX[categorie + ':' + quote(nom, safe='')]


def liste(g, valeurs):
    tete = BNode()
    Collection(g, tete, valeurs)
    return tete


def propriete(g, forme, chemin, minimum, maximum=None, datatype=None, valeurs=None):
    p = BNode()
    g.add((forme, SH.property, p))
    g.add((p, SH.path, chemin))
    g.add((p, SH.minCount, Literal(minimum)))
    if maximum is not None:
        g.add((p, SH.maxCount, Literal(maximum)))
    if datatype is not None:
        g.add((p, SH.datatype, datatype))
    if valeurs is not None:
        g.add((p, SH['in'], liste(g, valeurs)))


def construire(catalogue):
    donnees, formes = Graph(), Graph()
    for g in (donnees, formes):
        for prefixe, ns in [('chrys', EX), ('skos', SKOS), ('sh', SH)]:
            g.bind(prefixe, ns)
    schema = EX.concepts
    donnees.add((schema, RDF.type, SKOS.ConceptScheme))
    donnees.add((schema, EX.version, Literal(catalogue['version'])))
    donnees.add((schema, EX.sourceSHA256, Literal(catalogue['source_sha256'])))
    for nom in catalogue.get('observations', []):
        n = noeud('observation', nom)
        donnees.add((n, RDF.type, SKOS.Concept))
        donnees.add((n, RDF.type, EX.Observation))
        donnees.add((n, SKOS.prefLabel, Literal(nom, lang='fr')))
        donnees.add((n, SKOS.inScheme, schema))
    for role in catalogue['roles']:
        n = noeud('role', role)
        donnees.add((n, RDF.type, SKOS.Concept))
        donnees.add((n, SKOS.prefLabel, Literal(role, lang='fr')))
        donnees.add((n, SKOS.inScheme, schema))
    for nom, m in catalogue['mecanismes'].items():
        n = noeud('mecanisme', nom)
        donnees.add((n, RDF.type, EX.Mecanisme))
        donnees.add((n, RDF.type, SKOS.Concept))
        donnees.add((n, SKOS.prefLabel, Literal(nom, lang='fr')))
        donnees.add((n, SKOS.definition, Literal(m['pre'] + ' ; ' + m['effets'], lang='fr')))
        donnees.add((n, SKOS.inScheme, schema))
        donnees.add((n, EX.phase, Literal(m['phase'])))
        donnees.add((n, EX.testDepartage, Literal(m['test'], lang='fr')))
        for param in m['params']:
            donnees.add((n, EX.parametre, Literal(param)))
        for role in m['roles']:
            r = noeud('role', role)
            donnees.add((n, EX.role, r))
            donnees.add((n, SKOS.related, r))
        for exemple in m['contre_exemples']:
            donnees.add((n, SKOS.scopeNote, Literal(exemple, lang='fr')))
        forme = noeud('forme', nom)
        formes.add((forme, RDF.type, SH.NodeShape))
        formes.add((forme, SH.targetNode, n))
        propriete(formes, forme, SKOS.prefLabel, 1, 1, RDF.langString)
        propriete(formes, forme, SKOS.definition, 1, 1, RDF.langString)
        propriete(formes, forme, SKOS.inScheme, 1, 1, valeurs=[schema])
        propriete(formes, forme, EX.phase, 1, 1, XSD.integer, [Literal(m['phase'])])
        propriete(formes, forme, EX.testDepartage, 1, 1, RDF.langString)
        propriete(formes, forme, EX.parametre, len(m['params']), len(m['params']), XSD.string,
                   [Literal(p) for p in m['params']] if m['params'] else None)
        propriete(formes, forme, EX.role, len(m['roles']), len(m['roles']),
                   valeurs=[noeud('role', r) for r in m['roles']] if m['roles'] else None)
    return donnees, formes


def main():
    catalogue = json.loads((ICI / 'catalogue_ontologie.json').read_text())
    donnees, formes = construire(catalogue)
    ok, rapport, texte = validate(donnees, shacl_graph=formes, inference='none', meta_shacl=True)
    assert ok, texte
    donnees.serialize(ICI / 'ontologie.skos.ttl', format='turtle')
    formes.serialize(ICI / 'ontologie.shapes.ttl', format='turtle')
    rapport.serialize(ICI / 'ontologie.rapport.ttl', format='turtle')
    n = noeud('mecanisme', 'deplacement')
    mutations = {
        'definition_absente': (SKOS.definition, None),
        'phase_incoherente': (EX.phase, Literal(999)),
        'type_phase_incorrect': (EX.phase, Literal('mouvement')),
        'parametres_absents': (EX.parametre, None),
        'parametre_inconnu': (EX.parametre, Literal('invente')),
        'role_inconnu': (EX.role, noeud('role', 'invente')),
    }
    resultats = []
    for nom, (p, v) in mutations.items():
        mutant = Graph()
        for t in donnees:
            mutant.add(t)
        mutant.remove((n, p, None))
        if v is not None:
            mutant.add((n, p, v))
        conforme, _, _ = validate(mutant, shacl_graph=formes, inference='none')
        resultats.append({'cas': nom, 'rejete': not conforme})
        assert not conforme, nom
    bilan = {'portee': 'catalogue des contrats, diagnostic hors parties', 'conforme': bool(ok),
             'mecanismes': len(catalogue['mecanismes']), 'roles': len(catalogue['roles']),
             'pyshacl': importlib.metadata.version('pyshacl'), 'rdflib': importlib.metadata.version('rdflib'),
             'source_sha256': catalogue['source_sha256'], 'mutations': resultats,
             'contrats_sha256': catalogue['contrats_sha256'],
             'preuve_resolubilite': False, 'victoire_arc_supplementaire': 0}
    (ICI / 'bilan_skos_shacl.json').write_text(json.dumps(bilan, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(bilan, ensure_ascii=False))


if __name__ == '__main__':
    main()
