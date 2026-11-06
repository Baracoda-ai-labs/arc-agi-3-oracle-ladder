"""Pilote séquentiel : hypothèses issues du préfixe seul, expérience, révision, SDK."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent


def sauver(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))


def decider(source, sortie, offre, timeout=60):
    """Ne reçoit ni identifiant de jeu, ni résultat futur, ni solution."""
    sortie.mkdir(parents=True, exist_ok=False)
    for suffixe in (".npz", ".json"):
        shutil.copyfile(source.with_suffix(suffixe), (sortie / "prefixe").with_suffix(suffixe))
    source = sortie / "prefixe"
    j = json.loads(source.with_suffix(".json").read_text())
    actions = [r["action"] for r in j["rows"]]
    selection = any(isinstance(a, list) for a in actions)
    script = "preparer_selection.py" if selection else "preparer_roles.py"
    cmd = [sys.executable, str(ICI / script), "--source", str(source), "--sortie", str(sortie / "candidats")]
    if not selection:
        cmd.append("--sans-ablation")
    debut = time.monotonic()
    traces = []

    def lancer(cmd):
        restant = timeout - (time.monotonic() - debut)
        if restant <= 0:
            raise subprocess.TimeoutExpired(cmd, timeout)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=restant, check=False)
        traces.append({"commande": cmd, "code": r.returncode, "stdout": r.stdout, "stderr": r.stderr})
        return r.returncode == 0

    try:
        lancer(cmd)
        exp = sortie / "candidats/experience.json"
        if not exp.exists() and not selection and 6 in offre:
            exp = sortie / "selection.json"
            lancer([sys.executable, str(ICI / "experience_selection_visuelle.py"), "--source", str(source), "--sortie", str(exp)])
        if not exp.exists():
            exp = sortie / "sans_but.json"
            lancer(
                [
                    sys.executable,
                    str(ICI / "experience_sans_but.py"),
                    "--source",
                    str(source),
                    "--sortie",
                    str(exp),
                    "--offre",
                    json.dumps(offre),
                ]
            )
        statut = "experience" if exp.exists() else "hors_domaine_ou_aucune_experience"
    except subprocess.TimeoutExpired:
        statut = "budget_decision"
        exp = None
    sauver(
        sortie / "decision.json",
        {
            "statut": statut,
            "historique_actions": len(actions),
            "branche": "selection_contact" if selection else "roles_puis_selection",
            "secondes": time.monotonic() - debut,
            "appels": traces,
        },
    )
    return exp if statut == "experience" else None


def comparer(predictions, image, film, hud, victoire):
    """L'écran suivant n'est pas le rendu terminal du niveau quitté."""
    resultat = []
    for h in predictions:
        p = np.asarray(h["image"]).copy()

        def ecart(g, p=p):
            obs = np.asarray(g).copy()
            pred = p.copy()
            for y, x in hud:
                obs[y, x] = pred[y, x] = 0
            return int(np.count_nonzero(obs != pred))

        dernier = ecart(image)
        terminal_attendu = bool(h.get("fin", False))
        ecarts = [ecart(g) for g in film]
        conforme = dernier == 0 and terminal_attendu == victoire
        if h["nom"] == "aucun_effet_visible_hypothese_nulle":
            conforme = conforme and all(d == 0 for d in ecarts)
        if victoire and terminal_attendu and 0 in ecarts:
            conforme = True
        resultat.append(
            {
                "nom": h["nom"],
                "ecart_final": dernier,
                "ecarts_film": ecarts,
                "terminal_attendu": terminal_attendu,
                "conforme": conforme,
            }
        )
    return resultat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--coups", type=int, default=80)
    ap.add_argument("--secondes", type=float, default=240)
    ap.add_argument("--reprendre", type=Path)
    args = ap.parse_args()
    # Liste publique déjà autorisée ; refus avant création d'une partie.
    autorises = {
        "ar25",
        "bp35",
        "cd82",
        "dc22",
        "ft09",
        "g50t",
        "ka59",
        "lf52",
        "lp85",
        "ls20",
        "m0r0",
        "r11l",
        "re86",
        "sb26",
        "sc25",
        "sk48",
        "sp80",
        "su15",
        "tn36",
        "tr87",
    }
    if args.jeu not in autorises:
        raise ValueError("Jeu hors liste publique autorisée")
    if not 8 <= args.coups <= 80 or not 0 < args.secondes <= 240:
        raise ValueError("Budget hors protocole")
    args.sortie.mkdir(parents=True, exist_ok=False)
    # Import du seul harnais public ; aucune inspection des sources de jeux.
    from boucle_objets_variables import LaboP1

    sources = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            ICI / n
            for n in (
                "boucle_roles_autonome.py",
                "preparer_roles.py",
                "preparer_selection.py",
                "experience_selection_visuelle.py",
                "roles_observes.py",
                "objets_variables.py",
                "experience_sans_but.py",
                "selection_observee.py",
                "plan_selection_dynamique.py",
            )
        ]
    }
    sauver(args.sortie / "sources.json", sources)
    lab = LaboP1(args.jeu, 1, "/Users/ts/models/chrysalide3/experiments/G/publics20c", args.sortie / "N1/partie")
    debut = time.monotonic()
    journal = []
    vus = set()
    tentatives = 0
    statut = "budget"
    restaurations = 0
    sondes_sans_effet = 0

    def offre():
        return [int(getattr(a, "value", a)) for a in lab.actions_disponibles]

    def bilan():
        sauver(args.sortie / "journal.json", journal)
        b = {
            "jeu": args.jeu,
            "statut": statut,
            "coups_reels": len(lab.rows),
            "appels_step_tentes": tentatives,
            "initialisations": 1,
            "coups_restauration": restaurations,
            "coups_nouveaux": len(lab.rows) - restaurations,
            "niveaux_gagnes": int(lab.won),
            "jeu_gagne": lab.partie_gagnee,
            "secondes": time.monotonic() - debut,
            "appels_ia": 0,
            "retouches_pendant_essai": 0,
        }
        sauver(args.sortie / "bilan.json", b)
        return b

    try:
        if args.reprendre:
            precedent = json.loads(args.reprendre.with_suffix(".json").read_text())
            archive = np.load(args.reprendre.with_suffix(".npz"))
            if len(precedent["rows"]) >= args.coups:
                raise ValueError("Archive dépasse le budget de reprise")
            if precedent["game"] != args.jeu or precedent["level"] != 1 or precedent["victory"]:
                raise ValueError("Archive incompatible avec la reprise")
            if not np.array_equal(lab.image, archive["images"][0]):
                raise ValueError("État initial différent")
            for k, row in enumerate(precedent["rows"]):
                a = row["action"]
                code = a if isinstance(a, int) else 6
                if code not in offre():
                    raise ValueError("Action de restauration indisponible")
                tentatives += 1
                restaurations += 1
                g, f = lab.play(a, purpose="restauration_comptee_pas_une_nouvelle_sonde")
                bilan()
                if (
                    lab.finished
                    or not np.array_equal(g, archive["images"][k + 1])
                    or not np.array_equal(f, archive[f"film_{k + 1}"])
                ):
                    raise ValueError("Restauration différente")
            sauver(
                args.sortie / "restauration.json",
                {"source": str(args.reprendre), "coups": restaurations, "images_et_films_identiques": True},
            )
        else:
            for a in [1, 2, 3, 4] * 2:
                if a not in offre():
                    continue
                tentatives += 1
                lab.play(a, purpose="sonde_initiale_generique")
                bilan()
                if lab.finished:
                    break
        for cycle in range(80):
            if lab.finished or len(lab.rows) >= args.coups:
                break
            if sondes_sans_effet >= 3:
                statut = "trois_sondes_sans_effet"
                break
            restant = args.secondes - (time.monotonic() - debut)
            if restant <= 0:
                break
            dossier = args.sortie / f"decision_{cycle:02d}"
            exp = decider(args.sortie / "N1/partie", dossier, offre(), timeout=min(60, restant))
            if exp is None:
                statut = json.loads((dossier / "decision.json").read_text())["statut"]
                break
            e = json.loads(exp.read_text())
            raw = exp.read_bytes()
            entry = {
                "cycle": cycle,
                "avant": len(lab.rows),
                "experience": str(exp),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "resultats": [],
            }
            journal.append(entry)
            bilan()  # Prédictions persistées AVANT tout coup.
            cle = hashlib.sha256(lab.image.tobytes() + json.dumps(e["actions"]).encode()).hexdigest()
            if cle in vus:
                statut = "experience_deja_jouee_meme_image"
                break
            vus.add(cle)
            survivants = None
            for a, hs in zip(e["actions"], e["predictions"], strict=True):
                if lab.finished or len(lab.rows) >= args.coups or time.monotonic() - debut >= args.secondes:
                    break
                code = a if isinstance(a, int) else 6
                if code not in offre():
                    statut = "action_indisponible"
                    return
                tentatives += 1
                g, film = lab.play(a, purpose=e["question"])
                tests = comparer(hs, g, film, e.get("hud", []), lab.won)
                valides = {r["nom"] for r in tests if r["conforme"]}
                if e.get("type") == "sonde_sans_but":
                    sondes_sans_effet = sondes_sans_effet + 1 if valides else 0
                survivants = valides if survivants is None else survivants & valides
                entry["resultats"].append(
                    {"coup": len(lab.rows), "comparaisons": tests, "victoire_sdk": lab.won, "frames": len(film)}
                )
                bilan()
                if lab.finished or not survivants:
                    break
    except Exception as err:
        statut = "erreur"
        journal.append({"erreur": repr(err)})
        raise
    finally:
        if lab.finished:
            statut = "victoire_reelle" if lab.won else "defaite_reelle"
        print(json.dumps(bilan()), flush=True)


if __name__ == "__main__":
    main()
