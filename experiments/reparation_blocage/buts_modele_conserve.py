"""Buts existants sur une dynamique admise ; aucune nouvelle induction."""
import copy
import time
from dataclasses import replace
from chaine_coherente import Chaine
from contexte_export import exporter_contextuel
from chrysalide.arc3.moteur import _candidats_buts


def actions_modele(chaine, offre):
    from chrysalide.arc3.moteur import NOMS, _clics_offerts, _lot_c
    actions = [(NOMS[a],) for a in offre if a in NOMS]
    m = chaine.perception
    if 6 in offre and getattr(m, 'th_releve', None) is not None and getattr(m, 'tr', None) is not None:
        tr = copy.copy(m.tr)
        tr.etats = list(m.tr.etats[:len(chaine.grilles)])
        tr.etats += [m.tr.etat(g) for g in chaine.grilles[len(tr.etats):]]
        for code in _clics_offerts(m.th_releve, tr):
            a = _lot_c(code, tr)
            actions.append(('MOUSE', a['row'], a['col']))
    return list(dict.fromkeys(actions))


def candidats(chaine, actions, echeance=None, but_prioritaire=None):
    vue = chaine.perception
    th = getattr(vue, 'th_releve', None)
    if th is None or getattr(vue, 'tr', None) is None or chaine.refute:
        return
    original, non = exporter_contextuel(vue, th, vue.tr.taille)
    if non or original != chaine.programme:
        return
    if chaine.rejouer()[1] is None:
        return
    tr = copy.copy(vue.tr)
    # La perception reste celle admise. Inclure aussi les observations postérieures
    # à son induction pour éliminer les buts déjà atteints sans victoire réelle.
    tr.etats = list(vue.tr.etats[:len(chaine.grilles)])
    tr.etats += [vue.tr.etat(g) for g in chaine.grilles[len(tr.etats):]]
    from extension_but_relationnel import proposer
    extensions, diagnostics = proposer(th, tr, chaine.grilles)
    couverture = None
    if extensions:
        from diagnostic_couverture_but import diagnostiquer
        couverture = diagnostiquer(th, tr, chaine.grilles)
    # Le transfert nettoie les anciens catalogues locaux, mais conserve son but.
    # Le réexaminer lui aussi, sans l'admettre s'il contredit un état observé.
    herites=[th.but] if th.but is not None else []
    theorie_buts = replace(th, buts_motifs=list(dict.fromkeys([*herites,*th.buts_motifs,*extensions])))
    buts=_candidats_buts(theorie_buts, tr)
    if but_prioritaire is not None:
        buts=sorted(buts,key=lambda b:tuple(b[:len(but_prioritaire)])!=tuple(but_prioritaire))
    else:
        import os
        if os.environ.get('CHRYS_DISTANCE_APPRISE', '0') == '1':
            from integration_innovations_31.distance.raccord_distance import classer_candidats
            buts = classer_candidats(
                buts, tr.etats, len(chaine.grilles), actif=True,
                metrique=os.environ.get('CHRYS_DISTANCE_METRIQUE', 'manhattan'))
    for but in buts:
        if echeance is not None and time.monotonic() >= echeance:
            return
        perception = copy.deepcopy(vue)
        # pour_but retire aussi des murs : ici on conserve strictement la physique.
        perception.th_releve = replace(copy.deepcopy(th), but=but)
        programme, non = exporter_contextuel(perception, perception.th_releve, tr.taille)
        if non:
            continue
        c = Chaine(perception, programme, chaine.grilles, chaine.lots, actions,
                   coups_deja_joues=chaine.coups, reserve=chaine.limite,
                   films=[e['images'] if e else None for e in chaine.films.entrees])
        controle, etat = c.rejouer()
        if etat is not None and all(controle.get(k) for k in
                ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
            c.activer_atms()
            c.diagnostic_extension_but = [d for d in diagnostics if d['candidat'] == but]
            c.diagnostic_couverture_but = couverture
            yield but, c


def chercher(chaines, actions, secondes=15, accepter=None, but_prioritaire=None, processus=0):
    debut = time.monotonic()
    echeance = debut + secondes
    portefeuille = processus > 1 and but_prioritaire is not None
    fin_premiere_passe = debut + secondes / 2 if portefeuille else echeance
    approfondir = []
    # Références aux candidats déjà construits, sans copie de leurs historiques.
    max_retenus = 16
    essais = []
    for nom, source in list(chaines.items()):
        if nom == 'p1_but_hypothese':
            continue
        if time.monotonic() >= fin_premiere_passe:
            break
        for but, c in candidats(source, actions(source) if callable(actions) else actions,
                                echeance=fin_premiere_passe, but_prioritaire=but_prioritaire):
            reste = fin_premiere_passe - time.monotonic()
            if reste <= 0:
                break
            prioritaire = (but_prioritaire is not None and
                           tuple(but[:len(but_prioritaire)]) == tuple(but_prioritaire))
            parite = None
            if prioritaire:
                from plan_parite import proposer_chaine
                parite = proposer_chaine(c)
            plan = parite if parite and parite['statut'] == 'plan_simule_valide' else (
                c.proposer(secondes=min(.25, max(0., fin_premiere_passe-time.monotonic()))))
            essai = {'source':nom, 'but':but, 'statut':plan['statut'],
                     'extension':getattr(c, 'diagnostic_extension_but', []),
                     'couverture':getattr(c, 'diagnostic_couverture_but', None)}
            if parite is not None:
                essai['parite'] = parite
            essais.append(essai)
            if plan['statut'] == 'plan_simule_valide':
                if accepter is not None and not accepter(c.plan['actions'][0]):
                    essai['statut'] = 'premier_coup_deja_essaye'
                    continue
                return c, essais
            if portefeuille and tuple(but[:len(but_prioritaire)]) == tuple(but_prioritaire):
                if len(approfondir) < max_retenus:
                    approfondir.append((nom, but, c))
                else:
                    essai['approfondissement'] = 'limite_16_candidats_retenus'
    if portefeuille and time.monotonic() >= fin_premiere_passe:
        essais.append({'statut':'premiere_passe_bornee',
                       'raison':'demi_budget_atteint_catalogue_pas_necessairement_epuise'})
    for i, (nom, but, c) in enumerate(approfondir):
        reste = echeance - time.monotonic()
        if reste <= 0:
            break
        allocation = reste / (len(approfondir) - i)
        plan = c.proposer(secondes=allocation, methode='portefeuille', processus=processus)
        essais.append({'source':nom, 'but':but, 'statut':plan['statut'],
                       'recherche':'portefeuille_herite', 'budget_s':allocation,
                       'infos':plan.get('infos', {})})
        if plan['statut'] == 'plan_simule_valide':
            if accepter is not None and not accepter(c.plan['actions'][0]):
                essais[-1]['statut'] = 'premier_coup_deja_essaye'
                continue
            return c, essais
    return None, essais
