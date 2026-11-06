from pathlib import Path
import copy,tarfile,cloudpickle,pytest
from session_chaine_generique import agent_transfere
import buts_roles_herites as buts

@pytest.fixture(scope='module')
def archive():
    p=Path(__file__).parent/'archives/ka59_n3_victoire63.tar.gz'
    with tarfile.open(p) as t:
        noms=[n for n in t.getnames() if n.endswith('/agent.pkl')]
        assert len(noms)==1
        return cloudpickle.loads(t.extractfile(noms[0]).read())

def test_api_nouveau_layout_dynamique_et_source_conservees(archive):
    old=copy.deepcopy(archive.modele_gagnant.programme)
    a=agent_transfere(archive,archive.images[-1],[1,2,3,4,6]);c=next(iter(a.chaines.values()))
    assert c.rejouer()[1] is not None and c.preuve_but_elargi['centres']==[(35,8,9,9)]
    assert c.but_hypothese_non_confirmee and not c.preuve_but_elargi['but_confirme']
    assert c.preuve_transfert_roles['but_source_confirme_par_victoire']
    sans=lambda p:[r for r in p['regles'] if r['nom']!='couverture_heritee_elargie_hypothese']
    assert sans(c.programme)==sans(old) and archive.modele_gagnant.programme==old
    assert len(a.precedents)==len(archive.precedents)+1

def test_refus_correspondance_ambigue(archive,monkeypatch):
    original=buts.couverture
    monkeypatch.setattr(buts,'couverture',lambda vue:original(vue)*2)
    with pytest.raises(ValueError,match='ambigu'):
        agent_transfere(archive,archive.images[-1],[1,2,3,4,6])
