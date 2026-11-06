"""Avancer par consensus des hypothèses, observation et replanification."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from apprentissage_regles import Apprentissage
from boucle_navigation_visible import decalage, sauver
from boucle_objets_variables import LaboP1
from decision_horloges import decision
from experience_regles_bp35 import cle
from garde_oscillations import GardeOscillations, signature
from hypotheses_navigation import HypothesesNavigation
from issues_observees import issue_sdk
from monde_temporel import EtatTemporel
from observation_censuree import issue_pour_revision
from perception_hierarchique import decomposer
from preflight_interventions_bp35 import charger
from surface_nouvelle import proposer as proposer_surface

R = Path(__file__).resolve().parent


def scenes_film(before, film, modele):
    _, _, origin = modele.lire(before)
    return [decomposer(g, modele, (origin[0], origin[1] + decalage(before, g, modele.palette)[0]))[0] for g in film]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--executer", action="store_true")
    ap.add_argument("--reprendre", type=Path, required=True)
    ap.add_argument("--limite-reprise", type=int, required=True)
    args = ap.parse_args()
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    m, h, cs, _old, _rows, known = charger()
    prefix = R / "runs/remontee_bp35_reel1/N2/partie"
    pz = np.load(prefix.with_suffix(".npz"))
    pj = json.loads(prefix.with_suffix(".json").read_text())
    # N3 est déjà visible après la victoire N2 ; aucune action N3 antérieure.
    h = HypothesesNavigation(m, clics=(False, True))
    known = set()
    garde = GardeOscillations()
    temporel = EtatTemporel(pz["images"][-1])
    journal_temporel = []
    couleurs_connues = set(map(int, np.unique(pz["images"][:-1])))
    resume_z = resume_j = None
    resume_count = 0
    image_depart = pz["images"][-1]
    if args.reprendre:
        resume_z = np.load(args.reprendre.with_suffix(".npz"))
        resume_j = json.loads(args.reprendre.with_suffix(".json").read_text())
        all_actions = list(resume_j["actions"])
        known.update(cle(resume_z["images"][i], x) for i, x in enumerate(all_actions))
        resume_j["actions"] = all_actions[: args.limite_reprise]
        resume_count = len(resume_j["actions"])
        for k, action in enumerate(resume_j["actions"]):
            garde.enregistrer(signature(resume_z["images"][k], m, action, h.actives()))
            journal_temporel.append(temporel.observer(resume_z["images"][k], resume_z["images"][k + 1], action, m))
            h.observer(resume_z["images"][k], action, resume_z["images"][k + 1], resume_z[f"film_{k + 1}"])
            known.add(cle(resume_z["images"][k], action))
        image_depart = resume_z["images"][resume_count]
    pre = decision(image_depart, h, cs, known, 40 - resume_count, [3, 4, 6, 7], garde, temporel)
    sauver(out / "preflight.json", pre)
    if not args.executer or not pre["plan"]:
        print(json.dumps(pre, default=int))
        return
    a = Apprentissage(
        [{"id": n, **c} for n, c in cs.items()],
        out / "memoire.json",
        {"famille": "navigation_gravite_clic", "portee": "bp35N3", "transfert_autorise": False},
    )
    # Les cinq clauses sont héritées comme hypothèses, pas confirmations N3.
    source = R / "runs/bp35_navigation_visible_reprise1/N1/partie"
    z = np.load(source.with_suffix(".npz"))
    j = json.loads(source.with_suffix(".json").read_text())
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob("*.py")}
    sauver(out / "sources.json", hashes)
    lab = LaboP1("bp35", 1, "/Users/ts/models/chrysalide3/experiments/G/publics20c", out / "N1/partie")
    access = lab
    status = "budget"
    history = []
    acces_n2 = None
    reouvertures = []
    surfaces = []
    try:
        for i, action in enumerate(j["actions"]):
            im, film = lab.play(action, purpose="acces_N2_seulement")
            if not np.array_equal(im, z["images"][i + 1]) or not np.array_equal(film, z[f"film_{i + 1}"]):
                raise ValueError("Accès divergent")
        if not lab.won:
            raise ValueError("Accès non gagné")
        lab = lab.next_level(out / "N2/partie")
        for i, action in enumerate(pj["actions"]):
            im, film = lab.play(action, purpose="acces_frontiere_connue")
            if not np.array_equal(im, pz["images"][i + 1]) or not np.array_equal(film, pz[f"film_{i + 1}"]):
                raise ValueError("Préfixe N2 divergent")
        if not lab.won:
            raise ValueError("Accès N2 non gagné")
        acces_n2 = lab
        lab = lab.next_level(out / "N3/partie")
        if resume_j is not None:
            for t, action in enumerate(resume_j["actions"]):
                im, film = lab.play(action, purpose="restauration_N3_sans_nouvelle_experience")
                if not np.array_equal(im, resume_z["images"][t + 1]) or not np.array_equal(film, resume_z[f"film_{t + 1}"]):
                    raise ValueError("Reprise N3 divergente")
        for k in range(40 - resume_count):
            current = {n: cs[n] for n in a.actives()}
            d = decision(lab.image, h, current, known, 40 - resume_count - k, lab.actions_disponibles, garde, temporel)
            if not d["plan"]:
                sonde = proposer_surface(lab.image, m, couleurs_connues, lab.actions_disponibles, known)
                admissible_sonde = temporel.evaluer(lab.image, m, h, current, sonde["plan"][0]) if sonde is not None else None
                if sonde is not None and admissible_sonde["admissible"]:
                    sonde["controle_temporel"] = admissible_sonde
                    sonde["etapes"][0]["predictions"] = dict.fromkeys(current, "inconnue")
                    d = sonde
            d["offre_reelle"] = lab.actions_disponibles
            sauver(out / f"decision_avant_{k + 1}.json", d)
            if not d["plan"]:
                status = d["raison"]
                break
            action = d["plan"][0]
            action = json.loads(json.dumps(action, default=int))
            before = lab.image.copy()
            key = cle(before, action)
            if key in known:
                raise ValueError("Expérience déjà enregistrée")
            code = 6 if isinstance(action, list) else action
            if code not in lab.actions_disponibles:
                raise ValueError("Action indisponible")
            known.add(key)
            garde.enregistrer(signature(before, m, action, h.actives()))
            im, film = lab.play(action, purpose=d["raison"])
            issue = issue_sdk(lab.rows[-1]["state"], lab.rows[-1]["levels_completed"], 2)
            journal_temporel.append(temporel.observer(before, im, action, m))
            validite = issue_pour_revision(im, m, lab.rows[-1]["state"], lab.rows[-1]["levels_completed"], 2)
            sauver(out / f"validite_apres_{k + 1}.json", validite)
            if not validite["revisable"]:
                status = "observation_censuree"
                history.append({"action": action, "validite": validite})
                break
            # Le rôle contrôle détermine la phase de grille avant l'action ; caméra du film recale ensuite.
            scenes = scenes_film(before, film, m)
            obs = a.observer(
                scenes, issue, hashlib.sha256(film.tobytes() + key.encode()).hexdigest(), True, d["etapes"][0]["predictions"]
            )
            history.append({"action": action, "raison": d["raison"], "observation": obs})
            sauver(out / "apprentissage.json", a.rapport())
            if lab.finished:
                status = "victoire_N3" if lab.won else "defaite"
                break
            h.observer(before, action, im, film, issue_observee=issue)
            if d["raison"] == "sonde_classe_visuelle_nouvelle":
                preuves = m.apprendre_clics([before, im], [action])
                surfaces.append(
                    {"coup": k + 1, "preuves": preuves, "portee": "ouverture observée, fermeture et permanence non établies"}
                )
            if not h.actives():
                ancien = h.journal
                h = HypothesesNavigation(m, clics=(False, True))
                h.observer(before, action, im, film, issue_observee=issue)
                reouvertures.append({"coup": k + 1, "ancien": ancien, "nouveau": h.journal})
                if not h.actives():
                    status = "transition_hors_catalogue"
                    break
    except (ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        status = "refus:" + repr(exc)
    finally:
        bilan = {
            "statut": status,
            "coups_N1": len(access.rows),
            "coups_N2": len(acces_n2.rows) if acces_n2 is not None else (len(lab.rows) if lab is not access else 0),
            "coups_N3": len(lab.rows) if acces_n2 is not None else 0,
            "coups_reprise_N3": resume_count if acces_n2 is not None else 0,
            "initialisations": 1,
            "resets": 0,
            "hypotheses_contact": a.actives(),
            "hypotheses_dynamique": h.actives(),
            "sources_inchangees": hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob("*.py")},
        }
        sauver(out / "reouvertures.json", reouvertures)
        sauver(out / "surfaces.json", surfaces)
        sauver(out / "monde_temporel.json", journal_temporel)
        sauver(out / "bilan.json", bilan)
        sauver(out / "historique.json", history)
        sauver(out / "dynamique.json", h.journal)
        print(json.dumps(bilan))


if __name__ == "__main__":
    main()
