"""Le neuronal choisit une expérience dans une liste vérifiable, jamais une vérité."""

import json

from evidence_films import Films
from PIL import Image
from reprise_flux_27b import appeler_flux

from chrysalide.qwen.images import PAL


def consulter(image, avant, film, decision, out, numero):
    out.mkdir(exist_ok=True)
    current = out / f"actuel_{numero}.png"
    Image.fromarray(PAL[image % 16]).resize((640, 640), Image.Resampling.NEAREST).save(current)
    files = [current]
    if avant is not None:
        f = Films()
        f.ajouter(avant, film)
        for k, page in enumerate(f.planches(0)):
            p = out / f"film_{numero}_{k}.png"
            p.write_bytes(page)
            files.append(p)
    candidates = decision["experiences_candidates"]
    schema = {
        "type": "object",
        "required": ["experience", "hypothese", "question"],
        "properties": {
            "experience": {"type": "integer", "minimum": 0, "maximum": len(candidates) - 1},
            "hypothese": {"type": "string"},
            "question": {"type": "string"},
        },
        "additionalProperties": False,
    }
    prompt = (
        "Tu es un expérimentateur dans un jeu inconnu. Les modèles sont partiels, pas des vérités. "
        "Choisis une expérience qui départage les explications ou explore une erreur perceptive. "
        "Ne donne pas une solution mémorisée. Les coordonnées des actions sont celles de la grille64x64, "
        "les images sont agrandies. Le défilement de caméra ne prouve pas un mouvement du personnage. "
        "Les pages de film conservent TOUTES les images intermédiaires dans leur ordre. "
        "Réponds uniquement au JSON demandé ; experience est un indice zéro-based de la liste. "
        "Ton hypothèse devra être vérifiée après action.\n" + json.dumps(decision, default=int, ensure_ascii=False)
    )
    raw, met = appeler_flux(prompt, files, out, numero, schema, jetons=400, delai=55, modele="gemma3:4b")
    if met["erreur"]:
        raise ValueError(f"Appel neuronal échoué : {met['erreur']}")
    rep = json.loads(raw)
    i = rep.get("experience")
    if type(i) is not int or not 0 <= i < len(candidates):
        raise ValueError("Expérience neuronale hors catalogue")
    return {
        "proposition": rep,
        "action": candidates[i]["action"],
        "metriques": met,
        "autorite": "proposition seulement ; prédictions comparées après action",
    }


def reparer_perception(modele, image, out, numero):
    from perception_navigation import candidats

    out.mkdir(exist_ok=True)
    paths = []
    for name, g in [("observe", image), ("reference_avant", modele.images[0]), ("reference_apres", modele.images[1])]:
        p = out / f"perception_{numero}_{name}.png"
        Image.fromarray(PAL[g % 16]).resize((640, 640), Image.Resampling.NEAREST).save(p)
        paths.append(p)
    cs = candidats(modele, image)
    schema = {
        "type": "object",
        "required": ["hypothese", "raison"],
        "properties": {
            "hypothese": {"type": "string", "enum": ["union_couleurs", "motif_connexe", "abstention"]},
            "raison": {"type": "string"},
        },
        "additionalProperties": False,
    }
    prompt = (
        "L'identification du personnage par union de ses couleurs échoue : silhouette étalée. "
        "Les deux images de référence précèdent et suivent une commande de déplacement observée. "
        "Choisis une hypothèse de perception à vérifier, pas une solution de jeu. "
        "union_couleurs = regrouper tous les pixels des couleurs apprises ; motif_connexe = "
        "chercher une composante connexe ayant le motif multicolore observé dans les références, miroir autorisé. "
        "abstention si insuffisant. Ne devine pas de règle du jeu. Candidats motif_connexe actuels (centres64x64) : " + str(cs)
    )
    raw, met = appeler_flux(prompt, paths, out, numero, schema, jetons=300, delai=55, modele="gemma3:4b")
    if met["erreur"]:
        raise ValueError("Neuronal perception indisponible")
    rep = json.loads(raw)
    if rep.get("hypothese") != "motif_connexe" or len(cs) != 1:
        raise ValueError("Hypothèse neuronale de perception non applicable")
    # Vérification sur toutes les références causales avant activation.
    from perception_navigation import position

    if any(position(modele, g) != modele.position(g) for g in modele.images):
        raise ValueError("Perception proposée contredit les références")
    modele.perception_connexe = True
    return {"proposition": rep, "metriques": met, "candidats": cs, "statut": "compatible_references_a_verifier_sur_actions"}
