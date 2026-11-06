"""Un statut intermédiaire sans contrôle reconnu ne prouve pas la survie."""

from issues_observees import issue_sdk, scene_image


def issue_pour_revision(image, modele, state, niveaux, baseline):
    issue = issue_sdk(state, niveaux, baseline)
    if issue != "continue":
        return {"issue": issue, "revisable": True, "raison": "terminal_sdk"}
    controls = [o for o in scene_image(image, modele).sprites if "controle" in o.get("tags", ())]
    if len(controls) != 1:
        return {"issue": "inconnue", "revisable": False, "raison": "controle_non_unique_avec_sdk_intermediaire"}
    return {
        "issue": issue,
        "revisable": True,
        "raison": "controle_reconnu_et_sdk_intermediaire",
        "limite": "absence de terminal maintenant, pas absence de danger futur",
    }
