import copy
import os
from types import SimpleNamespace
import pytest
from contexte_export import appliquer_contexte_export, exporter_contextuel
from test_revision_forme_occultee import cas
from revision_forme_occultee import reviser
from revision_perception_selection import porteur_boite
from chaine_agent_integree import lots, canon


def test_restauration_contexte_et_exception(monkeypatch):
    monkeypatch.setenv('CHRYS_PORTEUR_BOITE', '0')
    p = SimpleNamespace(contexte_export={'CHRYS_PORTEUR_BOITE': '1'})
    with pytest.raises(RuntimeError), appliquer_contexte_export(p):
        assert os.environ['CHRYS_PORTEUR_BOITE'] == '1'
        raise RuntimeError('test')
    assert os.environ['CHRYS_PORTEUR_BOITE'] == '0'
    monkeypatch.delenv('CHRYS_PORTEUR_BOITE')
    with appliquer_contexte_export(p):
        assert os.environ['CHRYS_PORTEUR_BOITE'] == '1'
    assert 'CHRYS_PORTEUR_BOITE' not in os.environ


def test_trace_corrigee_buts_et_transfert_sans_contexte_ambiant(monkeypatch, cas):
    import buts_modele_conserve as ancien
    source, z, rows = cas
    # Refaire uniquement la sélection avec la proposition, puis la réparation
    # existante : aucune mutation des modules runtime importés par l'agent.
    from transfert_modele_c import reaffecter
    import cloudpickle
    from pathlib import Path
    r = Path(__file__).parent
    s = cloudpickle.loads((r/'runs/session_re86_buts_conserves1/modele_gagnant_local.pkl').read_bytes())
    source, _ = reaffecter(s, z['images'][0], [canon(k) for k in (1,2,3,4,5)])
    import revision_perception_selection as selection
    source, _ = selection.reviser(source,z['images'][0],z['images'][1],canon(5),z['film_1'])
    with porteur_boite():
        c, diag = reviser(source,z['images'][:12].tolist(),lots([r['action'] for r in rows[:11]]),
                         films=[z[f'film_{i}'] for i in range(1,12)])
    assert diag['admis']
    monkeypatch.delenv('CHRYS_PORTEUR_BOITE', raising=False)
    assert c.perception.contexte_export == {'CHRYS_PORTEUR_BOITE': '1'}
    sans_contexte = copy.deepcopy(c)
    sans_contexte.perception.contexte_export = {}
    assert list(ancien.candidats(sans_contexte,c.actions)) == []
    buts = ancien
    avant = copy.deepcopy(c.perception.th_releve)
    candidats = []
    for but, candidat in buts.candidats(c,c.actions):
        candidats.append((but, candidat))
        assert 'CHRYS_PORTEUR_BOITE' not in os.environ  # même après yield
        assert candidat.perception.contexte_export == c.perception.contexte_export
        th = copy.deepcopy(candidat.perception.th_releve)
        th.but = avant.but
        assert th == avant
        assert exporter_contextuel(candidat.perception,candidat.perception.th_releve,
                                   candidat.perception.tr.taille)[0] == candidat.programme
        assert candidat.rejouer()[1] is not None
    assert candidats
    import transfert_modele_c as transfert
    nouveau, _ = transfert.reaffecter(c,z['images'][0],c.actions)
    assert nouveau.perception.contexte_export == c.perception.contexte_export
    assert nouveau.perception.contexte_export is not c.perception.contexte_export
    assert 'CHRYS_PORTEUR_BOITE' not in os.environ
    assert c.perception.th_releve == avant
