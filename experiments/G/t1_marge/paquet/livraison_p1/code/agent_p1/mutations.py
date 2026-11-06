"""Génération de réparations structurelles typées à partir d'une contradiction localisée.

Base : la théorie v4 implicite (objet non revendiqué = décor immobile). Huit opérateurs (brief §4.2) :
 M1 paramètre/relation spatiale  : effet miroir du coup joueur, 8 transformations (famille « jumeau »)
 M2 précondition                 : déclencheur conditionné à un déplacement effectif du joueur
 M3 type de déclencheur          : coup joueur / coup effectif / tout coup (temps)
 M4 local → distant              : poursuite / fuite d'un objet distant (le joueur)
 M5 état persistant              : route latente avec pointeur mémoire (induite des données d'invention)
 M6 effet différé                : délai d'un coup
 M7 périmètre d'un effet         : ACTION5 réinitialise aussi l'objet ; l'objet occupe les dalles
 M8 composition                  : mobile suivant un couloir (rail) ; destruction par porte fermée ;
                                   occultation par la porte (rendu ≠ état) ; porte = mur pour l'objet
Les opérateurs ne sont proposés que si le contexte causal les rend pertinents (gating), ce qui réduit l'espace.
"""
from itertools import product
from .hypotheses import Hypothese, programme, TRANSFOS
from .simulation import induire_route


def contexte_causal(objet, contradictions, lignes):
    cs = [c for c in contradictions if c['objet'] == objet['id']]
    types = {c['type'] for c in cs}
    retour_origine = any(c['type'] == 'deplacement' and tuple(c['observe']) == tuple(objet['pos0'])
                         and c['action'] == 5 for c in cs)
    actions = sorted({c['action'] for c in cs})
    immobile_sur_coup = [L['t'] for L in lignes if L['action'] in (1, 2, 3, 4)
                         and L['objets'][objet['id']][0] == L['objets'][objet['id']][1]
                         and L['objets'][objet['id']][0] is not None]
    disparition_porte = [c for c in cs if c['type'] == 'disparition']
    return dict(objet=objet['id'], types=sorted(types), retour_origine=retour_origine, actions=actions,
                n=len(cs), premiers=[c['t'] for c in cs[:5]], immobile_sur_coup=immobile_sur_coup[:5],
                disparition=bool(disparition_porte))


def generer(objet, ctx, lignes_invention):
    """Rend la liste d'hypothèses candidates (non filtrées) avec la trace des mutations appliquées."""
    out = []
    if 'deplacement' not in ctx['types'] and not ctx['disparition']:
        return out
    route, inc = induire_route(objet, lignes_invention)
    effets = [('miroir', t, ['M1:relation_miroir(%s)' % t]) for t in TRANSFOS]
    effets += [('poursuite', 'id', ['M4:relation_distante(poursuite)']),
               ('fuite', 'id', ['M4:relation_distante(fuite)']),
               ('couloir', 'id', ['M8:composition(autonome+rail)'])]
    fins = ['reste', 'couloir'] + (['disparait'] if ctx['disparition'] else [])
    if len(route) >= 2:
        effets += [('route_latente', 'id', ['M5:etat_persistant(route,pointeur)'])]
    declencheurs = [('coup_joueur', []), ('coup_effectif', ['M2:precondition(deplacement_effectif)']),
                    ('tout_coup', ['M3:declencheur_temporel'])]
    reinits = [(None, [])] + ([('action5', ['M7:portee(reinit_ACTION5->objet)'])] if ctx['retour_origine']
                              or 5 in ctx['actions'] else [])
    delais = [(0, []), (1, ['M6:effet_differe(1)'])]
    destr = [(None, [])]
    if ctx['disparition']:
        destr += [('porte_fermee', ['M8:composition(destruction_par_porte)']),
                  ('occultation_porte', ['M8:rendu_different(occulte_sous_porte)']),
                  ('bloque_par_porte', ['M1:relation(porte=mur_pour_objet)'])]
    k = 0
    for (eff, tr, m1), (dec, m2), (ri, m3), (de, m4), (ds, m5) in product(effets, declencheurs, reinits, delais, destr):
        for fin in (fins if eff == 'route_latente' else ['reste']):
            prog = programme(declencheur=dec, effet=eff, reinit=ri, delai=de, transfo=tr, destruction=ds,
                             fin_route=fin, route=route if eff == 'route_latente' else None)
            muts = m1 + m2 + m3 + m4 + m5 + ([f'fin_route({fin})'] if eff == 'route_latente' else [])
            out.append(Hypothese(id=f"{objet['id']}-H{k:04d}", version=1, objet=objet['id'], programme=prog,
                                 mutations=muts))
            k += 1
    out_inc = inc
    for h in out:
        if h.programme['effet'] == 'route_latente':
            h.preuve_rejet = None
            h.__dict__['incoherence_route'] = out_inc
    return out


def generer_parametres_seuls(objet, ctx, lignes_invention):
    """Ablation « recherche de paramètres uniquement » : on n'autorise que les familles existantes
    (décor immobile, miroir du contrôlé = paramètre de la famille déplacement) et leurs paramètres."""
    out = []
    for k, (t, dec) in enumerate(product(TRANSFOS, ('coup_joueur', 'coup_effectif'))):
        out.append(Hypothese(id=f"{objet['id']}-P{k:03d}", version=1, objet=objet['id'],
                             programme=programme(declencheur=dec, effet='miroir', transfo=t),
                             mutations=[f'param:transfo={t}', f'param:declencheur={dec}']))
    out.append(Hypothese(id=f"{objet['id']}-P_base", version=1, objet=objet['id'], programme=programme(),
                         mutations=[]))
    return out
