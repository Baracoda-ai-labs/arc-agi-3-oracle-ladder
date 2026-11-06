"""Un bras à la fois, sans témoins ; sortie neuve, manifeste et commandes sauvegardés."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from preparer import ICI, PAQUET, REF, preparer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nom")
    ap.add_argument("--jeux", type=Path, required=True)
    ap.add_argument("--jeu", nargs="+", required=True)
    ap.add_argument("--graine", type=int, default=0)
    ap.add_argument('--memoire-reprise', type=Path)
    configurations = {'eteint': ('0', '0', '0'), 'reparation': ('1', '0', '0'),
                      'locale': ('2', '0', '0'), 'export': ('0', '1', '0'),
                      'locale_export': ('2', '1', '0'), 'export_rapide': ('0', '1', '1'),
                      'locale_rapide': ('2', '1', '1'), 'locale_terminale': ('2', '1', '1'),
                      'locale_contexte': ('2', '1', '1'), 'coherente': ('0', '1', '1'), 'coherente_cegar_atms': ('0', '1', '1')}
    ap.add_argument("--bras", choices=['reference', *configurations], required=True)
    a = ap.parse_args()
    interdits = {"vc33", "tu93", "wa30", "s5i5", "cn04"}
    if any(g[:4] in interdits for g in a.jeu) or any((a.jeux / g).exists() for g in interdits):
        raise SystemExit("REFUS : témoins présents")
    sha = preparer()
    sortie = ICI / "runs" / a.nom
    sortie.mkdir(parents=True, exist_ok=False)
    memoire_sha = {}
    if a.memoire_reprise:
        shutil.copytree(a.memoire_reprise, sortie / 'memoire_inter_jeux')
        memoire_sha = {str(p.relative_to(a.memoire_reprise)): __import__('hashlib').sha256(p.read_bytes()).hexdigest()
                       for p in a.memoire_reprise.rglob('*') if p.is_file()}
    env = {k: v for k, v in os.environ.items() if not k.startswith("CHRYS_") and k != "GEL27_TEMOINS"}
    env.update(PYTHON=sys.executable, PYTHONHASHSEED="0")
    if a.bras != "reference":
        rep, export, rapide = configurations[a.bras]
        env.update(CHRYS_REPARATION_BLOCAGE=rep, CHRYS_EXPORT_SANS_EFFET=export, CHRYS_CENTRES_RAPIDES=rapide)
        if a.bras in ('locale_terminale', 'locale_contexte'):
            env['CHRYS_REPARATION_TERMINALE'] = '1'
        if a.bras == 'locale_contexte':
            env['CHRYS_PLAN_CONTEXTE_COMPLET'] = '1'
        if a.bras in ('coherente', 'coherente_cegar_atms'):
            env.update(CHRYS_CHAINE_COHERENTE='1', CHRYS_PLAN_CONTEXTE_COMPLET='1')
        if a.bras == 'coherente_cegar_atms':
            env.update(CHRYS_CHAINE_ATMS='1', CHRYS_CHAINE_CEGAR='1')
    paquet = REF if a.bras == "reference" else PAQUET
    cmd = ["bash", str(paquet / "lancer.sh"), str(a.jeux.resolve()), str(sortie),
           "--graine", str(a.graine), "--jeu", *a.jeu]
    (sortie / "commande.json").write_text(json.dumps({"cmd": cmd, "bras": a.bras, "sha_experimental": sha,
        'memoire_reprise': str(a.memoire_reprise) if a.memoire_reprise else None, 'memoire_sha256': memoire_sha}, indent=2))
    with (sortie / "execution.log").open("w") as f:
        r = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, check=False)
    raise SystemExit(r.returncode)


if __name__ == "__main__":
    main()
