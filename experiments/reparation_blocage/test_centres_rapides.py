import importlib.util
import random
from pathlib import Path

ICI = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('centres_rapides_test', ICI / 'code/centres_rapides.py')
rapide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rapide)


def reference(col, marques):
    return [z for z, k in col.items() if k not in marques
            and all(col.get((z[0] + dx, z[1] + dy)) in marques for dx, dy in rapide.VOISINS8)]


def test_identique_sur_cartes_variees_et_ordres():
    rng = random.Random(24)
    for _ in range(500):
        coords = [(x, y) for y in range(rng.randrange(3, 20)) for x in range(rng.randrange(3, 20))]
        rng.shuffle(coords)
        col = {z: rng.randrange(4) for z in coords if rng.random() > 0.1}
        for marques in [{0}, {1, 2}, set(), {0, 1, 2, 3}]:
            assert rapide.centres_motifs(col, marques) == reference(col, marques)


def test_cache_ne_confond_pas_couleur_et_presence_du_centre():
    col = {(x, y): 1 for x in range(3) for y in range(3)}
    col[1, 1] = 0
    assert rapide.centres_motifs(col, {1}) == [(1, 1)]
    col[1, 1] = 2
    assert rapide.centres_motifs(col, {1}) == [(1, 1)]
    del col[1, 1]
    assert rapide.centres_motifs(col, {1}) == []
    col[1, 1] = 1
    assert rapide.centres_motifs(col, {1}) == []


def test_cache_borne_et_mutations_des_marques():
    for i in range(300):
        col = {(x + i * 5, y): 1 for x in range(3) for y in range(3)}
        col[i * 5 + 1, 1] = 0
        assert rapide.centres_motifs(col, {1}) == reference(col, {1})
        col[i * 5, 0] = 0
        assert rapide.centres_motifs(col, {1}) == reference(col, {1})
    assert rapide._entoures.cache_info().currsize <= 256
