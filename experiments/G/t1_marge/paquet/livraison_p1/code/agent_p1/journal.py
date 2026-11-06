"""Journaux append-only : un fichier par épisode, jamais écrasé (suffixe horodaté si le nom existe)."""
import json, os, time, hashlib, subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent


def sha_code():
    h = hashlib.sha256()
    for p in sorted(RACINE.glob('*.py')):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()


def etat_paquet():
    """C (CCM-306-B) : empreinte du paquet RECALCULÉE au lancement (chaque fichier de SHA256SUMS revérifié)."""
    racine = RACINE.parents[2]
    m = racine / 'SHA256SUMS'
    if not m.exists():
        return None
    ok = True
    for ligne in m.read_text().splitlines():
        h, _, chemin = ligne.partition('  ')
        f = racine / chemin
        ok = ok and f.exists() and hashlib.sha256(f.read_bytes()).hexdigest() == h
    return dict(conforme=ok, global_sha256=hashlib.sha256(m.read_bytes()).hexdigest())


def _defaut(o):
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=str)
    if hasattr(o, 'item'):
        return o.item()
    if hasattr(o, 'resume'):
        return o.resume()
    return str(o)


class Journal:
    def __init__(self, dossier, nom, meta):
        d = Path(dossier); d.mkdir(parents=True, exist_ok=True)
        p = d / f'{nom}.jsonl'
        if p.exists():
            p = d / f'{nom}_{time.strftime("%Y%m%d_%H%M%S")}.jsonl'
        self.path = p
        self.ecrire('meta', **meta, code_sha256=sha_code(), debut=time.strftime('%Y-%m-%dT%H:%M:%S'),
                    env={k: v for k, v in os.environ.items() if k.startswith('CHRYS_')}, paquet=etat_paquet())  # C (CCM-306-B)

    def ecrire(self, type_, **kw):
        with open(self.path, 'a') as f:
            f.write(json.dumps(dict(type=type_, **kw), default=_defaut, ensure_ascii=False) + '\n')
