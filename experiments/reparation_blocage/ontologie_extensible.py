"""Familles conditionnelles et extensions sur traces ; aucun droit d'action."""
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from chrysalide.langue import depuis_python
from chrysalide.langue.ontologie_formelle import MECANISMES, separer_pour_transfert
from chrysalide.langue.theorie_contrats import vers_contrats

if __package__:
    from .atms import ATMS
else:
    from atms import ATMS


def _familles():
    nom = '_chrysalide_familles_existantes'
    if nom not in sys.modules:
        chemin = Path(__file__).resolve().parents[1] / 'defi_llm/couche6/strategies/familles.py'
        spec = importlib.util.spec_from_file_location(nom, chemin)
        module = importlib.util.module_from_spec(spec)
        sys.modules[nom] = module
        spec.loader.exec_module(module)
    return sys.modules[nom]


def _sha(valeur):
    return hashlib.sha256(json.dumps(valeur, sort_keys=True).encode()).hexdigest()


def _serialisable(valeur):
    if isinstance(valeur, dict):
        return {str(k): _serialisable(v) for k, v in valeur.items()}
    if isinstance(valeur, (set, frozenset)):
        return [_serialisable(v) for v in sorted(valeur, key=repr)]
    if isinstance(valeur, (list, tuple)):
        return [_serialisable(v) for v in valeur]
    return valeur


class FicheRevision:
    """Une classification dépend de toute sa théorie, sans prétention causale fine."""

    def __init__(self, theorie, actions, contexte, **indices):
        f = _familles()
        autorises = {'modele_visible', 'memoire', 'glissade', 'bascule_au_clic', 'propagation_voisins'}
        if set(indices) - autorises or any(type(v) is not bool for v in indices.values()):
            raise ValueError('Indices explicites booleens requis')
        contrats = vers_contrats(theorie)
        self.contrats = copy.deepcopy(contrats)
        self.economie = decrire_economie(theorie)
        # Les objets ne sont pas reconstruits depuis des couleurs ou un nom de jeu.
        # Seuls les rôles déjà portés par les champs actifs alimentent le reconnaisseur.
        controles = {k[0] for k in theorie.moves} | {k[0] for k in theorie.moves_supposes}
        objets = [{'roles': [role]} for role, classes in (
            ('controle', controles), ('poussable', theorie.poussables),
            ('autonome', theorie.autonomes)) for _ in classes]
        if theorie.but and theorie.but[0] == 'sortie':
            objets.append({'roles': ['cible']})
        if theorie.selection_clic or theorie.exclusif or theorie.desel:
            objets.append({'roles': ['selectionnable']})
        actions = ['CLICK' if a == 'MOUSE' else a for a in actions]
        signaux = f.signaux_depuis_objets(objets, actions, jauge=bool(theorie.jauge), **indices)
        # Une configuration de bascule n'est pas nécessairement un bouton individuel.
        if 'bascule_au_clic' not in indices:
            signaux.bascule_au_clic = bool(theorie.bascule)
        if 'glissade' not in indices:
            signaux.glissade = bool(theorie.glisse)
        if 'memoire' not in indices:
            signaux.memoire = bool(theorie.fantome or theorie.retour)
        if 'propagation_voisins' not in indices:
            signaux.propagation_voisins = bool(theorie.motif and any(dx or dy for dx, dy in theorie.motif))
        self.signaux = vars(signaux).copy()
        self.atms = ATMS()
        self.contexte = [self.atms.supposer('snapshot:' + _sha(contexte))]
        self.candidats = []
        for famille, score in f.reconnaitre(signaux):
            noeud = 'famille:' + famille
            self.atms.justifier(noeud, self.contexte)
            self.candidats.append({'famille': famille, 'score_heuristique': score,
                                   'noeud': noeud, 'recommandation': f.recommandation(famille, signaux)})

    def revoquer(self):
        self.atms.interdire(self.contexte)

    def rapport(self):
        valides = [copy.deepcopy(c) for c in self.candidats if self.atms.tient(c['noeud'], self.contexte)]
        transfert = [separer_pour_transfert({'mecanisme': i['contrat'], 'params': i['params']})
                     for i in self.contrats['instances'] if i['section'] in ('mecanisme', 'hypothese')]
        return {'statut': 'classification_conditionnelle' if valides else 'classification_revoquee',
                'economie_du_jeu': copy.deepcopy(self.economie),
                'candidats': valides, 'signaux': copy.deepcopy(self.signaux),
                'contrats': _serialisable(self.contrats), 'dependances': self.contexte.copy(),
                'transfert_candidat': _serialisable(transfert) if valides else [],
                'transfert_confirme': False,
                'probabilites_calibrees': False, 'droit_action': False,
                'limite': 'Indices absents inconnus ; catalogue a cinq familles proposees non reconnues ici'}


