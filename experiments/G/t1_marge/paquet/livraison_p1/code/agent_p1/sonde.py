"""Sonde de développement (comptée) : joue des actions élémentaires et résume ce qui change. Aucun code de jeu lu."""
import json, sys
from pathlib import Path
import numpy as np
from chrysalide.arc3.logique.jeux import environnement, jouer_action
from .objets import composantes, forme


def objets_image(im, fond=None):
    vals, cnt = np.unique(im, return_counts=True)
    fond = int(vals[np.argmax(cnt)]) if fond is None else fond
    out = []
    for c in vals:
        if c == fond:
            continue
        for cs in composantes(im == c):
            pos, f = forme(cs)
            xs = [x for x, y in cs]; ys = [y for x, y in cs]
            out.append(dict(c=int(c), n=len(cs), x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys),
                            cx=int(round(np.mean(xs))), cy=int(round(np.mean(ys)))))
    return out, fond


def resume_diff(a, b):
    m = a != b
    if not m.any():
        return 'aucun changement'
    ys, xs = np.where(m)
    from collections import Counter
    cols = Counter((int(a[y, x]), int(b[y, x])) for y, x in zip(ys, xs)).most_common(5)
    return f'{int(m.sum())} px, bbox x{xs.min()}-{xs.max()} y{ys.min()}-{ys.max()}, {cols}'


def sonder(jeu, dossier, sortie, seq):
    env = environnement(jeu, dossier); f = env.reset(); im = np.asarray(f.frame[-1]); log = []
    images = [im]
    for a in seq:
        f = jouer_action(env, a); nb = np.asarray(f.frame[-1])
        log.append(dict(action=a, diff=resume_diff(im, nb), niveaux=f.levels_completed, etat=str(f.state),
                        n_images=len(f.frame)))
        im = nb; images.append(im)
    Path(sortie).mkdir(parents=True, exist_ok=True)
    np.savez_compressed(Path(sortie) / 'sonde.npz', images=np.asarray(images))
    (Path(sortie) / 'sonde.json').write_text(json.dumps(dict(jeu=jeu, actions=seq, log=log), indent=1, default=str))
    for L in log:
        print(L)
    return images, log
