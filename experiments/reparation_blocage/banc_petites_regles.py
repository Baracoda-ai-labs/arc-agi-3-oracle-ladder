"""Nouvelle condition sur les seuls préfixes déjà isolés ; pas de SDK."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parent


def empreintes(paths):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    out = Path(sys.argv[1]).resolve()
    src = R / "runs/controleur_trois_archives_fige1"
    out.mkdir(parents=True, exist_ok=False)
    sources = sorted(R.glob("*.py"))
    initial = empreintes(sources)
    rows = []
    for game in ("bp35", "ka59", "ar25"):
        dest = out / game
        dest.mkdir()
        for name in ("prefixe.json", "prefixe.npz", "reference.json", "reference.npz"):
            p = src / game / name
            if p.exists():
                shutil.copyfile(p, dest / name)
        inputs = empreintes(sorted(dest.glob("*")))
        run = subprocess.run(
            [sys.executable, str(R / "banc_controleur_archives.py"), "--worker", str(dest), "--petites-regles"],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        (dest / "execution.json").write_text(json.dumps({"code": run.returncode, "stdout": run.stdout, "stderr": run.stderr}))
        assert run.returncode == 0, run.stderr
        assert inputs == empreintes([Path(p) for p in inputs])
        (dest / "entrees_sha256.json").write_text(json.dumps(inputs, indent=2))
        report = json.loads((dest / "decision.json").read_text())
        p = report["petites_regles"]
        rows.append(
            {
                "jeu": game,
                "statut": report["statut"],
                "proposeur": p["statut"],
                "generes": p.get("generes", 0),
                "compatibles": p.get("compatibles", 0),
                "experiences": len(p["experiences"]),
                "separatrices": sum(e["statut"] == "experience_discriminante_simulee" for e in p["experiences"]),
                "secondes": report["secondes"],
                "sdk": 0,
            }
        )
    assert initial == empreintes(sources)
    (out / "sources_sha256.json").write_text(json.dumps(initial, indent=2))
    (out / "bilan.json").write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
