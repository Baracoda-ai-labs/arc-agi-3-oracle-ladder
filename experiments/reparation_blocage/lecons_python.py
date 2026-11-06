"""Lecon Python : réutilise le lecteur, les macros et le moteur existants."""
import ast
import copy
import hashlib
import json

from chrysalide.arc3.langage import Programme, _parcourir
from chrysalide.langue import depuis_python, vers_python
from chrysalide.langue.traducteur import Refus, _Lecteur, _mot, _regle, _terme

if __package__:
    from .chaine_coherente import empreinte
    from .ontologie_extensible import ExtensionCandidate
else:
    from chaine_coherente import empreinte
    from ontologie_extensible import ExtensionCandidate


METHODES = {'but', 'paliers', 'generique', 'portefeuille', 'nmcs', 'aleatoire', 'cegar'}
CHAMPS = {'id', 'version', 'portee', 'params', 'si', 'mots', 'regles', 'mecanismes',
          'strategie', 'provenance', 'limites', 'statut'}


def _parametres(t):
    if isinstance(t, list):
        if t and t[0] == 'param':
            if len(t) != 2 or not isinstance(t[1], str):
                raise ValueError('param attend un nom literal declare')
            yield t[1]
        for x in t:
            yield from _parametres(x)
    elif isinstance(t, dict):
        for x in t.values():
            yield from _parametres(x)


