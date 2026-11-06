"""Évite de mélanger modules du dépôt et du paquet expérimental dans pytest."""
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
R = ICI.parents[1]


def main():
    tests = ['test_perception_guidee.py', 'test_objets_variables.py', 'test_apprendre_retour.py', 'test_contact_observe.py', 'test_lecons_python.py', 'test_ontologie_extensible.py', 'test_chaine_coherente.py', 'test_releve_coherente.py', 'test_montecarlo.py',
             'test_contexte_plan.py', 'test_export_retour.py', 'test_centres_rapides.py', 'test_evidence_films.py', 'test_ablation.py', 'test_observateur_cpu.py', 'test_cegar_atms.py', 'test_observateur_harnais.py', 'test_propositions_python.py']
    bootstrap = ('import sys; from pathlib import Path; '
                 f'p=Path({str(ICI / "paquet")!r}); sys.path.insert(0,str(p)); '
                 'from chrysalide.arc3.logique import plan,export_langage; '
                 'assert Path(plan.__file__).is_relative_to(p); '
                 'assert Path(export_langage.__file__).is_relative_to(p); '
                 'print("Modules verifies :",plan.__file__,export_langage.__file__); '
                 'import pytest; sys.exit(pytest.main(sys.argv[1:]))')
    commandes = [[sys.executable, '-c', bootstrap, '-q', *[str(ICI / t) for t in tests]],
                 [sys.executable, '-m', 'pytest', '-q', 'tests/test_theorie_contrats.py',
                  'tests/test_ontologie_formelle.py::test_trois_etages_coherents',
                  'tests/test_ontologie_formelle.py::test_phases_coherentes_avec_les_effets']]
    with (ICI / 'tests_assemblage.txt').open('w') as f:
        for cmd in commandes:
            resultat = subprocess.run(cmd, cwd=R, text=True, capture_output=True, check=False)
            f.write(resultat.stdout + resultat.stderr)
            print(resultat.stdout, end='')
            if resultat.returncode:
                print(resultat.stderr)
                raise SystemExit(resultat.returncode)


if __name__ == '__main__':
    main()
