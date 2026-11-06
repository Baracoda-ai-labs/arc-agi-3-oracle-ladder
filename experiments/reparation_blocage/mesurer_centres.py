"""ABBA séquentiel dans quatre processus neufs ; calculs sur trace seulement."""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent


def worker(mode, sortie):
    if mode == 'prefiltre':
        os.environ['CHRYS_PAQUET_DIAGNOSTIC'] = str(ICI / 'paquet_prefiltre')
        os.environ['CHRYS_SANS_EFFET_PREFILTRE'] = '1'
        os.environ['CHRYS_CENTRES_RAPIDES'] = '1'
    from diagnostiquer_export import diagnostic
    if mode == 'rapide':
        from chrysalide.arc3.logique import theorie
        spec = importlib.util.spec_from_file_location('centres_rapides', ICI / 'code/centres_rapides.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        theorie.centres_motifs = module.centres_motifs
    t0 = time.process_time()
    d = diagnostic()
    d['cpu_total'] = time.process_time() - t0
    d['mode_centres'] = mode
    sortie.write_text(json.dumps(d, ensure_ascii=False, default=repr, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sortie', type=Path)
    ap.add_argument('--worker', choices=['reference', 'rapide', 'prefiltre'])
    ap.add_argument('--base', choices=['reference', 'rapide'], default='reference')
    ap.add_argument('--variante', choices=['rapide', 'prefiltre'], default='rapide')
    a = ap.parse_args()
    if a.worker:
        worker(a.worker, a.sortie)
        return
    a.sortie.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith('CHRYS_')}
    env.update(CHRYS_EXPORT_SANS_EFFET='1', PYTHONHASHSEED='0')
    donnees = []
    for i, mode in enumerate([a.base, a.variante, a.variante, a.base]):
        p = a.sortie / f'{i + 1}-{mode}.json'
        subprocess.run([sys.executable, __file__, str(p), '--worker', mode], env=env, check=True, timeout=120)
        d = json.loads(p.read_text())
        donnees.append(d)
        print(mode, d['cpu_proposition'], d['but'], 'porte', d['porte_corrigee'], flush=True)
    valeurs = {mode: [d['cpu_proposition'] for d in donnees if d['mode_centres'] == mode]
               for mode in (a.base, a.variante)}
    identiques = all((d['but'], d['plan'], d['etapes'], d['porte_corrigee']) ==
                    (donnees[0]['but'], donnees[0]['plan'], donnees[0]['etapes'], donnees[0]['porte_corrigee'])
                    for d in donnees)
    r, o = sum(valeurs[a.base]) / 2, sum(valeurs[a.variante]) / 2
    bilan = {'cpu': valeurs, 'resultats_identiques': identiques, 'reduction_cpu_pourcent': 100 * (r - o) / r}
    (a.sortie / 'bilan.json').write_text(json.dumps(bilan, indent=2) + '\n')
    print(json.dumps(bilan), flush=True)


if __name__ == '__main__':
    main()
