"""Source unique Python → catalogue neutre pour vues SKOS/SHACL."""
import hashlib
import json
from pathlib import Path

from chrysalide.langue.ontologie_formelle import MECANISMES, PHASES, VERSION
from chrysalide.langue.roles import roles_ontologie
from chrysalide.langue.theorie_contrats import TABLE

ICI = Path(__file__).resolve().parent


def main():
    source = ICI.parents[1] / 'chrysalide/langue/ontologie_formelle.py'
    roles = roles_ontologie()
    for m in MECANISMES.values():
        assert m['phase'] in PHASES
        assert set(m['roles']) <= set(roles)
    catalogue = {'version': VERSION, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                 'contrats_sha256': hashlib.sha256(source.with_name('theorie_contrats.py').read_bytes()).hexdigest(),
                 'observations': sorted({c[1] for c in TABLE.values() if c[0] == 'observation'}),
                 'mecanismes': MECANISMES, 'phases': PHASES, 'roles': roles}
    (ICI / 'catalogue_ontologie.json').write_text(json.dumps(catalogue, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'mecanismes': len(MECANISMES), 'roles': len(catalogue['roles']), 'version': VERSION}))


if __name__ == '__main__':
    main()
