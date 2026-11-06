"""Essai de développement : navigation partielle apprise sur observations archivées."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from boucle_objets_variables import LaboP1
from navigation_gravite_visible import NavigationVisible

R = Path(__file__).resolve().parent


def sauver(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2, default=lambda v: int(v)))


def decalage(a, b, palette, bord=63):
    """Translation verticale apparente du décor, sans accès au monde caché."""
    candidats = []
    for dy in range(-36, 37):
        lo = max(0, -dy)
        limite = min(a.shape[0], b.shape[0]) if bord is None else bord
        hi = min(limite, limite - dy)
        aa = a[lo:hi]
        bb = b[lo + dy : hi + dy]
        masque = ~np.isin(aa, list(palette)) & ~np.isin(bb, list(palette))
        err = float(np.mean(aa[masque] != bb[masque]))
        candidats.append((err, abs(dy), dy))
    err, _, dy = min(candidats)
    return dy, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--reprendre", type=Path)
    args = ap.parse_args()
    out = args.sortie
    out.mkdir(parents=True, exist_ok=False)
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), R / "navigation_gravite_visible.py"]}
    sauver(out / "sources.json", sources)
    prefix = R / "runs/roles_autonomes_bp35_fige1/N1/partie"
    z = np.load(prefix.with_suffix(".npz"))
    j = json.loads(prefix.with_suffix(".json").read_text())
    m = NavigationVisible(z["images"], j["actions"])
    archive = Path("/Users/ts/models/chrysalide3/experiments/G/couverture/pub_generique/bp35/N1/partie")
    old = np.load(archive.with_suffix(".npz"))
    jold = json.loads(archive.with_suffix(".json").read_text())
    preuves = m.apprendre_clics(old["images"][:13], jold["actions"][:12])
    sauver(
        out / "apprentissage.json",
        {
            "prefixe": str(prefix),
            "archive_clics": str(archive),
            "actions_prefixe": 4,
            "actions_archive_lues": 12,
            "preuves_clics": preuves,
            "palette": sorted(m.palette),
            "pas": m.pas,
            "libre": m.sol,
            "assistance": "famille de modèle choisie par Codex après lecture du rapport humain; pas transfert aveugle",
        },
    )
    lab = LaboP1("bp35", 1, "/Users/ts/models/chrysalide3/experiments/G/publics20c", out / "N1/partie")
    start = time.monotonic()
    journal = []
    vus = set()
    statut = "budget"
    raison = None
    try:
        if args.reprendre:
            oldrun = args.reprendre
            frames = np.load(oldrun / "N1/partie.npz")
            for i in range(1, len(frames["images"])):
                action = json.loads((oldrun / f"prediction_{i:02d}.json").read_text())["action"]
                image, film = lab.play(action, purpose="restauration_comptee")
                if not np.array_equal(image, frames["images"][i]) or not np.array_equal(film, frames[f"film_{i}"]):
                    raise ValueError("Restauration divergente")
            sauver(out / "restauration.json", {"coups": len(lab.rows), "images_films_identiques": True})
        for k in range(len(lab.rows), 40):
            if time.monotonic() - start > 120:
                break
            p = json.loads(json.dumps(m.proposer(lab.image), default=int))
            key = (hashlib.sha256(lab.image[:-1].tobytes()).hexdigest(), str(p["action"]))
            if key in vus:
                statut = "cycle"
                break
            vus.add(key)
            sauver(out / f"prediction_{k + 1:02d}.json", p)
            before = lab.image.copy()
            image, film = lab.play(p["action"], purpose="plan_local_un_coup_puis_reobservation")
            row = {"coup": len(lab.rows), "decision": p, "frames": len(film), "sdk": lab.rows[-1]}
            journal.append(row)
            if lab.finished:
                statut = "victoire_niveau_reelle" if lab.won else "defaite_reelle"
                break
            dy, err = decalage(before, image, m.palette)
            observed = m.position(image)
            cell = p["position_suivante_locale"]
            ox, oy = p["origine"]
            s = m.pas
            predicted = (ox + cell[0] * s + s // 2, oy + cell[1] * s + s // 2 + dy)
            row.update(
                decalage_y=dy,
                erreur_decor=err,
                position_predite=predicted,
                position_observee=observed,
                position_conforme=predicted == observed,
            )
            sauver(out / "journal.json", journal)
            if predicted != observed:
                statut = "divergence_position"
                break
    except (ValueError, KeyError, IndexError, RuntimeError, TypeError) as e:
        statut = "refus"
        raison = f"{type(e).__name__}: {e}"
    finally:
        sauver(out / "journal.json", journal)
        b = {
            "statut": statut,
            "raison": raison,
            "coups_reels": len(lab.rows),
            "initialisations": 1,
            "niveaux_gagnes": int(lab.won),
            "jeu_entier_gagne": lab.partie_gagnee,
            "secondes": time.monotonic() - start,
            "frames": sum(len(f) for f in lab.films.values()),
            "entrainement": False,
            "appels_llm": 0,
            "comparaison": "position avec défilement estimé a posteriori, pas rendu complet validé",
            "sources_inchangees": all(hashlib.sha256((R / n).read_bytes()).hexdigest() == h for n, h in sources.items()),
        }
        sauver(out / "bilan.json", b)
        print(json.dumps(b, ensure_ascii=False))


if __name__ == "__main__":
    main()