class LeconPython:
    """La provenance écrite par le proposeur est déclarative, jamais une preuve."""

    def __init__(self, source):
        if len(source) > 64000:
            raise ValueError('Lecon trop longue')
        arbre = ast.parse(source)
        if sum(1 for _ in ast.walk(arbre)) > 8000:
            raise ValueError('Lecon trop complexe')
        declarations = []
        for st in arbre.body:
            if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
                continue
            if (isinstance(st, ast.ImportFrom) and st.module == 'chrysalide_langue' and st.level == 0
                    and len(st.names) == 1 and st.names[0].name == '*' and st.names[0].asname is None):
                continue
            if (not isinstance(st, ast.Assign) or len(st.targets) != 1
                    or not isinstance(st.targets[0], ast.Name) or st.targets[0].id != 'LECON'
                    or not isinstance(st.value, ast.Call) or not isinstance(st.value.func, ast.Name)
                    or st.value.func.id != 'Lecon' or st.value.args):
                raise Refus(st, 'LECON = Lecon(champ=valeur, ...) attendu')
            declarations.append(st.value)
        if len(declarations) != 1:
            raise ValueError('Une seule LECON requise')
        for n in ast.walk(arbre):
            if isinstance(n, ast.Call):
                noms = [k.arg for k in n.keywords]
                if None in noms or len(noms) != len(set(noms)):
                    raise Refus(n, 'Arguments dupliques ou depliage interdits')
                if (isinstance(n.func, ast.Name) and n.func.id == 'Mot'
                        and (n.args or set(noms) - {'params', 'corps', 'sorte'})):
                    raise Refus(n, 'Mot : params, corps et sorte seulement')
                if isinstance(n.func, ast.Name) and n.func.id == 'Regle' and 'autres' in noms:
                    raise Refus(n, 'Une proposition ne peut injecter des metadonnees de validation dans une regle')
            if isinstance(n, ast.Dict):
                cles = [ast.literal_eval(k) for k in n.keys]
                if len(cles) != len(set(cles)):
                    raise Refus(n, 'Cles de dictionnaire dupliquees')
        call = declarations[0]
        kw = {k.arg: k.value for k in call.keywords}
        if set(kw) - CHAMPS or not {'id', 'version', 'portee', 'params', 'si', 'mecanismes'} <= set(kw):
            raise Refus(call, 'Champs inconnus ou contrat de lecon incomplet')
        corps = ast.Call(func=ast.Name(id='Programme', ctx=ast.Load()), args=[],
                        keywords=[k for k in call.keywords if k.arg in ('mots', 'regles')])
        self.corps = depuis_python('PROGRAMME = ' + ast.unparse(corps))
        self.corps.setdefault('regles', [])
        self.corps.setdefault('mots', {})
        lecteur = _Lecteur()
        lecteur.mots = set(self.corps['mots'])
        self.meta = {k: lecteur.donnee(v) for k, v in kw.items() if k not in ('si', 'mots', 'regles')}
        self.condition = lecteur.terme(kw['si'])
        self.meta.setdefault('statut', 'propose')
        self.meta.setdefault('strategie', {})
        if (not isinstance(self.meta['id'], str) or not self.meta['id']
                or type(self.meta['version']) is not int or self.meta['version'] < 1
                or self.meta['statut'] != 'propose'):
            raise ValueError('Identite/version valides et statut propose requis')
        params = self.meta['params']
        if (not isinstance(params, list) or not all(isinstance(p, str) and p.isidentifier() for p in params)
                or len(params) != len(set(params))):
            raise ValueError('Parametres distincts requis')
        if set(_parametres([self.condition, self.corps])) - set(params):
            raise ValueError('Parametre utilise non declare')
        strategie = self.meta['strategie']
        if not isinstance(strategie, dict) or set(strategie) - {'methode'}:
            raise ValueError('Strategie : methode seulement ; budget fourni par le harnais')
        if strategie and strategie.get('methode') not in METHODES:
            raise ValueError('Strategie inconnue')
        p = Programme(self.corps)  # arités des macros, récursion, portée et noms natifs
        _parcourir(self.condition, set(), p.mots, p.fonctions, set(), 'condition_lecon')
        for r in self.corps['regles']:
            lies = set()
            for nom, expr in r.get('soit', {}).items():
                _parcourir(expr, lies, p.mots, p.fonctions, set(), 'regle_lecon')
                lies.add(nom)
            for expr in [r.get('quand', True), *r.get('alors', [])]:
                _parcourir(expr, lies, p.mots, p.fonctions, set(), 'regle_lecon')
        # Vérifie aussi la portée et les noms de contrats dans le registre existant.
        ExtensionCandidate(vers_python(self.corps), self.meta['mecanismes'], self.meta['portee'])
        self.source_sha = hashlib.sha256(source.encode()).hexdigest()

    def python(self):
        champs = [f'{k}={v!r}' for k, v in self.meta.items()]
        champs += ['si=' + _terme(self.condition),
                   'mots={' + ', '.join(f'{k!r}: {_mot(v)}' for k, v in self.corps['mots'].items()) + '}',
                   'regles=[' + ', '.join(_regle(r) for r in self.corps['regles']) + ']']
        return 'LECON = Lecon(\n    ' + ',\n    '.join(champs) + '\n)\n'

    def instancier(self, chaine, valeurs):
        if set(valeurs) != set(self.meta['params']):
            raise ValueError('Tous les parametres doivent etre lies, sans ajout')
        # Les valeurs sont des données JSON, jamais des morceaux de programme.
        valeurs = json.loads(json.dumps(valeurs, allow_nan=False))
        p = copy.deepcopy(chaine.programme)
        if set(p.get('mots', {})) & set(self.corps['mots']):
            raise ValueError('Une lecon ne peut masquer un mot existant')
        anciens = {r.get('nom') for r in p.get('regles', [])}
        nouveaux = [r.get('nom') for r in self.corps['regles']]
        if len(nouveaux) != len(set(nouveaux)) or anciens & set(nouveaux):
            raise ValueError('Une lecon ne peut masquer une regle existante')
        if any(set(v) & set(valeurs) for v in p.get('niveau', {}).values()):
            raise ValueError('Parametre deja utilise dans le programme cible')
        p.setdefault('mots', {}).update(copy.deepcopy(self.corps['mots']))
        p.setdefault('regles', []).extend(copy.deepcopy(self.corps['regles']))
        p.setdefault('niveau', {}).setdefault('*', {}).update(valeurs)
        Programme(p)
        return p

    def evaluer_strategie(self, chaine, valeurs, secondes=.2):
        if not self.meta['strategie']:
            return {'statut': 'strategie_absente', 'droit_action': False}
        if not 0 < secondes <= 2:
            raise ValueError('Budget local maximal de deux secondes')
        if chaine.refute or empreinte(chaine.programme) != chaine.modele_sha:
            return {'statut': 'modele_invalide', 'droit_action': False}
        candidat = copy.deepcopy(chaine)
        candidat.programme = self.instancier(chaine, valeurs)
        candidat.modele_sha = empreinte(candidat.programme)
        candidat.version += 1
        candidat._verifie, candidat.plan = None, None
        controle, courant = candidat.rejouer()
        if courant is None or not controle['catalogue_shacl']:
            return {'statut': 'lecon_incompatible', 'controle': controle, 'droit_action': False}
        pc, scene = courant
        pi = Programme(candidat.programme)
        pi.etat = copy.deepcopy(pc.etat)
        applicable = pi.ev(self.condition, {'_scene': scene, '_action': ('',), '_niveau': 0, '_debut': False})
        if type(applicable) is not bool or not applicable:
            return {'statut': 'precondition_non_satisfaite', 'droit_action': False}
        resultat = candidat.proposer(secondes=secondes, methode=self.meta['strategie']['methode'])
        return {'statut': 'strategie_evaluee_en_simulation', 'resultat': resultat,
                'source_sha256': self.source_sha, 'snapshot_origine': chaine.signature(),
                'droit_action': False, 'transfert_reel_demontre': False}
