"""Superviseur de recherche + mémoire persistante des hypothèses (ajouts du coordinateur, inspirés d'AVO).

Mémoire : chaque hypothèse évaluée est enregistrée (empreinte du programme, statut, preuve de rejet, filiation :
mutations depuis la base, version d'invention, parent). Dans un même contexte (jeu, niveau, objet), une hypothèse
réfutée n'est JAMAIS retestée : les données ne font que croître, la preuve reste valable (elle est recopiée).
Hors de son contexte, une réfutation n'est qu'un a priori (+2 bits), jamais une élimination.

Superviseur : les réparations sont groupées en familles de modification structurelle, par niveau d'expressivité
(avis expert §2) : 1 paramètre/relation (miroir), 2 dépendance distante (poursuite/fuite) et composition
(mobile sur couloir), 3 état persistant (route latente). Chaque famille est évaluée par complexité croissante ;
après N_CONSEC réfutations successives SANS PROGRÈS (aucune ne réduit le nombre d'erreurs du meilleur
candidat de la famille), le superviseur l'abandonne et change de TYPE de
modification au lieu de multiplier les variantes. Il s'arrête d'escalader dès qu'un niveau a des survivantes
(en évaluant aussi le niveau suivant pour garder des concurrentes). Une famille dont les survivantes ont été
réfutées prospectivement deux versions de suite est rétrogradée en fin de file (stagnation).
"""
import json
from itertools import product
from pathlib import Path
from .hypotheses import Hypothese, programme, TRANSFOS, empreinte
from .simulation import induire_route
from .classement import evaluer

N_CONSEC = 40

FAMILLES = [  # (nom, niveau, mutation principale)
    ('parametre_miroir', 1, 'M1'),
    ('distant_poursuite', 2, 'M4'),
    ('composition_couloir', 2, 'M8'),
    ('persistant_route', 3, 'M5'),
]


class Memoire:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.d = json.loads(self.path.read_text()) if self.path and self.path.exists() else {}

    def cle(self, contexte, prog):
        return f"{contexte}|{empreinte(prog)}"

    def refutee(self, contexte, prog):
        r = self.d.get(self.cle(contexte, prog))
        return r if r and r['statut'] == 'rejetee' else None

    def refutee_ailleurs(self, contexte, prog):
        e = empreinte(prog)
        return [k for k, r in self.d.items() if k.endswith('|' + e) and not k.startswith(contexte + '|')
                and r['statut'] == 'rejetee']

    def enregistrer(self, contexte, h, version, famille):
        k = self.cle(contexte, h.programme)
        old = self.d.get(k)
        self.d[k] = dict(id=h.id, statut=h.statut, preuve=h.preuve_rejet, mutations=h.mutations, famille=famille,
                         version=version, parent=h.parent, score=h.score,
                         premiere_version=old['premiere_version'] if old else version)

    def sauver(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.d, indent=0, default=str, ensure_ascii=False))


