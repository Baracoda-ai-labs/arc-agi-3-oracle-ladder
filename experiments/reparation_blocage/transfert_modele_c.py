"""Réaffectation provisoire d'une théorie C à une image de nouveau niveau."""
import copy

import numpy as np

from chaine_coherente import Chaine
from chrysalide.arc3.moteur import MoteurC
from chrysalide.arc3.logique.faits import Trajectoire, couleurs_diagonales, cellules
from contexte_export import exporter_contextuel


def reaffecter(source, image, actions, coups_deja_joues=0, reserve=150):
    """Retourne (chaîne locale, diagnostic), sans induction de loi ni ancien état."""
    vue = source.perception
    ancien = getattr(vue, 'tr', None)
    origine = getattr(vue, 'th_releve', None)
    if ancien is None or origine is None or source.refute:
        raise ValueError('Source C absente ou réfutée')
    programme, non = exporter_contextuel(vue, origine, ancien.taille)
    if non or programme != source.programme or source.rejouer()[1] is None:
        raise ValueError('Source non synchronisée ou non admissible')
    g = np.asarray(image).copy()
    meme_format = g.shape == np.asarray(source.grilles[0]).shape
    tr = Trajectoire([g.tolist()], [], ech=(ancien.s, ancien.ox, ancien.oy),
        atomiques=ancien.atomiques, formes_heritees=copy.deepcopy(ancien.formes),
        exclues_heritees=ancien.exclues if meme_format else frozenset(),
        sans_fond=ancien.fond == -1)
    # Ces correspondances sont perceptives ; aucune position passée n'est copiée.
    for nom in ('marqueur', 'marqueurs', 'details', 'tuiles'):
        setattr(tr, nom, copy.deepcopy(getattr(ancien, nom)))
    # L'induction lit la zone de clic sur la trajectoire ; l'export la lit sur
    # la théorie admise. Conserver le même contrat, sans anciennes positions.
    tr.hitbox_formes = copy.deepcopy(getattr(origine, 'hitbox_formes', frozenset()))
    tr.diagonales = frozenset(tr.diagonales) | frozenset(ancien.diagonales)
    if origine.porteur:
        tr.diagonales |= couleurs_diagonales(tr.cases[0], tr.fond, tr.exclues)
    tr._carte = {}
    tr._bruts = []
    tr.etats = [tr.etat(g)]
    tr._bruts = list(tr.etats)
    th = copy.deepcopy(origine)
    defauts = type(th)()
    inconnus = []
    hotes_sous_marqueur = []
    hotes_candidats = []
    if th.porteur:
        marqueurs = [o for o in tr.etats[0] if o[0] == th.porteur[0]]
        if marqueurs:
            palettes = {k for k, _ in th.peint_contact}
            pieces = [o for o in tr.etats[0] if len(o[1]) > 1 and o[0] < 512
                      and o[0] not in th.solides and o[0] not in palettes]
            hotes_sous_marqueur = sorted({o[0] for o in pieces
                if any(cellules(o) & cellules(m) for m in marqueurs)})
            hotes_candidats = sorted({o[0] for o in pieces} - set(hotes_sous_marqueur))
            th.hotes = frozenset((o[0], o[1]) for o in pieces)
        else:
            inconnus.append('marqueur_porteur_non_reaffecte')
    # Garder les lois indépendantes, laisser leurs paramètres locaux non résolus.
    for nom in ('teleports_cases', 'derives', 'selection', 'retour', 'fantome',
                'selection_clic', 'marqueur_sel', 'sans_effet', 'portes_cases',
                'tenue_cases', 'jauge', 'enroule', 'ancres_bornees', '_dalles',
                'clic_configs'):
        if getattr(th, nom, None):
            inconnus.append(nom)
            setattr(th, nom, copy.deepcopy(getattr(defauts, nom)))
    th.hors_jeu = tr.exclues
    th.masque_projection = origine.masque_projection & tr.exclues if meme_format else frozenset()
    th.buts_compatibles = []
    th.buts_motifs = []
    th.obligations = {}
    but_reaffecte = False
    if th.but and th.but[0] == 'marques':
        from chrysalide.arc3.logique.induction import ajouter_but_marques
        ajouter_but_marques(th, [(tr, None, None)])
        if th.buts_motifs:
            # Même contrat (couleur ou simple couverture), nouvelles positions seules.
            th.but = ('marques', th.buts_motifs[-1][1], *origine.but[2:])
            th.buts_motifs = [th.but]
            but_reaffecte = True
        else:
            inconnus.append('but_marques_non_reaffecte')
            th.but = None
    elif th.but and th.but[0] in ('copie', 'emboite'):
        inconnus.append('but_coordonnees')
        th.but = None
    if getattr(ancien, '_carte', None):
        inconnus.append('classes_comportement_instance')
    m = MoteurC()
    m.contexte_export = copy.deepcopy(getattr(vue, 'contexte_export', {}))
    m.tr, m.th_releve, m._couches = tr, th, th.couches()
    programme, non = exporter_contextuel(m, th, tr.taille)
    if non:
        raise ValueError('Théorie transférée non exportable : ' + repr(non))
    c = Chaine(m, programme, [g.tolist()], [], actions,
        coups_deja_joues=coups_deja_joues, reserve=reserve,
        origine='transfert_C_provisoire', films=[])
    controle, etat = c.rejouer()
    if etat is None or not all(controle.get(k) for k in
            ('catalogue_shacl', 'traduction_python', 'rejeu', 'compilation_fidele')):
        raise ValueError('Instance transférée non admissible : ' + repr(controle))
    if not np.array_equal(c.perception.rendu(etat[1]), c.perception.vue(g)):
        raise ValueError('Perception transférée ne restitue pas la nouvelle image')
    c.activer_atms()
    diag = {'famille': 'moteur_c', 'promotion_durable': False,
        'regles_reapprises': 0, 'transitions_nouveau_niveau': 0,
        'mouvements_conserves': th.moves == origine.moves,
        'but_source': origine.but, 'but_instance': th.but,
        'but_reaffecte_depuis_nouvelle_image': but_reaffecte,
        'diagonales_instance': sorted(tr.diagonales),
        'hotes_sous_marqueur': hotes_sous_marqueur,
        'autres_hotes_candidats_a_confirmer': hotes_candidats,
        'parametres_non_reaffectes': inconnus,
        'hypotheses': ['classes_et_echelle_reutilisables', 'masque_interface_reutilisable',
                       'regles_et_but_encore_a_verifier_sur_nouveau_niveau'],
        'controle': controle, 'source_signature': source.signature()}
    c.transfert_provisoire = copy.deepcopy(diag)
    return c, diag
