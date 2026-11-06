"""Raccord pré-théorie sans état propre : Dossier → question et sonde existante."""

import copy

import numpy as np
from classification_prefixe import classifier
from experience_selection_visuelle import proposer as proposer_selection_visuelle
from jauges_observees import jauges_validees
from roles_observes import PerceptionRoles

from chrysalide.arc3.exploration import Explorateur
from chrysalide.arc3.moteur import NOMS


def description(dossier, modeles=()):
    masque, preuves = jauges_validees(dossier.images, dossier.actions)
    preuve = (
        {
            "origine": "jauges_validees",
            "portee": "hypothese conditionnelle de coût, pas décor sans effet",
            "coups_prefixe": len(dossier.actions),
            "validations": preuves,
        }
        if masque
        else None
    )
    fiche = classifier(dossier.images, dossier.actions, dossier.films, sorted(masque), preuve)
    preselection = any(
        isinstance(getattr(c.perception, "base", c.perception), PerceptionRoles) and not c.refute
        for c in (modeles.values() if hasattr(modeles, "values") else [])
    )
    selection_bornee = 6 in dossier.offre and any(a in (1, 2, 3, 4) for a in dossier.offre) and not preselection
    essayees = {6 if isinstance(a, list) else a for a in dossier.actions}
    inconnues = [a for a in dossier.offre if a not in essayees]
    if not dossier.actions:
        question = "Quels effets ont les commandes offertes sur les éléments visibles ?"
    elif inconnues:
        question = "Que fait une commande encore non essayée dans cette observation ?"
    elif modeles:
        question = "La transition du plan et son issue concordent-elles avec l’observation ?"
    else:
        question = "Quelle capacité explique le changement observé, sans supposer le but ?"
    return {
        "classification": fiche,
        "prerequis_selection": {
            "perception_roles_admise": preselection,
            "clic_differe": selection_bornee,
            "raison": "premier clic interprétable requiert une perception de déplacement compatible",
        },
        "question_manquante": question,
        "questions_couvertes": {
            "commandes_essayees": sorted(essayees),
            "commandes_non_essayees": inconnues,
            "perception": "compatible_sur_prefixe" if modeles else "inconnue",
            "regles": "compatibles_sur_prefixe" if modeles else "inconnues",
            "but": "hypothese_non_prouvee" if modeles else "inconnu",
        },
        "hud": sorted(map(list, masque)),
        "preuve_masque": preuve,
        "prefixe_sha256": dossier.signature(),
    }


def proposer(dossier, contexte, modeles=()):
    """Priorité de groupes déjà implémentée dans Explorateur ; aucun nouvel inducteur."""
    if not dossier.offre or dossier.reserve <= 0:
        return None
    masque = contexte["hud"]

    def propre(image):
        a = np.array(image, copy=True)
        for y, x in masque:
            a[y, x] = 0
        return a

    def action_dict(a):
        return {"action": "MOUSE", "row": a[2], "col": a[1]} if isinstance(a, list) else {"action": NOMS[a]}

    gs = [propre(g) for g in dossier.images]
    if 6 in dossier.offre and contexte["prerequis_selection"]["perception_roles_admise"]:
        for c in modeles.values() if hasattr(modeles, "values") else []:
            vue = getattr(c.perception, "base", c.perception)
            if not isinstance(vue, PerceptionRoles):
                continue
            try:
                exp = proposer_selection_visuelle(vue, dossier.images[-1])
            except (ValueError, KeyError, TypeError, IndexError, RuntimeError):
                continue
            action = exp["actions"][0]
            # Les expériences déjà faites dans ce rendu restent des preuves, pas des sondes à répéter.
            if any(a == action and np.array_equal(propre(image), gs[-1]) for a, image in zip(dossier.actions, dossier.images)):
                continue
            return {
                **exp,
                "hud": contexte["hud"],
                "preuve_masque": copy.deepcopy(contexte["preuve_masque"]),
                "type": "selection_visuelle_existante",
                "proposeur": "experience_selection_visuelle",
                "cout_actions": 1,
                "but": "inconnu",
                "risque": "inconnu",
                "couverture_complete": False,
            }
    ex = Explorateur(graine=0, groupe=True)
    for i, a in enumerate(dossier.actions):
        ex.noter(gs[i], action_dict(a), gs[i + 1])
    candidats = [c for c in ex.candidats(gs[-1], dossier.offre) if ex.essais[(gs[-1].tobytes(), ex._cle(c))] == 0]
    if not candidats:
        return None
    # Un nouveau canal avant de répéter un canal connu : principe déjà utilisé par experience_sans_but.
    if contexte["prerequis_selection"]["clic_differe"]:
        candidats = [c for c in candidats if c["action"] != "MOUSE"]
    if not candidats:
        return None
    connus = {action_dict(a)["action"] for a in dossier.actions}
    nouveaux = [c for c in candidats if c["action"] not in connus]
    candidats = nouveaux or candidats
    try:
        choix = ex._par_groupe(gs[-1], candidats)
    except (ValueError, KeyError, TypeError, IndexError, RuntimeError):
        choix = None
    choix = choix or ex.rnd.choice(candidats)
    a = (
        ["clic", int(choix["col"]), int(choix["row"])]
        if choix["action"] == "MOUSE"
        else next(k for k, v in NOMS.items() if v == choix["action"])
    )
    return {
        "actions": [a],
        "predictions": [[{"nom": "aucun_effet_visible_hypothese_nulle", "image": dossier.images[-1].tolist(), "fin": False}]],
        "hud": contexte["hud"],
        "preuve_masque": copy.deepcopy(contexte["preuve_masque"]),
        "question": contexte["question_manquante"],
        "type": "acquisition_pre_theorie",
        "proposeur": "Explorateur_groupes_nouveaute_existant",
        "cout_actions": 1,
        "but": "inconnu",
        "risque": "inconnu",
        "couverture_complete": False,
    }
