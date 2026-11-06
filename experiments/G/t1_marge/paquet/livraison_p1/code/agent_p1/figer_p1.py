"""Gel P1 : SHA-256 de chaque fichier du paquet, global, et de la mémoire de départ. Refuse d'écraser."""
import hashlib, json, sys, time
from pathlib import Path

R = Path(__file__).resolve().parent


def main(sortie, memoire_depart):
    out = Path(sortie)
    if out.exists():
        raise SystemExit(f'{out} existe déjà')
    f = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(R.glob('*.py'))}
    g = hashlib.sha256(json.dumps(f, sort_keys=True).encode()).hexdigest()
    m = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(memoire_depart).glob('*.json'))}
    L = [f'gel : {time.strftime("%Y-%m-%dT%H:%M:%S")}', f'code_global_sha256 : {g}',
         f'memoire_depart : {memoire_depart}'] + [f'  {k} {v}' for k, v in m.items()] + ['fichiers :'] + \
        [f'  {k} {v}' for k, v in f.items()]
    out.write_text('\n'.join(L) + '\n'); print('\n'.join(L[:4]))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