def familles_candidates(objet, ctx, lignes_invention):
    """Dict famille -> hypothèses (non évaluées), triées par complexité croissante."""
    route, inc = induire_route(objet, lignes_invention)
    declencheurs = [('coup_joueur', []), ('coup_effectif', ['M2:precondition(deplacement_effectif)']),
                    ('tout_coup', ['M3:declencheur_temporel'])]
    reinits = [(None, []), ('action5', ['M7:portee(reinit_ACTION5->objet)'])]
    delais = [(0, []), (1, ['M6:effet_differe(1)'])]
    # « porte = mur pour l'objet » est une relation (M1) toujours applicable s'il existe des portes ;
    # les variantes de destruction/occultation ne sont proposées qu'après une disparition observée.
    destr = [(None, []), ('bloque_par_porte', ['M1:relation(porte=mur_pour_objet)'])]
    if ctx['disparition']:
        destr += [('porte_fermee', ['M8:composition(destruction_par_porte)']),
                  ('occultation_porte', ['M8:rendu_different(occulte_sous_porte)']),
                  ('bloque_et_ecrase', ['M8:composition(porte=mur+ecrasement)'])]
    effets = {
        'parametre_miroir': [(dict(effet='miroir', transfo=t), [f'M1:relation_miroir({t})']) for t in TRANSFOS],
        'distant_poursuite': [(dict(effet='poursuite'), ['M4:relation_distante(poursuite)']),
                              (dict(effet='fuite'), ['M4:relation_distante(fuite)'])],
        'composition_couloir': [(dict(effet='couloir', fin_couloir=f), ['M8:composition(autonome+rail)', f'M1:fin_couloir({f})'])
                                for f in ('arret', 'demi_tour')],
        'persistant_route': ([(dict(effet='route_latente', route=route, fin_route=fr, fin_couloir=fc),
                               ['M5:etat_persistant(route,pointeur)', f'fin_route({fr})', f'M1:fin_couloir({fc})'])
                              for fr in (['reste', 'couloir'] + (['disparait'] if ctx['disparition'] else []))
                              for fc in (('arret', 'demi_tour') if fr == 'couloir' else ('arret',))]
                             if len(route) >= 2 else []),
    }
    out = {}
    for fam, liste in effets.items():
        hs = []
        for (eff, m1), (dec, m2), (ri, m3), (de, m4), (ds, m5) in product(liste, declencheurs, reinits, delais, destr):
            prog = programme(declencheur=dec, reinit=ri, delai=de, destruction=ds, **eff)
            h = Hypothese(id='', version=1, objet=objet['id'], programme=prog, mutations=m1 + m2 + m3 + m4 + m5,
                          parent=f'base:decor_immobile/{fam}')
            if fam == 'persistant_route':
                h.__dict__['incoherence_route'] = inc
            hs.append(h)
        hs.sort(key=lambda h: h.cout)
        for k, h in enumerate(hs):
            h.id = f"{objet['id']}-{fam[:4]}{k:03d}"
        out[fam] = hs
    return out


def superviser(objet, ctx, lignes, model, t_invention, memoire, contexte, version, portes_initiales=(),
               journal=None, retrogradees=(), n_consec=N_CONSEC, sans_superviseur=False):
    """Évalue les familles sous contrôle du superviseur. Rend (hypothèses évaluées, rapport)."""
    fams = familles_candidates(objet, ctx, [L for L in lignes if L['t'] <= t_invention])
    ordre = sorted(FAMILLES, key=lambda f: (f[0] in retrogradees, f[1]))
    evaluees = []; rapport = dict(familles=[], sautees_memoire=0, niveau_survivantes=None)
    for nom, niveau, mp in ordre:
        if not sans_superviseur and rapport['niveau_survivantes'] is not None and niveau > rapport['niveau_survivantes'] + 1:
            rapport['familles'].append(dict(famille=nom, niveau=niveau, statut='non_exploree_progres_suffisant'))
            continue
        consec = 0; testees = 0; surv = 0; abandon = False; saut = 0; meilleur = 10 ** 9
        for h in fams[nom]:
            r = memoire.refutee(contexte, h.programme) if memoire else None
            if r:
                h.statut = 'rejetee'; h.preuve_rejet = dict(r['preuve'] or {}, memoire=True, depuis_version=r['premiere_version'])
                saut += 1; evaluees.append(h); continue
            ail = memoire.refutee_ailleurs(contexte, h.programme) if memoire else []
            evaluer([h], objet, lignes, model, t_invention, portes_initiales=portes_initiales)
            if ail:
                h.score += 0.2; h.__dict__['refutee_ailleurs'] = ail[:3]
            h.version = version; evaluees.append(h); testees += 1
            if memoire:
                memoire.enregistrer(contexte, h, version, nom)
            nerr = len(h.contredit)
            if h.statut == 'rejetee':
                consec = 0 if nerr < meilleur else consec + 1   # progrès = moins d'erreurs que le meilleur de la famille
                meilleur = min(meilleur, nerr)
                if not sans_superviseur and consec >= n_consec and surv == 0:
                    abandon = True; break
            else:
                consec = 0; surv += 1
        rapport['sautees_memoire'] += saut
        reste = len(fams[nom]) - testees - saut
        rapport['familles'].append(dict(famille=nom, niveau=niveau, mutation=mp, testees=testees, survivantes=surv,
                                        sautees_memoire=saut, abandon_apres_refutations=abandon, non_testees=reste))
        if journal and abandon:
            journal.ecrire('superviseur', objet=objet['id'], version=version, famille=nom,
                           decision='changement_de_type_de_modification', refutations_successives=consec,
                           non_testees=reste)
        if surv and rapport['niveau_survivantes'] is None:
            rapport['niveau_survivantes'] = niveau
    if memoire:
        memoire.sauver()
    return evaluees, rapport
