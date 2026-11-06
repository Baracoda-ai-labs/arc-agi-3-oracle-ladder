"""Gel du code avant la mesure tenue à l'écart (g50t N7) : SHA-256 par fichier + global + bibliothèque utilisée.
Refuse d'écraser un FIGE.txt existant."""
import hashlib, json, sys, time
from pathlib import Path

R = Path(__file__).resolve().parent


def main(sortie, biblio):
    out = Path(sortie)
    if out.exists():
        raise SystemExit(f'{out} existe déjà : gel non réécrit')
    fichiers = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(R.glob('*.py'))}
    g = hashlib.sha256(json.dumps(fichiers, sort_keys=True).encode()).hexdigest()
    b = hashlib.sha256(Path(biblio).read_bytes()).hexdigest()
    lignes = [f'gel : {time.strftime("%Y-%m-%dT%H:%M:%S")}', f'code_global_sha256 : {g}', f'bibliotheque : {biblio} {b}',
              'protocole : g50t N7 joué une seule fois, set_level(6) (injection signalée), budget 150, mode complet,',
              '            bibliothèque issue de N6, aucune lecture préalable des traces N7 d\'Astra, aucune réparation après mesure.']
    lignes += [f'{k} {v}' for k, v in fichiers.items()]
    out.write_text('\n'.join(lignes) + '\n')
    print('\n'.join(lignes[:3]))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
