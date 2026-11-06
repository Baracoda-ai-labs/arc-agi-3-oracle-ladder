"""Régression sur observations réelles : le contexte antérieur reste archivé."""
import copy
from pathlib import Path
import cloudpickle
from chaine_agent_integree import AgentIntegre, canon


def test_calques_apres_restauration_contexte_reel():
    path = Path(__file__).parent / 'runs/ar25_memoire_continue_source1/agent.pkl'
    archive = cloudpickle.loads(path.read_bytes())
    a = AgentIntegre([archive.images[3]], [], [], [], reparation=True)
    a.installer_modele_jeu(copy.deepcopy(archive.memoire_jeu))
    programme = copy.deepcopy(next(iter(a.chaines.values())).programme)
    a.images = copy.deepcopy(archive.images[:4])
    a.actions = copy.deepcopy(archive.actions[:3])
    a.films = copy.deepcopy(archive.films[:3])
    a.issues = copy.deepcopy(archive.issues[:3])
    a.debut_contexte = 3
    for k in range(3, 8):
        c = a.chaines['transfert_objets_0']
        c.plan = {'actions': [canon(archive.actions[k])], **c.signature(), 'origine': 'trace_reelle'}
        c._tracer_plan()
        a.attente = {'actions': [archive.actions[k]], 'modeles': ['transfert_objets_0']}
        a.observer(archive.actions[k], archive.images[k+1], archive.films[k], 'continue', source='trace')
    assert set(a.chaines) == {'transfert_objets_0/detail_local', 'transfert_objets_0/detail_periodique'}
    assert len(a.images) == 9 and a.actions == archive.actions and a.debut_contexte == 3
    for c in a.chaines.values():
        assert c.programme == programme and len(c.grilles) == 6 and len(c.lots) == 5
        check, state = c.rejouer()
        assert state is not None and check['compilation_fidele'] and check['transitions'] == 5
    assert not any(r['type'] == 'revision_refusee' for r in a.journal)
