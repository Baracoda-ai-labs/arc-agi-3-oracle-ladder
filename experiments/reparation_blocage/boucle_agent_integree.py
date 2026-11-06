"""Harnais multijeux : un seul pilote, budget global, observations avant replanification."""

import argparse
import ast
import hashlib
import json
import resource
import signal
import sys
import time
from pathlib import Path

import numpy as np
from boucle_objets_variables import LaboP1
from chaine_agent_integree import AgentIntegre
from issues_observees import issue_sdk

R = Path(__file__).parent
AUTORISES = {
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
DEPENDANCES = [
    "paquet/references/astra4/livraison_astra4/ajouts/boucle_v4/economie.py",
    "boucle_agent_integree.py",
    "chaine_agent_integree.py",
    "chaine_coherente.py",
    "controleur_experimentation.py",
    "atms.py",
    "evidence_films.py",
    "objets_variables.py",
    "roles_observes.py",
    "selection_observee.py",
    "perception_guidee.py",
    "plan_selection_dynamique.py",
    "boucle_roles_autonome.py",
    "preparer_roles.py",
    "preparer_selection.py",
    "experience_sans_but.py",
    "experience_selection_visuelle.py",
]


def sauver(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=int))


def empreintes(paths=None):
    if paths is None:
        paths = {str((R / n).resolve()) for n in DEPENDANCES}
        paths.update(
            str(Path(m.__file__).resolve())
            for m in list(sys.modules.values())
            if getattr(m, "__file__", None)
            and (str(R.resolve()) in str(m.__file__) or getattr(m, "__name__", "").startswith(("chrysalide.", "agent_p1.")))
            and str(m.__file__).endswith(".py")
        )
        pending = list(paths)
        while pending:
            p = pending.pop()
            for node in ast.walk(ast.parse(Path(p).read_text())):
                names = (
                    [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else [x.name for x in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                for name in names:
                    q = R / (name.split(".")[0] + ".py")
                    if q.is_file() and str(q.resolve()) not in paths:
                        paths.add(str(q.resolve()))
                        pending.append(str(q.resolve()))
    paths = set(paths) | {str((R / 'dreamcoder_bibliotheque.json').resolve())}
    return {str(n): hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in sorted(paths)}


def main(args, *, dossier_jeux=None, jeux_autorises=None):
    # Overrides réservés aux harnais qui valident leur propre catalogue explicite.
    # L'interface CLI publique conserve exactement sa racine et son allowlist.
    if (dossier_jeux is None) != (jeux_autorises is None):
        raise ValueError("Racine et catalogue doivent être fournis ensemble")
    racine = dossier_jeux if dossier_jeux is not None else "/Users/ts/models/chrysalide3/experiments/G/publics20c"
    autorises = set(jeux_autorises) if jeux_autorises is not None else AUTORISES
    if args.jeu not in autorises:
        raise ValueError("Jeu non autorisé")
    if not 8 <= args.coups <= 80 or not 0 < args.secondes <= 240:
        raise ValueError("Budget hors protocole")
    decouverte_courte = getattr(args, "decouverte_courte", False)
    legacy_sans_but = getattr(args, "legacy_sans_but", False)
    utilite_sondes = getattr(args, "utilite_sondes", False)
    exploration_p1 = getattr(args, "exploration_p1", False)
    routage_classes = getattr(args, "routage_classes", False)
    aiguillage_provisoire = getattr(args, "aiguillage_provisoire", False)
    revision_solidite = getattr(args, "revision_solidite", False)
    revision_projection = getattr(args, "revision_projection", False)
    dreamcoder_mots = getattr(args, "dreamcoder_mots", False)
    recherche_briques = getattr(args, "recherche_briques", "off")
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    hashes = empreintes()
    sauver(out / "sources.json", hashes)
    start = time.monotonic()
    cpu = time.process_time()
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    lab = None
    agent = None
    status = "budget"
    decisions = []
    attempts = 0
    initialisations_tentees = 0

    def bilan():
        kids = resource.getrusage(resource.RUSAGE_CHILDREN)
        b = {
            "jeu": args.jeu,
            "statut": status,
            "coups_reels": len(lab.rows) if lab else 0,
            "appels_step_tentes": attempts,
            "intervalle_coups_en_incident": [len(lab.rows) if lab else 0, attempts],
            "initialisations": int(lab is not None),
            "initialisations_tentees": initialisations_tentees,
            "niveaux_gagnes": int(lab.won) if lab else 0,
            "jeu_gagne": lab.partie_gagnee if lab else False,
            "secondes": time.monotonic() - start,
            "cpu_s": time.process_time() - cpu + kids.ru_utime + kids.ru_stime - children.ru_utime - children.ru_stime,
            "revisions": agent.revisions if agent else 0,
            "decouverte_courte": decouverte_courte,
            "legacy_sans_but": legacy_sans_but,
            "utilite_sondes": utilite_sondes,
            "exploration_p1": exploration_p1,
            "routage_classes": routage_classes,
            "aiguillage_provisoire": aiguillage_provisoire,
            "revision_solidite": revision_solidite,
            "revision_projection": revision_projection,
            "dreamcoder_mots": dreamcoder_mots,
            "recherche_briques": recherche_briques,
            "sources_inchangees": hashes == empreintes(hashes),
            "nouveaute": "raccord capacités/Chaine/calques/replanification à chaque coup ; pas gain contre Franzen établi",
        }
        sauver(out / "bilan.json", b)
        sauver(out / "journal.json", agent.journal if agent else [])
        return b

    def expired(_signum, _frame):
        raise TimeoutError("Budget mural global épuisé")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, args.secondes)
    try:
        initialisations_tentees = 1
        bilan()
        lab = LaboP1(args.jeu, 1, str(racine), out / "N1/partie")
        for a in [] if decouverte_courte else [1, 2, 3, 4] * 2:
            if lab.finished or time.monotonic() - start >= args.secondes:
                break
            if a not in lab.actions_disponibles:
                continue
            attempts += 1
            bilan()
            lab.play(a, purpose="sonde_initiale_generique_comptee")
        if not lab.finished:
            npz = np.load(out / "N1/partie.npz")
            acts = [r["action"] for r in lab.rows]
            agent = AgentIntegre(
                list(npz["images"]),
                acts,
                [npz[f"film_{i + 1}"] for i in range(len(acts))],
                [issue_sdk(r["state"], r["levels_completed"], 0) for r in lab.rows],
                args.coups,
                not args.sans_reparation,
                decouverte_courte=decouverte_courte,
                legacy_sans_but=legacy_sans_but,
                utilite_sondes=utilite_sondes,
                exploration_p1=exploration_p1,
                routage_classes=routage_classes,
                aiguillage_provisoire=aiguillage_provisoire,
                revision_solidite=revision_solidite,
                revision_projection=revision_projection,
                dreamcoder_mots=dreamcoder_mots,
                recherche_briques=recherche_briques,
            )
        for cycle in range(args.coups):
            if lab.finished or len(lab.rows) >= args.coups or time.monotonic() - start >= args.secondes:
                break
            if empreintes(hashes) != hashes:
                raise ValueError("Sources modifiées pendant mesure")
            folder = out / f"decision_{cycle:03d}"
            folder.mkdir()
            remaining = args.secondes - (time.monotonic() - start)
            d = agent.decider(lab.actions_disponibles, folder, out / "N1/partie", secondes=min(30, remaining))
            sauver(folder / "decision.json", d)
            decisions.append(d["statut"])
            bilan()
            if not d.get("actions"):
                status = d["statut"]
                break
            if time.monotonic() - start >= args.secondes:
                status = "budget"
                break
            a = d["actions"][0]
            code = 6 if isinstance(a, list) else a
            if code not in lab.actions_disponibles:
                raise ValueError("Action non offerte")
            attempts += 1
            bilan()
            im, film = lab.play(a, purpose=d["statut"])
            result = agent.observer(a, im, film, issue_sdk(lab.rows[-1]["state"], lab.rows[-1]["levels_completed"], 0))
            sauver(folder / "observation.json", result)
            bilan()
        if lab.finished:
            status = "victoire_reelle" if lab.won else "defaite_reelle"
    except TimeoutError:
        status = "budget_mural"
    except (ValueError, KeyError, TypeError, IndexError, RuntimeError, AssertionError) as exc:
        status = "refus"
        sauver(out / "erreur.json", {"erreur": repr(exc)})
    except Exception as exc:
        status = "incident_execution"
        sauver(out / "erreur.json", {"erreur": repr(exc)})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        print(json.dumps(bilan()), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--coups", type=int, default=80)
    ap.add_argument("--secondes", type=float, default=240)
    ap.add_argument("--sans-reparation", action="store_true")
    ap.add_argument("--decouverte-courte", action="store_true")
    ap.add_argument("--legacy-sans-but", action="store_true")
    ap.add_argument("--utilite-sondes", action="store_true")
    ap.add_argument("--exploration-p1", action="store_true")
    ap.add_argument("--routage-classes", action="store_true")
    ap.add_argument("--aiguillage-provisoire", action="store_true")
    ap.add_argument("--revision-solidite", action="store_true")
    ap.add_argument("--revision-projection", action="store_true")
    ap.add_argument("--dreamcoder-mots", action="store_true")
    ap.add_argument("--recherche-briques", choices=("off", "naturel", "dreamcoder"), default="off")
    main(ap.parse_args())
