"""Rassemble les sorties conservées sans déplacer ni écraser les enregistrements."""
import json
import os
import subprocess
from pathlib import Path

from comparer_passages import comparer

ICI = Path(__file__).resolve().parent


def collecter():
    reprises = json.loads((ICI / 'reprises_t4.json').read_text())
    etats, assembles = [], []
    for d in reprises:
        src, nouveau = (ICI / 'runs' / d[k] for k in ('source', 'reprise'))
        faits = json.loads((src / 'resume.json').read_text())
        fin = json.loads((nouveau / 'resume.json').read_text()) if (nouveau / 'resume.json').exists() else {}
        try:
            os.kill(d['pid'], 0)
            actif = True
        except ProcessLookupError:
            actif = False
        except PermissionError:
            observation = subprocess.run(['/usr/sbin/lsof', '-t', str(nouveau / 'execution.log')],
                                         capture_output=True, text=True, check=False)
            actif = True if observation.returncode == 0 and observation.stdout.strip() else (
                False if observation.returncode == 1 and not observation.stderr.strip() else None)
        etats.append({'source': d['source'], 'termines': len(faits) + len(fin), 'attendus': 104,
                          'actif': actif, 'coups_interrompus': d['coups_interrompus']})
        if len(faits) + len(fin) != 104:
            continue
        assert not (faits.keys() & fin.keys())
        prefixe = {}
        for nom, longueur in d['interruptions'].items():
            old = json.loads((src / nom).read_text())['rows']
            new = json.loads((nouveau / nom).read_text())['rows']
            prefixe[nom] = [x['action'] for x in old] == [x['action'] for x in new[:longueur]]
        destination = ICI / 'runs' / (d['source'] + '_assemble')
        destination.mkdir(exist_ok=True)
        for racine, resume in [(src, faits), (nouveau, fin)]:
            for jeu in resume:
                lien = destination / jeu
                if not lien.exists():
                    lien.symlink_to(racine / jeu, target_is_directory=True)
                assert lien.resolve() == (racine / jeu).resolve()
        (destination / 'resume.json').write_text(json.dumps(faits | fin, indent=2) + '\n')
        etats[-1]['prefixes_reproduits'] = prefixe
        assembles.append(destination)
    bilan = {'etats': etats, 'complet': len(assembles) == 2}
    if bilan['complet']:
        bilan['comparaison'] = comparer(*assembles)
        bilan['comparaison']['coups_interrompus_total'] = sum(x['coups_interrompus'] for x in reprises)
        bilan['limite_reprise'] = 'Mémoire persistante restaurée ; processus neufs au jeu y077, caches volatils non restaurés. Confirmation fraîche requise pour un éventuel gain.'
        (ICI / 'bilan_t4_final.json').write_text(json.dumps(bilan, ensure_ascii=False, indent=2) + '\n')
    return bilan


if __name__ == '__main__':
    d = collecter()
    print(json.dumps({k: v for k, v in d.items() if k != 'comparaison'}, ensure_ascii=False))
    if d['complet']:
        print(json.dumps({k: v for k, v in d['comparaison'].items() if k != 'niveaux'}, ensure_ascii=False))
