"""Deux propositions indépendantes sur archives : anticipation puis diagnostic."""

import argparse
import hashlib
import json
import signal
from pathlib import Path

import numpy as np
from evidence_films import Films
from issues_observees import issue_sdk, scene_image
from reprise_flux_27b import appeler_flux
from transfert_navigation_bp35 import apprendre

from chrysalide.arc3.langage import Programme
from chrysalide.langue import depuis_python

R = Path(__file__).resolve().parent
SOURCE = R / "runs/bp35_N2_hypotheses_neuronal_reprise1"
SCHEMA = {
    "type": "object",
    "required": [
        "programme_python",
        "hypothese",
        "alternative",
        "experience",
        "prediction_si_vraie",
        "prediction_si_fausse",
        "preuves",
    ],
    "properties": {
        **{
            k: {"type": "string"}
            for k in ["programme_python", "hypothese", "alternative", "experience", "prediction_si_vraie", "prediction_si_fausse"]
        },
        "preuves": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}
CONTRAT = """Tu proposes une règle pour compléter un modèle de jeu inconnu, sans solution donnée.
Le modèle représente déplacement, gravité et suppression au clic, mais les issues restent inconnues.
Examine les observations réelles, leurs actions exactes et les films. Une animation n'est pas une action.
Produis UNE hypothèse de règle dans notre Python déclaratif, une explication concurrente et une expérience
précise avec deux résultats observables différents. Cite les frames qui soutiennent ton hypothèse.
Si insuffisant, programme_python peut rester vide. Ne sélectionne pas dans un menu et n'invente pas de faits.
Le texte Python est parsé, jamais exécuté. Syntaxe disponible :
from chrysalide_langue import *
PROGRAMME = Programme(mode="regles", regles=[Regle("nom", quand=EXPRESSION, alors=[EFFET])])
Primitives disponibles : objets({"tag":"..."}), existe(EXPRESSION for o in objets(...)),
x(o), y(o), largeur(o), hauteur(o), contact_moteur(a,b), chevauche(a,b), visible(o),
comparaisons, and/or/not, action(), perdre(), gagner(), niveau_suivant().
Chaque générateur a une seule boucle ; imbriquer les existe pour plusieurs objets.
Tags perceptifs : controle pour la composante suivie ; couleur_N pour chaque composante de couleur ARC N.
Les masques visibles sont disjoints ; une collision cachée n'est pas forcément représentée.
N'invente aucun tag, variable libre ou fonction. Coordonnées64x64, x horizontal,y vertical.
Il n'y a pas de copie des sources du jeu ni de capteur d'état interne.
Toutes les images intermédiaires sont fournies en planches ordonnées, avec référence globale.
Le code proposé sera vérifié après ta réponse, indépendamment du texte explicatif.
"""


def audit(code, modele, episodes):
    if not code.strip():
        return {"statut": "abstention"}
    if len(code) > 8000:
        return {"statut": "refus_taille"}
    try:
        p = depuis_python(code)
        if set(p) - {"mode", "regles", "etat", "origine"} or p.get("etat") or not 1 <= len(p.get("regles", [])) <= 4:
            raise ValueError("Programme hors contrat borné de règles sans état")
        serial = json.dumps(p)
        if any('"' + op + '"' in serial for op in ("tant_que", "alea", "donnees_de_niveau", "attr_cache")):
            raise ValueError("Opérateur hors observations ou hors budget")
        pr = Programme(p)
        results = []

        def stop(_s, _f):
            raise TimeoutError("Audit borné10s")

        signal.signal(signal.SIGALRM, stop)
        signal.alarm(10)
        try:
            for e in episodes:
                issues = []
                for g in e["frames"]:
                    sc = scene_image(g, modele)
                    pr.step(
                        sc,
                        ("MOUSE", e["action"][2], e["action"][1])
                        if isinstance(e["action"], list)
                        else ({3: "LEFT", 4: "RIGHT"}.get(e["action"], "OTHER"),),
                    )
                    issues.append(sc.issue)
                predicted = next((v for v in issues if v is not None), "inconnue")
                results.append(
                    {
                        "episode": e["nom"],
                        "observe": e["issue"],
                        "declenchements": issues,
                        "issue_predite": predicted,
                        "contradiction_observee": predicted != "inconnue" and predicted != e["issue"],
                    }
                )
        finally:
            signal.alarm(0)
        return {
            "statut": "executable",
            "programme_interne": p,
            "episodes": results,
            "portee": "rejeu perceptif des issues, pas simulateur complet ni preuve de causalité",
        }
    except Exception as e:  # noqa: BLE001 -- proposition non fiable, diagnostic conservé
        return {"statut": "refuse", "raison": repr(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    out = ap.parse_args().sortie
    out.mkdir(parents=True, exist_ok=False)
    m, _h, _b, z1, j1 = apprendre()
    m.perception_connexe = True
    z = np.load(SOURCE / "N2/partie.npz")
    j = json.loads((SOURCE / "N2/partie.json").read_text())
    episodes = []
    for i, row in enumerate(j["rows"], 1):
        episodes.append(
            {
                "nom": f"N2_coup{i}",
                "action": row["action"],
                "issue": issue_sdk(row["state"], row["levels_completed"], 1),
                "frames": z[f"film_{i}"],
            }
        )
    # Contrôles négatifs de terminaison : N1 avant victoire, jamais fournis comme solution.
    for i, row in enumerate(j1["rows"][:-1], 1):
        episodes.append({"nom": f"N1_coup{i}", "action": row["action"], "issue": "continue", "frames": z1[f"film_{i}"]})
    results = []
    for phase, limit in [("anticipation", 1), ("diagnostic", 2)]:
        dst = out / phase
        dst.mkdir()
        f = Films()
        files = []
        for i in range(limit):
            f.ajouter(z["images"][i], z[f"film_{i + 1}"])
            for n, png in enumerate(f.planches(i)):
                p = dst / f"coup_{i + 1}_page_{n}.png"
                p.write_bytes(png)
                files.append(p)
        observations = [
            {
                "coup": i + 1,
                "action": row["action"],
                "etat_sdk": row["state"],
                "niveaux_termines": row["levels_completed"],
                "frames": len(z[f"film_{i + 1}"]),
            }
            for i, row in enumerate(j["rows"][:limit])
        ]
        prompt = CONTRAT + "\nOBSERVATIONS DISPONIBLES\n" + json.dumps(observations, ensure_ascii=False)
        (dst / "entrees.json").write_text(
            json.dumps(
                {
                    "prefixe_coups": limit,
                    "frames": sum(o["frames"] for o in observations),
                    "images_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                    "futur_non_fourni": phase == "anticipation",
                },
                indent=2,
            )
        )
        raw, metrics = appeler_flux(prompt, files, dst, 1, SCHEMA, jetons=1100, delai=55, modele="gemma3:4b")
        try:
            response = json.loads(raw)
            code = response.get("programme_python", "")
            (dst / "proposition.py").write_text(code)
            verdict = audit(code, m, episodes)
        except (ValueError, TypeError) as e:
            verdict = {"statut": "json_invalide", "raison": repr(e)}
        (dst / "audit.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2))
        results.append({"phase": phase, "metriques": metrics, "audit": verdict})
    (out / "bilan.json").write_text(
        json.dumps(
            {"resultats": results, "sdk": 0, "coups_reels": 0, "gain_niveaux": 0, "apprentissage_sur_cas_connu": True},
            ensure_ascii=False,
            indent=2,
        )
    )
    print(json.dumps([{"phase": r["phase"], "statut": r["audit"]["statut"]} for r in results]))


if __name__ == "__main__":
    main()
