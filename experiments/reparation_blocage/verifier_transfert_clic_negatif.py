"""Différentiel causal avec décisions fd3c3bb7 archivées, aucun SDK."""
import hashlib
import json
import signal
import subprocess
import time
from pathlib import Path

import numpy as np
from chaine_agent_integree import AgentIntegre
from issues_observees import issue_sdk
from boucle_agent_integree import empreintes

R = Path(__file__).resolve().parent
ROOT = R.parents[1]
OUT = R / 'runs/transfert_clic_negatif_traces3'

def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=int))

def run():
    OUT.mkdir(exist_ok=False)
    for name in ['ar25', 'm0r0', 'cd82']:
        source = R / 'runs/decouverte_courte_arc1' / name
        out = OUT / name
        out.mkdir()
        # Valider que la référence archivée est réellement le code demandé.
        hashes = json.loads((source / 'sources.json').read_text())
        differences = []
        for path, sha in hashes.items():
            relative = str(Path(path).relative_to(ROOT))
            blob = subprocess.run(['git', 'show', f'fd3c3bb7:{relative}'], cwd=ROOT, capture_output=True)
            old = blob.stdout if blob.returncode == 0 else Path(path).read_bytes()
            if hashlib.sha256(old).hexdigest() != sha:
                differences.append(relative)
        assert not differences, differences
        save(out / 'reference_verifiee.json', {'commit': 'fd3c3bb7', 'sources': hashes})
        archive = np.load(source / 'N1/partie.npz')
        rows = json.loads((source / 'N1/partie.json').read_text())['rows']
        images = archive['images']
        actions = [r['action'] for r in rows]
        films = [archive[f'film_{i+1}'] for i in range(len(rows))]
        issues = [issue_sdk(r['state'], r['levels_completed'], 0) for r in rows]
        offre = json.loads((source / 'decision_000/decision.json').read_text())['acquisition']['questions_couvertes']['commandes_non_essayees']
        agent = AgentIntegre(images[:1], [], [], [], decouverte_courte=True)
        checks = []
        started = time.monotonic()
        def timeout(sig, frame):
            raise TimeoutError('60s par cas')
        signal.signal(signal.SIGALRM, timeout)
        signal.setitimer(signal.ITIMER_REAL, 60)
        status = 'incomplet'
        try:
            for n, actual in enumerate(actions):
                ddir = out / f'decision_{n:03d}'
                ddir.mkdir()
                prefix = ddir / 'prefixe'
                np.savez_compressed(prefix.with_suffix('.npz'), images=images[:n+1], **{f'film_{i+1}': films[i] for i in range(n)})
                save(prefix.with_suffix('.json'), {'rows': [{'action': a} for a in actions[:n]]})
                decision = agent.decider(offre, ddir, prefix, secondes=min(10, 60-(time.monotonic()-started)))
                save(ddir / 'decision.json', decision)
                old = json.loads((source / f'decision_{n:03d}/decision.json').read_text())
                assert old['actions'][0] == actual
                same = decision.get('actions', [])[:1] == [actual]
                checks.append({'prefixe': n, 'ancienne_action': actual, 'nouvelle_action': decision.get('actions'), 'identique': same, 'modeles': list(agent.chaines)})
                if not same:
                    status = 'premiere_difference'
                    break
                agent.observer(actual, images[n+1], films[n], issues[n])
            else:
                status = 'trajectoire_archivee_identique'
        except TimeoutError:
            status = 'budget_60s'
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        result = {'cas': name, 'verification': 'traces_seulement', 'nouveaux_coups_reels': 0, 'statut': status, 'secondes': time.monotonic()-started, 'comparaisons': checks}
        save(out / 'bilan.json', result)
        print(json.dumps({**result, 'comparaisons': checks[-1:]}), flush=True)
    save(OUT / 'sources_finales.json', empreintes())

if __name__ == '__main__':
    run()
