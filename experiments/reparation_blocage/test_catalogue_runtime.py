"""La garde existante lie le catalogue au runtime exact, sans alias permissif."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

R = Path(__file__).resolve().parent
ROOT = R.parents[1]
WORKER = r'''
import json,tempfile
from pathlib import Path
from chaine_coherente import Chaine
from chrysalide.langue import ontologie_formelle,theorie_contrats
c=object.__new__(Chaine)
r={'initial':c.catalogue(),'source_sha256':c.ontologie_sha(),'contrats_sha256':c.contrats_sha()}
with tempfile.TemporaryDirectory() as d:
 for module,token in [(ontologie_formelle,'PHASES ='),(theorie_contrats,'TABLE =')]:
  original=module.__file__
  # Mutation réelle de copie source, sans toucher le paquet sûr ou le runtime actif.
  p=Path(d)/(module.__name__.split('.')[-1]+'.py')
  p.write_text(Path(original).read_text()+'\n'+('PHASES[1] = \"phase_mutante\"' if token.startswith('PHASES') else 'TABLE.pop(\"moves\")')+'\n')
  module.__file__=str(p)
  r[module.__name__]=c.catalogue()
  module.__file__=original
 r['restaure']=c.catalogue()
print(json.dumps(r))
'''

class CatalogueRuntime(unittest.TestCase):
    def test_runtime_exact_and_mutated_sources(self):
        for package, admissible in [(R/'paquet', True), (ROOT/'experiments/GEL27_moteur_seul_v3', False)]:
            env = dict(os.environ, PYTHONPATH=f'{package}:{R}', PYTHONDONTWRITEBYTECODE='1')
            p = subprocess.run([sys.executable, '-B', '-c', WORKER], env=env, cwd=package, capture_output=True, text=True, timeout=10, check=True)
            result = json.loads(p.stdout)
            self.assertEqual(result['initial'], admissible)
            self.assertEqual(result['restaure'], admissible)
            for module in ['ontologie_formelle', 'theorie_contrats']:
                self.assertFalse(result['chrysalide.langue.'+module])
            for key, filename in [('source_sha256','ontologie_formelle.py'),('contrats_sha256','theorie_contrats.py')]:
                self.assertEqual(result[key], hashlib.sha256((package/'chrysalide/langue'/filename).read_bytes()).hexdigest())

if __name__ == '__main__':
    unittest.main()
