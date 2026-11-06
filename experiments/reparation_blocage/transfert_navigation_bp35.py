"""N1 uniquement pour accès ; transfert vers N2 sans solution ni état interne."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from boucle_navigation_visible import sauver
from boucle_objets_variables import LaboP1
from hypotheses_navigation import HypothesesNavigation
from issues_observees import issue_sdk
from navigation_gravite_visible import NavigationVisible
from neuronal_navigation import consulter, reparer_perception

R = Path(__file__).resolve().parent


def apprendre():
    prefix = R / "runs/roles_autonomes_bp35_fige1/N1/partie"
    m = NavigationVisible(
        np.load(prefix.with_suffix(".npz"))["images"], json.loads(prefix.with_suffix(".json").read_text())["actions"]
    )
    source = R / "runs/bp35_navigation_visible_reprise1/N1/partie"
    z = np.load(source.with_suffix(".npz"))
    j = json.loads(source.with_suffix(".json").read_text())
    m.apprendre_clics(z["images"][:-1], j["actions"][:-1])
    h = HypothesesNavigation(m)
    for i, a in enumerate(j["actions"][:-1]):
        h.observer(z["images"][i], a, z["images"][i + 1], z[f"film_{i + 1}"])
    # Transfert du rôle candidat touché lors de la victoire N1, pas coordonnées.
    before = z["images"][-2]
    p = m.proposer(before)
    cell = p["position_suivante_locale"]
    s = m.pas
    ox, oy = p["origine"]
    patch = before[oy + cell[1] * s : oy + (cell[1] + 1) * s, ox + cell[0] * s : ox + (cell[0] + 1) * s]
    buts = {
        int(c) for c in np.unique(patch) if c not in m.palette | m.cassables | {m.sol} and 1 < int((before == c).sum()) <= s * s
    }
    return m, h, buts, z, j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    out = ap.parse_args().sortie
    out.mkdir(parents=True, exist_ok=False)
    files = [
        Path(__file__),
        R / "hypotheses_navigation.py",
        R / "navigation_gravite_visible.py",
        R / "neuronal_navigation.py",
        R / "perception_navigation.py",
        R / "reprise_flux_27b.py",
        R / "atms.py",
        R / "boucle_navigation_visible.py",
    ]
    sources = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    sauver(out / "sources.json", sources)
    m, h, buts, z, j = apprendre()
    sauver(
        out / "transfert.json",
        {
            "selection_sur_traces_N1": h.actives(),
            "comparaisons_N1": h.journal,
            "buts_candidats_transferes": sorted(buts),
            "scope": "gravité réouverte au niveau suivant ; clics hérités mais réfutables",
            "catalogue_fourni": True,
            "solution_N2_fournie": False,
        },
    )
    clics = tuple(sorted({h.catalogue[n][1] for n in h.actives()}))
    if not clics:
        raise ValueError("Aucun modèle N1 compatible, refus avant SDK")
    lab = LaboP1("bp35", 1, "/Users/ts/models/chrysalide3/experiments/G/publics20c", out / "N1/partie")
    access = lab
    start = time.monotonic()
    journal = []
    calls = 0
    statut = "budget"
    error = None
    vus = set()
    try:
        for i, a in enumerate(j["actions"]):
            image, film = lab.play(a, purpose="acces_N2_seulement")
            if not np.array_equal(image, z["images"][i + 1]) or not np.array_equal(film, z[f"film_{i + 1}"]):
                raise ValueError("Accès N1 différent de la trace ; arrêt")
        if not lab.won:
            raise ValueError("Accès N2 non confirmé")
        lab = lab.next_level(out / "N2/partie")
        h = HypothesesNavigation(m, buts, clics)
        avant = None
        film = None
        known = set(m.palette) | m.cassables | {m.sol} | buts
        known.update(c for c in np.unique(m.images[0]) if int((m.images[0] == c).sum()) > m.pas * m.pas)
        for k in range(60):
            if time.monotonic() - start > 300:
                break
            offre = [int(getattr(a, "value", a)) for a in lab.actions_disponibles]
            try:
                decision = json.loads(json.dumps(h.proposer(lab.image, offre), default=int))
            except ValueError as exc:
                if "Silhouette" not in str(exc) or calls >= 12:
                    raise
                calls += 1
                repair = reparer_perception(m, lab.image, out / "neuronal", calls)
                sauver(out / f"reparation_perception_{k:02d}.json", repair)
                decision = json.loads(json.dumps(h.proposer(lab.image, offre), default=int))
            novel = set(map(int, np.unique(lab.image))) - known
            uncertain = len(h.actives()) > 1 or bool(novel)
            if uncertain:
                if calls >= 12:
                    statut = "budget_neuronal"
                    break
                calls += 1
                neural = consulter(lab.image, avant, film, decision, out / "neuronal", calls)
                decision["neuronal"] = neural
                decision["action"] = neural["action"]
                # Une suggestion ne valide ni une couleur ni une mécanique inconnue.
            key = (hashlib.sha256(lab.image[:-1].tobytes()).hexdigest(), str(decision["action"]))
            if key in vus:
                statut = "cycle"
                break
            vus.add(key)
            decision["incertitude"] = {"plusieurs_modeles": len(h.actives()) > 1, "couleurs_nouvelles": sorted(novel)}
            sauver(out / f"decision_N2_{k + 1:02d}.json", decision)
            avant = lab.image.copy()
            image, film = lab.play(decision["action"], purpose=decision["raison"])
            row = {"coup": len(lab.rows), "decision": decision, "sdk": lab.rows[-1], "frames": len(film)}
            journal.append(row)
            row["verification"] = h.observer(
                avant,
                decision["action"],
                image,
                film,
                issue_observee=issue_sdk(lab.rows[-1]["state"], lab.rows[-1]["levels_completed"], lab.completed_baseline),
            )
            sauver(out / "journal.json", journal)
            sauver(out / "atms.json", h.atms.rapport())
            if lab.finished:
                statut = "victoire_N2_reelle" if lab.won else "defaite_N2_reelle"
                break
            sauver(out / "journal.json", journal)
            sauver(out / "atms.json", h.atms.rapport())
            if not h.actives():
                # Réfutation totale : diagnostic neuronal conservé, aucune correction manuelle dans l'essai.
                if calls < 12:
                    calls += 1
                    diag = {
                        "hypotheses": [],
                        "raison": "tous_modeles_refutes",
                        "verification": row["verification"],
                        "experiences_candidates": [
                            {"action": decision["action"], "question": "diagnostic seulement, ne sera pas exécutée"}
                        ],
                    }
                    row["diagnostic_neuronal"] = consulter(image, avant, film, diag, out / "neuronal", calls)
                statut = "catalogue_refute"
                break
    except (ValueError, TypeError, KeyError, IndexError, RuntimeError) as e:
        statut = "refus"
        error = repr(e)
    finally:
        sauver(out / "journal.json", journal)
        sauver(out / "atms.json", h.atms.rapport())
        b = {
            "statut": statut,
            "erreur": error,
            "coups_acces_N1": len(access.rows),
            "coups_N2": len(lab.rows) if lab is not access else 0,
            "coups_reels": len(access.rows) + (len(lab.rows) if lab is not access else 0),
            "initialisations": 1,
            "N2_gagne": lab is not access and lab.won,
            "jeu_entier_gagne": lab.partie_gagnee,
            "appels_neuronaux": calls,
            "secondes": time.monotonic() - start,
            "hypotheses_finales": h.actives(),
            "sources_inchangees": all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == s for p, s in sources.items()),
        }
        sauver(out / "bilan.json", b)
        print(json.dumps(b))


if __name__ == "__main__":
    main()
