"""Copie explicite du harnais archivé, jamais le harnais sûr ni un notebook soumis."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def transformer(texte):
    assert "CHRYS_OBSERVATEUR_CPU" not in texte, "Harnais deja transforme"
    appel = '            self._play_inner()\n'
    assert texte.count(appel) == 1
    bloc = '''            if os.environ.get("CHRYS_OBSERVATEUR_CPU") == "1":
                try:
                    from observateur_harnais import installer
                    self._chrys_observateur_cpu = installer(self, run.game_id)
                except Exception as erreur_observation:
                    self._chrys_observateur_erreur = type(erreur_observation).__name__
            self._play_inner()
'''
    texte = texte.replace(appel, bloc)
    fin = '''        finally:
            if gate is not None:
                gate.release()
'''
    assert texte.count(fin) == 1
    texte = texte.replace(fin, fin + '''            liaison = getattr(self, "_chrys_observateur_cpu", None)
            if liaison is not None:
                try:
                    liaison.fermer()
                except Exception as erreur_observation:
                    self._chrys_observateur_erreur = type(erreur_observation).__name__
''')
    compile(texte, '<harnais-observateur>', 'exec')
    return texte


def main():
    p = argparse.ArgumentParser(); p.add_argument('--source', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True); a = p.parse_args()
    source = a.source / 'inference/framework/solver.py'
    texte = source.read_text()
    nouveau = transformer(texte)
    if a.destination.exists():
        raise FileExistsError(a.destination)
    if a.source.resolve() == a.destination.resolve():
        raise ValueError('Destination distincte requise')
    shutil.copytree(a.source, a.destination, symlinks=True)
    cible = a.destination / 'inference/framework/solver.py'
    cible.write_text(nouveau)
    rapport = {'source': str(source), 'destination': str(cible),
               'source_sha256': hashlib.sha256(texte.encode()).hexdigest(),
               'destination_sha256': hashlib.sha256(nouveau.encode()).hexdigest(),
               'condition': 'CHRYS_OBSERVATEUR_CPU=1', 'aucun_lancement': True}
    ici = Path(__file__).resolve().parent
    (ici / 'harnais_observateur_prepare.json').write_text(json.dumps(rapport, indent=2) + '\n')
    print(json.dumps(rapport))


if __name__ == '__main__':
    main()
