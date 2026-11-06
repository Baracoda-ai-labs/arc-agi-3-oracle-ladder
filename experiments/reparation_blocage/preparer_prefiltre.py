"""Copie indépendante : ne réécrit jamais le paquet du banc en cours."""
import hashlib
import shutil
from pathlib import Path

ICI = Path(__file__).resolve().parent


def preparer():
    src, dst = ICI / 'paquet', ICI / 'paquet_prefiltre'
    if dst.exists():
        raise FileExistsError('Copie déjà préparée ; ne pas écraser une version mesurée')
    lignes = (src / 'SHA256SUMS').read_text().splitlines()
    for ligne in lignes:
        h, nom = ligne.split(maxsplit=1)
        assert hashlib.sha256((src / nom).read_bytes()).hexdigest() == h, nom
    shutil.copytree(src, dst)
    chemin = 'chrysalide/arc3/logique/theorie.py'
    texte = (dst / chemin).read_text()
    needle = '        if self.sans_effet and not isinstance(action, tuple) and self.cle_sans_effet(monde, action, taille) in self.sans_effet:\n'
    assert texte.count(needle) == 1
    texte = texte.replace(needle, '        if (self.sans_effet and not isinstance(action, tuple)\n'
                           '                and (os.environ.get("CHRYS_SANS_EFFET_PREFILTRE") != "1"\n'
                           '                     or _sans_effet_possible(self, monde, action))\n'
                           '                and self.cle_sans_effet(monde, action, taille) in self.sans_effet):\n')
    texte = texte.replace('import os\n', 'import os\nfrom chrysalide.arc3.logique.prefiltre_sans_effet import possible as _sans_effet_possible\n', 1)
    (dst / chemin).write_text(texte)
    helper = 'chrysalide/arc3/logique/prefiltre_sans_effet.py'
    shutil.copy2(ICI / 'code/prefiltre_sans_effet.py', dst / helper)
    noms = [ligne.split(maxsplit=1)[1] for ligne in lignes] + [helper]
    manifest = ''.join(f'{hashlib.sha256((dst / n).read_bytes()).hexdigest()}  {n}\n' for n in sorted(noms))
    (dst / 'SHA256SUMS').write_text(manifest)
    sha = hashlib.sha256(manifest.encode()).hexdigest()
    (dst / 'EMPREINTE.txt').write_text(f'Copie expérimentale indépendante préfiltre ; jamais soumise.\nglobal {sha}\n')
    return sha


if __name__ == '__main__':
    print(preparer())
