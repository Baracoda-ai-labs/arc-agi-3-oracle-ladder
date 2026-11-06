"""Préfixes isolés puis travailleurs hors jeu ; aucun moteur ARC instancié."""

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from chaine_coherente import Chaine
from controleur_experimentation import Controleur, Dossier
from hypotheses_navigation import HypothesesNavigation
from issues_observees import issue_sdk
from navigation_gravite_visible import NavigationVisible
from roles_observes import PerceptionRoles

R = Path(__file__).resolve().parent


def save(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=int))


def canon(a):
    return ["MOUSE", a[2], a[1]] if isinstance(a, list) else [{1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT"}[a]]


def travailler(folder, petites_regles=False):
    start = time.monotonic()
    meta = json.loads((folder / "prefixe.json").read_text())
    z = np.load(folder / "prefixe.npz")
    ims = list(z["images"])
    actions = meta["actions"]
    films = [z[f"film_{i + 1}"] for i in range(len(actions))]
    d = Dossier(ims, actions, films, meta["issues"], meta["coups_payes"], 4, tuple(meta["offre"]))
    chaines = {}
    diagnostics = []
    lots = [
        {"actions": [{"action": canon(a)[0], **({"row": a[2], "col": a[1]} if isinstance(a, list) else {})}]} for a in actions
    ]
    offered = [tuple(canon(a)) for a in actions if isinstance(a, int)]
    offered = list(dict.fromkeys(offered))
    for decor, roles in itertools.product((False, True), repeat=2):
        name = f"objets_decor{int(decor)}_roles{int(roles)}"
        try:
            v = PerceptionRoles(ims, [a if isinstance(a, int) else 6 for a in actions], decor_revele=decor, roles=roles)
            c = Chaine(v, v.programme(), [g.tolist() for g in ims], lots, offered, coups_deja_joues=len(actions), films=films)
            report, cur = c.rejouer()
            diagnostics.append({"nom": name, "controle": report})
            if cur is not None:
                chaines[name] = c
        except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
            diagnostics.append({"nom": name, "refus": repr(exc)})
    experiments = []
    for size in (1, 2):
        for seq in itertools.product(offered, repeat=size):
            experiments.append(
                "PROGRAMME = Programme(regles=[], experience="
                + repr(
                    {
                        "actions": [list(a) for a in seq],
                        "question": "Les hypothèses prédisent-elles le même effet visible de cette séquence ?",
                    }
                )
                + ")"
            )
    local = None
    try:
        if (folder / "reference.npz").exists():
            ref = np.load(folder / "reference.npz")
            learn = json.loads((folder / "reference.json").read_text())
            m = NavigationVisible(ref["images"], learn["actions"])
            m.cassables = set(learn["cassables"])
            m.perception_connexe = True
        else:
            m = NavigationVisible(ims, actions)
        h = HypothesesNavigation(m, clics=(True,) if m.cassables else (False,))
        for i, a in enumerate(actions):
            h.observer(ims[i], a, ims[i + 1], films[i], issue_observee=meta["issues"][i])
        if h.actives():
            local = h
        diagnostics.append({"nom": "navigation_locale", "actives": h.actives()})
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        diagnostics.append({"nom": "navigation_locale", "refus": repr(exc)})
    coverage = {
        "issues": "inconnue",
        "contact": "inconnue",
        "mouvement": "compatible" if chaines or local else "inconnue",
        "perception": "compatible" if chaines or local else "inconnue",
    }
    report = Controleur().decider(d, chaines, experiments, local, coverage, petites_regles=petites_regles)
    report.update(diagnostics=diagnostics, secondes=time.monotonic() - start, sdk=0)
    save(folder / "decision.json", report)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path)
    ap.add_argument("--worker", type=Path)
    ap.add_argument("--petites-regles", action="store_true")
    args = ap.parse_args()
    if args.worker:
        r = travailler(args.worker, petites_regles=args.petites_regles)
        print(json.dumps({"statut": r["statut"], "secondes": r["secondes"]}))
        return
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    cases = [
        ("bp35", R / "runs/bp35_N2_hypotheses_neuronal_reprise1/N2/partie", 1, 1),
        ("ka59", R / "runs/guidage_ka59_fige1/N1/partie", 8, 0),
        ("ar25", R / "runs/perception_guidee_arc1/N1/partie", 8, 0),
    ]
    for name, src, n, baseline in cases:
        folder = out / name
        folder.mkdir()
        raw = json.loads(src.with_suffix(".json").read_text())
        z = np.load(src.with_suffix(".npz"))
        assert raw["game"] == name and len(raw["rows"]) >= n
        rows = raw["rows"][:n]
        actions = [r["action"] for r in rows]
        np.savez_compressed(
            folder / "prefixe.npz", images=z["images"][: n + 1], **{f"film_{i}": z[f"film_{i}"] for i in range(1, n + 1)}
        )
        offer = sorted({6 if isinstance(a, list) else a for a in actions})
        paid = n
        if name == "bp35":
            # Mémoire déjà acquise N1 ; aucune lecture du second coup N2 pour la préparation.
            p = R / "runs/roles_autonomes_bp35_fige1/N1/partie"
            ref = np.load(p.with_suffix(".npz"))
            rj = json.loads(p.with_suffix(".json").read_text())
            learn = json.loads((R / "runs/bp35_navigation_visible_reprise1/apprentissage.json").read_text())
            np.savez_compressed(folder / "reference.npz", images=ref["images"])
            save(
                folder / "reference.json",
                {"actions": rj["actions"], "cassables": sorted({p["surface"] for p in learn["preuves_clics"]})},
            )
            offer = [3, 4, 6]
            paid = 16
        save(
            folder / "prefixe.json",
            {
                "actions": actions,
                "issues": [issue_sdk(r["state"], r["levels_completed"], baseline) for r in rows],
                "coups_payes": paid,
                "offre": offer,
                "source": str(src),
                "prefixe_uniquement": True,
            },
        )
    receipts = []
    for name, *_ in cases:
        folder = out / name
        result = subprocess.run(
            [sys.executable, __file__, "--worker", str(folder)], capture_output=True, text=True, timeout=90, check=False
        )
        save(folder / "execution.json", {"code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode:
            raise RuntimeError(result.stderr)
        report = json.loads((folder / "decision.json").read_text())
        receipts.append(
            {
                "jeu": name,
                "statut": report["statut"],
                "incertitudes": report["incertitudes"],
                "experience": report.get("experience"),
                "secondes": report["secondes"],
                "sdk": 0,
            }
        )
    save(out / "bilan.json", receipts)
    save(
        out / "empreintes_entrees.json",
        {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob("prefixe.*")},
    )
    print(json.dumps([{"jeu": r["jeu"], "statut": r["statut"]} for r in receipts]))


if __name__ == "__main__":
    main()
