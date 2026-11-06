"""Option explicite, héritage et absence d'invention d'observations."""
from types import SimpleNamespace
import pytest
from session_chaine_generique import configurer_composition, arguments_session, agent_transfere

@pytest.mark.parametrize('cli,attendu',[([],None),(['--composition-contextuelle-auto'],True)])
def test_option_cli(cli,attendu):
    args=arguments_session().parse_args(['--jeu','ar25','--sortie','/tmp/non_execute',*cli])
    assert args.composition_contextuelle_auto is attendu

def test_ancien_snapshot_non_active_implicitement():
    ancien=SimpleNamespace();nouveau=SimpleNamespace()
    assert configurer_composition(nouveau,ancien=ancien) is False
    assert vars(ancien)=={} and vars(nouveau)=={'composition_contextuelle_auto':False}

@pytest.mark.parametrize('actif',[False,True])
def test_retry_herite_seulement_option_pas_episodes(actif):
    ancien=SimpleNamespace(composition_contextuelle_auto=actif, observations_episodes=[{'actions':[1]}])
    nouveau=SimpleNamespace(images=['nouveau_niveau'])
    configurer_composition(nouveau,ancien=ancien)
    assert nouveau.composition_contextuelle_auto is actif
    assert not hasattr(nouveau,'observations_episodes') and nouveau.images==['nouveau_niveau']

def test_activation_explicite_sur_snapshot_et_reprise():
    a=SimpleNamespace()
    assert configurer_composition(a,True)
    assert configurer_composition(a,None)
    assert vars(a)=={'composition_contextuelle_auto':True}

@pytest.mark.parametrize('actif',[False,True])
def test_transfert_niveau_preserve_option_sans_fusion(monkeypatch,actif):
    import session_chaine_generique as module
    source=SimpleNamespace(perception=object(),grilles=['N1'],lots=[],films=SimpleNamespace(entrees=[]))
    ancien=SimpleNamespace(modele_gagnant=source,journal=[],precedents=[],actions=[1],
        commandes_connues={1},composition_contextuelle_auto=actif,
        observations_episodes=[{'interdit':'ne_pas_fusionner_N1_N2'}])
    c=SimpleNamespace(perception=SimpleNamespace(th_releve=None))
    monkeypatch.setattr('transfert_modele_c.reaffecter',lambda *args,**kw:(c,{}))
    monkeypatch.setattr(module,'nouvel_agent',lambda *args,**kw:SimpleNamespace(journal=[]))
    a=agent_transfere(ancien,'imageN2',[1])
    assert a.composition_contextuelle_auto is actif
    assert not hasattr(a,'observations_episodes')
    assert a.chaines=={'transfert_modele_c':c}