def _transitions(chaine):
    return {_sha([avant, lot, apres]) for avant, lot, apres in
            zip(chaine.grilles, chaine.lots, chaine.grilles[1:])}


class ExtensionCandidate:
    """Programme existant : compatibilité mesurée, jamais ajout automatique au vocabulaire."""

    def __init__(self, source, mecanismes, portee):
        if len(source) > 64000 or not mecanismes or set(mecanismes) - MECANISMES.keys():
            raise ValueError('Composition de mecanismes connus requise')
        if portee not in ('niveau', 'jeu', 'interjeux'):
            raise ValueError('Portee explicite requise')
        self.programme = depuis_python(source)
        self.source_sha = hashlib.sha256(source.encode()).hexdigest()
        self.mecanismes, self.portee = sorted(set(mecanismes)), portee
        self.bilan = {'statut': 'proposee', 'droit_action': False}

    def verifier(self, developpement, reserves):
        if not developpement or not reserves or any(not c.lots for c in [*developpement, *reserves]):
            raise ValueError('Deux ensembles de transitions non vides requis')
        vus = set().union(*map(_transitions, developpement))
        tenus = set().union(*map(_transitions, reserves))
        if vus & tenus:
            raise ValueError('Transitions reservees deja vues')
        rapports = []
        for ensemble, chaines in (('developpement', developpement), ('reserve', reserves)):
            for c in chaines:
                controle, etat = c.rejouer(copy.deepcopy(self.programme))
                conforme = etat is not None and all(controle.get(k) for k in
                    ('catalogue_shacl', 'traduction_python', 'rejeu', 'compilation_fidele'))
                rapports.append({'ensemble': ensemble, 'snapshot': c.signature(),
                                  'conforme': conforme, 'controle': controle})
        self.bilan = {'statut': 'compatible_sur_traces' if all(r['conforme'] for r in rapports) else 'refusee',
                      'source_sha256': self.source_sha, 'portee_demandee': self.portee,
                      'mecanismes_declares': self.mecanismes, 'rapports': rapports,
                      'transitions_developpement': len(vus), 'transitions_reservees': len(tenus),
                      'transfert_demontre': False, 'primitive_nouvelle': False,
                      'victoire_reelle_verifiee': False, 'droit_action': False}
        return copy.deepcopy(self.bilan)


def priorites_capacites(description, noms):
    """Hypothèse perceptive → ordre du catalogue existant, jamais exclusion."""
    translation = any(not p['region_bord'] for p in description['translation']['preuves'])
    clic = 'MOUSE' in description['canaux_observes']
    if translation and clic:
        priorite = [n for n in noms if n.startswith('selection_')]
    elif translation:
        priorite = [n for n in noms if n in ('objets', 'objets_contact')]
    else:
        priorite = []
    return {'statut':'priorite_hypothetique', 'prioritaires':priorite,
        'secondaires':[n for n in noms if n not in priorite],
        'familles_non_exclusives':description['memoire_familles_prior_seulement'],
        'preuves':{'translation':description['translation'],
                    'transformation_motif':description['transformation_motif'],
                    'canaux':description['canaux_observes']},
        'inconnues':description['inconnues'], 'droit_action':False,
        'reouverture':'refus_plan_ou_divergence', 'catalogue_complet_conserve':True}


def decrire_economie(theorie=None):
    """Axe transversal à toutes les familles ; inconnues explicites, pas lois universelles."""
    from chrysalide.langue.ontologie_formelle import ECONOMIE, PERCEPTION, OPTIONS_DOMAINE
    return {
        'statut': 'hypotheses_a_verifier',
        'niveau': 'description_generale_du_jeu',
        'reserve_compteurs_vies': {k: {'statut': 'inconnu', 'definition': v}
                                  for k,v in ECONOMIE['fluents'].items()},
        'vies_optionnelles': copy.deepcopy(OPTIONS_DOMAINE['vies']),
        'presence_objets': {'visible': 'preuve perceptive',
                           'non_visible': 'absence de preuve visuelle, pas destruction',
                           'consomme': 'effet causal candidat sur present'},
        'contrats': ['ECONOMIE', 'MECANISMES.ramassage',
                     'PERCEPTION.indice_de_rendu', 'PERCEPTION.sol_sous_occultant'],
        'projection': copy.deepcopy(PERCEPTION),
        'consommations_candidates': sorted(map(list,theorie.consomme)) if theorie else [],
        'jauge_candidate': bool(theorie.jauge) if theorie else False,
        'questions': ['Objet hors champ, occulté, transformé ou consommé ?',
                      'Une ressource change-t-elle après ce contact ?',
                      'Le retour au même endroit confirme-t-il la disparition ?'],
        'droit_action': False,
    }
