"""Fragment révélé au coup onze ; neuf prédictions gelées et refus des faux ajouts."""
import copy
import json
from pathlib import Path

import cloudpickle
import numpy as np
import pytest

from chaine_agent_integree import canon, lots
from chrysalide.arc3.logique.export_langage import exporter
from revision_forme_occultee import reviser
from revision_perception_selection import porteur_boite, reviser as selection
from transfert_modele_c import reaffecter

R = Path(__file__).parent


@pytest.fixture
def cas():
    z = np.load(R/'runs/session_re86_calques_hotes2/N2/partie.npz')
    rows = json.loads((R/'runs/session_re86_calques_hotes2/N2/partie.json').read_text())['rows']
    s = cloudpickle.loads((R/'runs/session_re86_buts_conserves1/modele_gagnant_local.pkl').read_bytes())
    c, _ = reaffecter(s, z['images'][0], [canon(i) for i in (1, 2, 3, 4, 5)])
    c, _ = selection(c, z['images'][0], z['images'][1], canon(5), z['film_1'])
    return c, z, rows


def test_prefixe_sans_divergence_ne_revise_pas(cas):
    c, z, rows = cas
    with porteur_boite():
        candidat, diag = reviser(c, z['images'][:11].tolist(), lots([r['action'] for r in rows[:10]]))
    assert candidat is None and diag['refus'] == 'aucune_divergence'


def test_fragment_avec_suffixe_geles_et_theorie_synchronisee(cas):
    c, z, rows = cas
    avant = copy.deepcopy(c.programme), copy.deepcopy(c.perception.th_releve)
    with porteur_boite():
        candidat, diag = reviser(c, z['images'][:12].tolist(), lots([r['action'] for r in rows[:11]]),
                                films=[z[f'film_{i}'] for i in range(1, 12)])
        assert diag['admis'] and diag['controle_avant']['premiere_divergence'] == 11, repr(diag)
        th, tr = candidat.perception.th_releve, candidat.perception.tr
        assert exporter(th, tr.taille)[0] == candidat.programme
        assert th.but == avant[1].but and th.moves == avant[1].moves
        monde = tr.etats[0]
        for i, row in enumerate(rows):
            monde, _ = th.pas(monde, row['action'], tr.taille)
            assert np.array_equal(th.rendu(monde, tr.taille, tr.fond), candidat.perception.vue(z['images'][i+1]))
    _, (pc, sc) = candidat.rejouer()
    for i in range(11, len(rows)):
        pc.step(sc, canon(rows[i]['action']))
        assert np.array_equal(candidat.perception.rendu(sc), candidat.perception.vue(z['images'][i+1]))
    assert len(candidat.lots) == 11
    assert c.programme == avant[0] and c.perception.th_releve == avant[1]


def test_fragment_sans_support_est_refuse(cas):
    c, z, rows = cas
    images = z['images'][:12].copy()
    images[-1, 0, 0] = (int(images[-1, 0, 0])+1) % 16
    with porteur_boite():
        candidat, diag = reviser(c, images.tolist(), lots([r['action'] for r in rows[:11]]))
    assert candidat is None and not diag['admis']
