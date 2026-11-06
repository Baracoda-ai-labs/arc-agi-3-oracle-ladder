"""Description pré-théorie des capacités suggérées par un préfixe observable.
Aucun identifiant, solution, probabilité calibrée ou état privé n'est accepté.
"""

from collections import Counter

import numpy as np
from evidence_films import Films
from ontologie_extensible import _familles, decrire_economie

from chrysalide.arc3.moteur import NOMS
from chrysalide.arc3.objets_temps import Pisteur


def information_film(avant, film, masque=(), preuve_masque=None):
    """L'inertie exige que TOUT le film soit inchangé, hors masque explicite étayé."""
    if masque and not preuve_masque:
        raise ValueError("Masque sans provenance explicite")
    avant = np.asarray(avant)
    frames = np.asarray(film)
    if frames.ndim != 3 or not len(frames) or frames.shape[1:] != avant.shape:
        raise ValueError("Film vide ou incompatible")
    visible = np.ones(avant.shape, dtype=bool)
    for y, x in masque:
        if not (0 <= y < avant.shape[0] and 0 <= x < avant.shape[1]):
            raise ValueError("Masque hors image")
        visible[y, x] = False
    diffs = [int(np.count_nonzero((f != avant) & visible)) for f in frames]
    return {
        "inerte": not any(diffs),
        "animation_transitoire": bool(any(diffs) and not diffs[-1]),
        "pixels_differents_par_frame": diffs,
        "masque": list(map(list, masque)),
        "preuve_masque": preuve_masque,
        "portee": "information visuelle, pas utilité ni absence de coût",
    }


def _objets(pistes, image):
    result = {}
    for ident, cases in pistes.items():
        if not cases:
            continue
        ys, xs = zip(*cases)
        y, x = min(ys), min(xs)
        dessin = tuple(sorted((int(yy - y), int(xx - x), int(image[yy, xx])) for yy, xx in cases))
        bord = min(ys) == 0 or min(xs) == 0 or max(ys) == image.shape[0] - 1 or max(xs) == image.shape[1] - 1
        result[ident] = {"dessin": dessin, "origine": (int(y), int(x)), "aire": len(cases), "bord": bord}
    return result


def classifier(images, actions, films, masque=(), preuve_masque=None):
    if len(images) != len(actions) + 1 or len(films) != len(actions):
        raise ValueError("Préfixe non aligné")
    if masque and not preuve_masque:
        raise ValueError("Masque non étayé")
    gs = [np.asarray(g).copy() for g in images]
    if not gs:
        raise ValueError("Image initiale absente")
    fond = Counter(gs[0].ravel().tolist()).most_common(1)[0][0]
    for g in gs:
        for y, x in masque:
            g[y, x] = fond
    suivi = Pisteur(revisable=True, chevauche=True)
    precedent = _objets(suivi.observer(gs[0]), gs[0])
    preuves = Films()
    trans = []
    transfos = []
    retours = []
    informations = []
    for k, (avant, apres, film) in enumerate(zip(images, images[1:], films)):
        if not len(film) or not np.array_equal(np.asarray(film)[-1], apres):
            raise ValueError("Film final non aligné")
        preuves.ajouter(avant, film)
        informations.append({"coup": k + 1, **information_film(avant, film, masque, preuve_masque)})
        actuel = _objets(suivi.observer(gs[k + 1]), gs[k + 1])
        for ident in precedent.keys() & actuel.keys():
            a, b = precedent[ident], actuel[ident]
            if a["dessin"] == b["dessin"] and a["origine"] != b["origine"]:
                trans.append(
                    {
                        "coup": k + 1,
                        "piste": int(ident),
                        "deplacement_yx": [v - u for u, v in zip(a["origine"], b["origine"])],
                        "identite": "hypothese_pisteur",
                        "region_bord": a["bord"] or b["bord"],
                    }
                )
            elif a["dessin"] != b["dessin"]:
                transfos.append(
                    {
                        "coup": k + 1,
                        "piste": int(ident),
                        "aire_avant": a["aire"],
                        "aire_apres": b["aire"],
                        "quart_de_tour_non_suffisant": a["aire"] != b["aire"],
                        "identite": "hypothese_pisteur_chevauchement",
                        "region_bord": a["bord"] or b["bord"],
                        "alternatives": ["orientation_rasterisee", "changement_motif", "occultation", "fusion_scission"],
                    }
                )
        if k >= 1 and not np.array_equal(gs[k], gs[k + 1]) and np.array_equal(gs[k - 1], gs[k + 1]):
            retours.append({"coups": [k, k + 1], "portee": "retour visuel observé, réversibilité causale non prouvée"})
        precedent = actuel
    atlas_preuves=[]
    try:
        from perception_silhouette_atlas import atlas
        _nav,_positions,_motifs,atlas_preuves=atlas(images,actions)
        for preuve in atlas_preuves:
            if any(preuve['deplacement_xy']):
                trans.append({'coup':preuve['coup'],'deplacement_yx':list(reversed(preuve['deplacement_xy'])),
                    'region_bord':False,'identite':'atlas_silhouette_provisoire',
                    'miroir_horizontal':preuve['miroir_horizontal']})
    except (ValueError,IndexError,KeyError,TypeError):
        pass
    noms = sorted({("MOUSE" if isinstance(a, list) else NOMS.get(a, str(a))) for a in actions})
    familles = _familles()
    signaux = familles.signaux_depuis_objets([], noms)
    # Les scores de cette mémoire ne sont pas des probabilités : conserver seulement les noms.
    memoire = [nom for nom, _score in familles.reconnaitre(signaux)]
    mouvement = any(not x["region_bord"] for x in trans)
    transformation = any(not x["region_bord"] for x in transfos)
    capacites = ["silhouette_atlas_navigation"] if atlas_preuves else []
    if mouvement:
        capacites.append("objets_translation_identites")
    if transformation:
        capacites.append("pisteur_chevauchement_atlas_motifs")
    if any(x["animation_transitoire"] for x in informations):
        capacites.append("evenements_frames_intermediaires")
    return {
        "statut": "description_pre_theorie",
        "economie_du_jeu": decrire_economie(),
        "coups_observes": len(actions),
        "canaux_observes": noms,
        "translation": {
            "statut": "non_couverte_par_translation_seule"
            if transformation
            else "transitions_compatibles"
            if mouvement
            else "inconnue",
            "preuves": trans,
        },
        "transformation_motif": {"statut": "candidate" if transformation else "non_etablie", "preuves": transfos},
        "retours_visuels": retours,
        "films": informations,
        "signatures_films": preuves.signatures(),
        "memoire_familles_prior_seulement": memoire,
        "capacites_a_essayer": capacites,
        "atlas_silhouette": atlas_preuves,
        "inconnues": ["identite_causale", "regles_interaction", "but", "issues", "dynamique_non_observee"],
        "priorite_modeles_deja_admis": True,
        "routage_exclusif": False,
        "droit_action": False,
        "modele_admis": False,
        "preuve_masque": preuve_masque,
    }
