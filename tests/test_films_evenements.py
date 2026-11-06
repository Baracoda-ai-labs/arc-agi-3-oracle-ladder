# SPDX-License-Identifier: MIT-0
"""CW-441 (E) : extracteur d'événements de film (`chrysalide/arc3/films.py`) sur des films synthétiques, et branchement
`moteur._evenements_films` (CHRYS_FILMS_EVT) : alignement film ↔ coup, films absents ou mal alignés sans effet."""
import numpy as np

from chrysalide.arc3 import films as F
from chrysalide.arc3 import moteur


def _bloc(g, x, y, c, k=2):
    g[y:y + k, x:x + k] = c
    return g


def test_trajectoire_passe_par_des_positions_intermediaires():
    fond = np.zeros((16, 16), np.uint8)
    avant = _bloc(fond.copy(), 1, 1, 3)
    film = [_bloc(fond.copy(), x, 1, 3) for x in (3, 5, 7, 9)]
    e = F.evenements(avant, film)
    t = [t for t in e["trajectoires"] if t["couleur"] == 3][0]
    assert t["intermediaires"] >= 2 and not t["revient"]


def test_couleur_ephemere_et_flash_qui_revient():
    avant = _bloc(np.zeros((16, 16), np.uint8), 4, 4, 2, k=6)  # panneau 6 × 6
    film = [_bloc(avant.copy(), 4, 4, 8, k=6), avant.copy()]   # il clignote en 8 puis revient à l'identique
    e = F.evenements(avant, film)
    assert e["transitoires"]["ephemeres"] == [8]
    assert any(s["sorte"] == "flash" for s in e["signaux"])


def test_retour_de_clic_n_est_pas_un_flash():
    avant = _bloc(np.zeros((16, 16), np.uint8), 4, 4, 2, k=6)
    film = [_bloc(avant.copy(), 4, 4, 8, k=6), avant.copy()]
    e = F.evenements(avant, film, clic=(6, 6))
    assert {s["sorte"] for s in e["signaux"]} == {"retour_clic"}


def test_coup_sans_animation_rien():
    avant = _bloc(np.zeros((8, 8), np.uint8), 1, 1, 3)
    e = F.evenements(avant, [avant.copy()])
    assert not e["trajectoires"] and not e["contacts"] and not e["signaux"]


def test_branchement_alignement():
    g = [np.zeros((8, 8), np.uint8)] * 3
    film = [_bloc(np.zeros((8, 8), np.uint8), 2, 2, 3), _bloc(np.zeros((8, 8), np.uint8), 4, 2, 3)]
    ev = moteur._evenements_films(g, [film, None], 2, acts=[4, 4])
    assert ev[0] is not None and ev[1] is None
    assert moteur._evenements_films(g, [film], 2) == [None, None]  # mal aligné : aucun événement


# --- CW-445 F2 : événements typés et CONTRÔLES NÉGATIFS (aucun faux mécanisme) ---------------------------------------
def test_f2_deplacement_puis_retour_n_a_pas_de_deplacement_etabli():
    fond = np.zeros((16, 16), np.uint8)
    avant = _bloc(fond.copy(), 6, 6, 3)
    film = [_bloc(fond.copy(), x, 6, 3) for x in (8, 10, 8, 6)]  # part et revient
    evs, preuve = F.evenements_types(avant, film)
    dep = [e for e in evs if e["kind"] == "deplacement"]
    assert dep and all(e["revient"] and e["displacement"] is None for e in dep)
    assert not any(e["kind"] in ("apparition", "disparition", "recoloration") for e in evs)
    assert preuve["final_state_changed"] is False and preuve["transient_events_observed"] is True


def test_f2_jauge_seule_est_au_bord():
    avant = np.zeros((16, 16), np.uint8)
    avant[0, :] = 4  # jauge sur la 1re rangée
    apres = avant.copy()
    apres[0, 12:] = 0  # elle raccourcit
    evs, _ = F.evenements_types(avant, [apres])
    assert evs and all(e["bord"] for e in evs)


def test_f2_animation_decorative_identique_pour_deux_actions():
    """Même état, deux actions, même film : l'extracteur rend la même chose (le consommateur écarte la décoration)."""
    avant = _bloc(np.zeros((16, 16), np.uint8), 6, 6, 2, k=4)
    film = [_bloc(avant.copy(), 6, 6, 9, k=4), avant.copy()]
    assert F.evenements_types(avant, film) == F.evenements_types(avant, [f.copy() for f in film])
    evs, preuve = F.evenements_types(avant, film)
    assert [e["kind"] for e in evs] == ["pulsation"] and not preuve["final_state_changed"]


def test_f2_apparition_et_types_json():
    import json
    avant = np.zeros((16, 16), np.uint8)
    apres = _bloc(avant.copy(), 7, 7, 5)
    evs, _ = F.evenements_types(avant, [apres])
    assert [e["kind"] for e in evs] == ["apparition"]
    json.dumps(evs)  # entiers ordinaires, sérialisable


def test_f2_bascule_sur_grille_reguliere_n_est_pas_un_deplacement():
    """ft09 : des cases d'une grille régulière changent de couleur ; aucun déplacement établi (contrôle négatif)."""
    avant = np.zeros((20, 20), np.uint8)
    for x in range(0, 20, 4):
        for y in range(0, 20, 4):
            avant[y:y + 2, x:x + 2] = 9
    apres = avant.copy()
    apres[0:2, 0:2] = 3  # une case quitte la couleur 9…
    apres[0:2, 18:20] = 9  # … une autre la prend (même nombre de cases)
    evs, _ = F.evenements_types(avant, [apres])
    assert not any(e["kind"] == "deplacement" and e["displacement"] is not None for e in evs)


def test_candidat_controle_fleches():
    fond = np.zeros((20, 20), np.uint8)
    coups, x = [], 4
    for a in (4, 4, 4, 3):  # trois RIGHT puis un LEFT : le bloc suit les flèches
        avant = _bloc(fond.copy(), x, 8, 7, k=3)
        x += 2 if a == 4 else -2
        coups.append((a, avant, [_bloc(fond.copy(), x, 8, 7, k=3)]))
    c = F.candidat_controle(coups)
    assert c and c[0]["couleur"] == 7 and c[0]["accord"] == 1.0
    assert F.candidat_controle([(("clic", 5, 5), a, f) for _, a, f in coups]) == []  # le clic n'est pas candidat
