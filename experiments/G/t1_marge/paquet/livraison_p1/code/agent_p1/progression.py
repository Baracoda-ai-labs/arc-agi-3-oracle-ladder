"""Parcours réel depuis RESET avec l'agent inventeur (non-régression g50t N1–N5), bibliothèque partagée entre niveaux.

Refuse max_level > 5 (N6 = cas étudié, lancé à part ; N7 = transfert tenu à l'écart, lancé une seule fois, code figé).
"""
import argparse, json
from pathlib import Path
from .agent import Agent, Laboratoire


def run(game, jeux, output, max_level=5, budget=150, seconds=600, mode='complet', biblio=None):
    if max_level > 5:
        raise ValueError('progression de développement limitée à N5')
    root = Path(output); root.mkdir(parents=True, exist_ok=True)
    lab = Laboratoire(game, 1, jeux, root / 'N1' / 'partie'); res = []
    for level in range(1, max_level + 1):
        r = Agent(game, level, jeux, root / f'N{level}', mode, budget, seconds, biblio, lab=lab).run()
        res.append({k: r[k] for k in ('game', 'level', 'victoire', 'actions', 'secondes', 'raison', 'hypotheses_generees')})
        (root / 'progression.json').write_text(json.dumps(res, indent=1))
        if not r['victoire'] or level == max_level:
            break
        lab = lab.next_level(root / f'N{level + 1}' / 'partie')
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--game', default='g50t'); ap.add_argument('--jeux', default='jeux')
    ap.add_argument('--output', required=True); ap.add_argument('--mode', default='complet'); ap.add_argument('--biblio')
    a = ap.parse_args(); print(json.dumps(run(a.game, a.jeux, a.output, mode=a.mode, biblio=a.biblio)))
