"""Reprise au jeu suivant la dernière sauvegarde complète, sans écrasement."""
import json
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
JEUX = Path('/Users/ts/models/chrysalide3_verrou/generateur/t4/environment_files')


def main():
    attendus = sorted(p.name for p in JEUX.iterdir() if p.is_dir())
    assert len(attendus) == 104 and all(j.startswith('y') and j[1:].isdigit() for j in attendus)
    preparations = []
    for nom, bras in [('t4_ref_g0', 'reference'), ('t4_rapide_g0', 'export_rapide')]:
        src = ICI / 'runs' / nom
        r = subprocess.run(['/usr/sbin/lsof', '-t', str(src / 'execution.log')], capture_output=True, text=True, check=False)
        if r.returncode != 1 or r.stdout.strip() or r.stderr.strip():
            raise RuntimeError(f'{nom}: activité ou inspection incertaine ; reprise refusée')
        faits = json.loads((src / 'resume.json').read_text())
        assert list(faits) == attendus[:len(faits)], 'ordre non préfixe'
        reste = attendus[len(faits):]
        assert reste
        # Si des niveaux ont déjà été gagnés dans le jeu incomplet, le checkpoint mémoire
        # serait situé au milieu de ce jeu : une reprise depuis RESET ne serait pas identique.
        interruption = {}
        for jeu in reste:
            assert not (src / jeu / 'resultat.json').exists(), f'{jeu}: checkpoint intermédiaire non pris en charge'
            for partie in (src / jeu).glob('N*/partie.json'):
                interruption[str(partie.relative_to(src))] = len(json.loads(partie.read_text())['rows'])
        nouveau = nom + '_reprise1'
        assert not (ICI / 'runs' / nouveau).exists()
        cmd = [sys.executable, str(ICI / 'mesurer.py'), nouveau, '--bras', bras, '--jeux', str(JEUX),
               '--jeu', *reste, '--graine', '0', '--memoire-reprise', str(src / 'memoire_inter_jeux')]
        preparations.append({'source': nom, 'reprise': nouveau, 'cmd': cmd, 'interruptions': interruption,
                                  'coups_interrompus': sum(interruption.values()), 'jeux_termines': len(faits)})
    for d in preparations:
        log = ICI / 'runs' / (d['reprise'] + '.supervision.log')
        with log.open('x') as f:
            p = subprocess.Popen(d['cmd'], stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                                 start_new_session=True, cwd=ICI.parents[1])
        d['pid'] = p.pid
        d['supervision'] = str(log)
    (ICI / 'reprises_t4.json').write_text(json.dumps(preparations, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps([{k: d[k] for k in ('source', 'reprise', 'pid', 'jeux_termines', 'coups_interrompus')}
                      for d in preparations], ensure_ascii=False))


if __name__ == '__main__':
    main()
