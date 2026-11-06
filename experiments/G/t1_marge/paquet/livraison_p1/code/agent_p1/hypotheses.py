"""Représentation des hypothèses : contrat causal typé, exécutable et vérifiable.

Un mécanisme = entité + déclencheur + préconditions + effet + sémantique temporelle + portée.
Le programme est un petit dictionnaire typé (pas de code arbitraire) interprété par `simulation.py`
et par `monde.ModeleEtendu` (même sémantique dans les deux).
"""
from dataclasses import dataclass, field, asdict
import hashlib, json, math

# Vocabulaire typé (domaines finis). Toute valeur hors domaine est refusée par `valider`.
DECLENCHEURS = ('jamais', 'coup_joueur', 'coup_effectif', 'tout_coup')
EFFETS = ('immobile', 'miroir', 'route_latente', 'couloir', 'poursuite', 'fuite')
REINIT = (None, 'action5')
DESTRUCTION = (None, 'porte_fermee', 'occultation_porte', 'bloque_par_porte', 'bloque_et_ecrase')
FIN_COULOIR = ('arret', 'demi_tour')
FIN_ROUTE = ('reste', 'disparait', 'couloir')
TRANSFOS = ('id', 'flipx', 'flipy', 'rot90', 'rot180', 'rot270', 'transpose', 'antitranspose')

# Coût descriptif (bits) de chaque choix structurel, relatif au mécanisme de base « décor immobile ».
# Les familles existantes (v4/BIBLIOTHEQUE) coûtent moins qu'un opérateur nouveau : c'est le prior explicite.
COUT = {
    'declencheur': {'jamais': 0, 'coup_joueur': 1, 'coup_effectif': 2, 'tout_coup': 1},
    'effet': {'immobile': 0, 'miroir': 3, 'route_latente': 4, 'couloir': 4, 'poursuite': 3, 'fuite': 3},
    'reinit': {None: 0, 'action5': 2},
    'destruction': {None: 0, 'porte_fermee': 2, 'occultation_porte': 3, 'bloque_par_porte': 2, 'bloque_et_ecrase': 3},
    'fin_couloir': {'arret': 0, 'demi_tour': 1},
    'fin_route': {'reste': 1, 'disparait': 1, 'couloir': 3},
    'delai': 2, 'transfo': 3, 'portee_dalles': 2, 'pas_route': 2,
}


def programme(declencheur='jamais', effet='immobile', reinit=None, delai=0, transfo='id', destruction=None,
              fin_route='reste', route=None, portee_dalles=None, fin_couloir='arret'):
    return dict(fin_couloir=fin_couloir, declencheur=declencheur, effet=effet, reinit=reinit, delai=delai, transfo=transfo,
                destruction=destruction, fin_route=fin_route, route=tuple(map(tuple, route)) if route else None,
                portee_dalles=portee_dalles)


def valider(p):
    assert p['declencheur'] in DECLENCHEURS and p['effet'] in EFFETS and p['reinit'] in REINIT
    assert p['destruction'] in DESTRUCTION and p['fin_route'] in FIN_ROUTE and p['transfo'] in TRANSFOS
    assert p.get('fin_couloir', 'arret') in FIN_COULOIR
    assert p['delai'] in (0, 1) and p['portee_dalles'] in (None, True, False)
    if p['effet'] == 'route_latente':
        assert p['route'] and len(p['route']) >= 1
    return True


def complexite(p):
    c = COUT['declencheur'][p['declencheur']] + COUT['effet'][p['effet']] + COUT['reinit'][p['reinit']]
    c += COUT['destruction'][p['destruction']] + (COUT['delai'] if p['delai'] else 0)
    if p['effet'] == 'miroir':
        c += COUT['transfo']
    if p['effet'] == 'route_latente':
        c += COUT['pas_route'] * (len(p['route']) - 1) + COUT['fin_route'][p['fin_route']]
    if p['portee_dalles'] is not None:
        c += COUT['portee_dalles']
    if p['effet'] in ('couloir', 'route_latente'):
        c += COUT['fin_couloir'][p.get('fin_couloir', 'arret')]
    return c


def empreinte(p):
    return hashlib.sha1(json.dumps(p, sort_keys=True, default=str).encode()).hexdigest()[:10]


# Opérateurs déjà présents dans la bibliothèque initiale (v4 + BIBLIOTHEQUE.md, côté exécutable v4) :
# un programme qui n'utilise que ceux-ci n'est PAS une invention structurelle.
BIBLIOTHEQUE_INITIALE = {
    'effet': {'immobile'},                 # tout objet non revendiqué = décor (théorie implicite v4)
    'objet_autonome': False,               # aucun mobile non contrôlé hors fantômes enregistrés par le joueur
    'reinit_objet': False,                 # ACTION5 ne concerne que joueur + routes enregistrées
    'occupant_non_joueur_sur_dalle': False,  # seuls joueur et fantômes enregistrés occupent les dalles
}


def nouveaute(p):
    """Liste des opérateurs structurels du programme absents de la bibliothèque initiale."""
    n = []
    if p['effet'] != 'immobile':
        n.append(f"objet_autonome:{p['effet']}")
    if p['reinit']:
        n.append('portee_reinit_etendue_aux_objets')
    if p['destruction'] in ('porte_fermee', 'bloque_par_porte', 'bloque_et_ecrase'):
        n.append(f"composition:{p['destruction']}(famille destruction/porte)")
    if p['portee_dalles']:
        n.append('occupant_autonome_sur_dalle(declencheur_distant)')
    return n


@dataclass
class Hypothese:
    id: str
    version: int
    objet: str
    programme: dict
    predicats: list = field(default_factory=list)
    mutations: list = field(default_factory=list)       # opérateurs appliqués depuis la base
    parent: str = 'base:decor_immobile'
    explique: list = field(default_factory=list)        # pas t expliqués
    contredit: list = field(default_factory=list)       # (t, catégorie, prédit, observé)
    non_predit: list = field(default_factory=list)      # pas sans prédiction (pouvoir prédictif nul)
    cout: float = 0.0
    score: float = None
    statut: str = 'candidate'                           # candidate / rejetee / survivante / validee
    refutable_par: list = field(default_factory=list)   # expériences qui la réfuteraient
    preuve_rejet: dict = None

    def __post_init__(self):
        valider(self.programme)
        self.cout = complexite(self.programme)
        if not self.predicats:
            p = self.programme
            self.predicats = [f"declencheur({p['declencheur']})", f"effet({p['effet']})",
                              f"reinit({p['reinit']})", f"destruction({p['destruction']})"]
            if p['delai']:
                self.predicats.append('delai(1)')
            if p['effet'] == 'miroir':
                self.predicats.append(f"transfo({p['transfo']})")
            if p['effet'] == 'route_latente':
                self.predicats.append(f"route({len(p['route'])} poses, fin={p['fin_route']})")
            if p['effet'] in ('couloir', 'route_latente'):
                self.predicats.append(f"fin_couloir({p.get('fin_couloir', 'arret')})")
            if p['portee_dalles'] is not None:
                self.predicats.append(f"occupe_dalles({p['portee_dalles']})")

    def resume(self):
        d = asdict(self)
        d['programme'] = {k: v for k, v in self.programme.items() if v not in (None, 0, 'id') or k == 'effet'}
        d['nouveaute'] = nouveaute(self.programme)
        d['contredit'] = self.contredit[:5]; d['n_contredit'] = len(self.contredit)
        d['explique'] = len(self.explique); d['non_predit'] = len(self.non_predit)
        return d
