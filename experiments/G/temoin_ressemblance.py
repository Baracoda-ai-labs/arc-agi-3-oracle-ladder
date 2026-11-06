"""[G] CW-359 : TÉMOIN DÉTERMINISTE du test d'exploration Qwen. Classe les objets candidats (« quel objet cliquer en
premier pour tester un changement de sélection ») par RESSEMBLANCE avec l'objet piloté : forme puis couleur, sans
apprentissage ni lecture des réponses. Score (plus grand = plus tôt) :
  forme : 2 si silhouette identique (masque des cases visibles, à translation près), sinon IoU des masques alignés en
          haut à gauche (0..1) ;
  couleur : 1 si une couleur rendue est commune (code ≥ 512 rendu `code % 16`, faits.MARQUEUR), sinon 0 ;
  départage : taille (écart du nombre de cases), puis distance au piloté, puis position (ligne, colonne).
Le piloté et les objets plus grands que le quart de la scène (fonds, cadres) sont exclus.
`classer(objets, pilote)` : objets = dicts {x, y, pixels} (format scène du langage), pilote = indice ou dict → liste de
(score, objet). Usage : PYTHONPATH=. .venv/bin/python experiments/G/temoin_ressemblance.py <dossier.pkl> → classement"""
import numpy as np


def _masque(o):
    px = np.asarray(o["pixels"])
    return px >= 0


def _couleurs(o):
    px = np.asarray(o["pixels"])
    return {int(c) % 16 if c >= 512 else int(c) for c in px[px >= 0].ravel()}


def _iou(a, b):
    h, w = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])
    pa, pb = np.zeros((h, w), bool), np.zeros((h, w), bool)
    pa[:a.shape[0], :a.shape[1]], pb[:b.shape[0], :b.shape[1]] = a, b
    u = (pa | pb).sum()
    return float((pa & pb).sum() / u) if u else 0.0


def _rogne(m):
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(xs) else m


def classer(objets, pilote, taille=None):
    p = objets[pilote] if isinstance(pilote, int) else pilote
    mp, cp = _rogne(_masque(p)), _couleurs(p)
    aire = (taille[0] * taille[1]) if taille else None
    out = []
    for o in objets:
        if o is p or not o.get("visible", True):
            continue
        m = _rogne(_masque(o))
        if aire and m.sum() > aire / 4:
            continue
        forme = 2.0 if m.shape == mp.shape and bool((m == mp).all()) else _iou(m, mp)
        couleur = 1.0 if _couleurs(o) & cp else 0.0
        d = abs(o["x"] - p["x"]) + abs(o["y"] - p["y"])
        out.append(((forme + couleur, -abs(int(m.sum()) - int(mp.sum())), -d, -o["y"], -o["x"]), o))
    out.sort(key=lambda t: t[0], reverse=True)
    return [(round(k[0], 3), o) for k, o in out]


def pilote_de(th, objets):
    """Indice de l'objet piloté : classe portant des `moves` dans la théorie de C (1re trouvée)."""
    cls = {c for c, _a in th.moves}
    for i, o in enumerate(objets):
        px = np.asarray(o["pixels"])
        if set(px[px >= 0].ravel().tolist()) & cls:
            return i
    return None


def main():
    import pickle
    import sys
    d = pickle.loads(open(sys.argv[1], "rb").read())  # noqa: SIM115
    objs = d["sprites_depart"]
    i = pilote_de(d["theorie"], objs)
    print("piloté", objs[i]["x"], objs[i]["y"], sorted(_couleurs(objs[i])))
    for s, o in classer(objs, i, d["taille"]):
        px = np.asarray(o["pixels"])
        print(s, (o["x"], o["y"]), px.shape, sorted(set(px[px >= 0].ravel().tolist())))


if __name__ == "__main__":
    main()
