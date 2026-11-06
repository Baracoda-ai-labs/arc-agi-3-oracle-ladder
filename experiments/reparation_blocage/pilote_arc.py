import subprocess
import sys
from pathlib import Path

p=Path("experiments/reparation_blocage")
for nom,bras in [("arc_blocage_controle_g1","export_rapide"),("arc_blocage_locale_g1","locale_rapide")]:
 cmd=[sys.executable,str(p/"mesurer.py"),nom,"--jeux","/Users/ts/models/chrysalide3/experiments/G/publics20c","--jeu","m0r0","sp80","--graine","1","--bras",bras]
 r=subprocess.run(cmd, check=False)
 if r.returncode: raise SystemExit(r.returncode)
subprocess.run([sys.executable,str(p/"comparer_passages.py"),str(p/"runs/arc_blocage_controle_g1"),str(p/"runs/arc_blocage_locale_g1"),str(p/"bilan_arc_blocage_g1.json")],check=True)
