import copy
import json
from pathlib import Path
import numpy as np
import pytest
from chaine_coherente import Chaine
from chaine_agent_integree import AgentIntegre, lots, canon
from perception_echelles import proposer as echelles
from revision_sans_effet import proposer
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.plan_langage import cle_complete

@pytest.fixture
def monde():
    p=Path(__file__).parent/'runs/sp80_echelles1/N1'
    g=np.load(p/'partie.npz')['images']
    a=json.loads((p/'partie.json').read_text())['actions']
    cs,_=echelles({'grilles':g[:9].tolist(),'lots':lots(a[:8])})
    return cs[0][1],g,a

def etendre(c,g,a,n):
    return Chaine(c.perception,c.programme,g[:n+1].tolist(),lots(a[:n]),[],coups_deja_joues=n)

def test_revision_prefixe_et_suffixe_independant(monde):
    c,g,a=monde
    source=etendre(c,g,a,11)
    th0=copy.deepcopy(source.perception.th_releve)
    assert source.rejouer()[0]['premiere_divergence']==11
    new,d=proposer(source)
    assert new is not None and d['admis'] and d['controle']['transitions']==11
    th1=copy.deepcopy(new.perception.th_releve)
    assert th1.sans_effet
    th1.sans_effet=th0.sans_effet
    assert th1==th0 and source.perception.th_releve==th0
    assert new.perception.tr.exclues==source.perception.tr.exclues
    _,(pc,sc)=new.rejouer()
    pi=Programme(new.programme);pi.etat=copy.deepcopy(pc.etat);si=copy.deepcopy(sc)
    for i in range(11,29):
        pc.step(sc,canon(a[i]));pi.step(si,canon(a[i]))
        assert cle_complete(si,pi.etat)==cle_complete(sc,pc.etat)
        assert np.array_equal(new.perception.rendu(sc),new.perception.vue(g[i+1]))
    assert len(new.grilles)==12

def test_refuse_changement_cache_par_echantillonnage(monde):
    c,g,a=monde
    source=etendre(c,g,a,11)
    source.grilles[-1][25][25]=3
    assert np.array_equal(source.perception.vue(source.grilles[-2]),source.perception.vue(source.grilles[-1]))
    new,d=proposer(source)
    assert new is None and d['refus']=='changement_natif_hors_masque'

def test_refuse_autre_contreexemple_dans_prefixe(monde):
    c,g,a=monde
    source=etendre(c,g,a,11)
    source.grilles[9][24][24]=3
    new,d=proposer(source)
    assert new is None and d['refus']=='rejeu_prefixe'

def test_observer_garde_modele_conditionne(monde):
    c,g,a=monde
    c=etendre(c,g,a,10);c.activer_atms()
    agent=AgentIntegre(g[:11],a[:10],[None]*10,['continue']*10)
    agent.chaines={'conserve':c}
    c.plan={'actions':[canon(a[10])], **c.signature(), 'origine':'experience_test'}
    c._tracer_plan()
    agent.attente={'actions':[a[10]],'modeles':['conserve'],'suite_plan':[]}
    agent.observer(a[10],g[11],[g[11].tolist()],'continue',source='trace')
    assert 'conserve/sans_effet' in agent.chaines
    assert any(r['type']=='revision_sans_effet' and r['admis'] for r in agent.journal)

def test_but_existant_conserve(monde):
    from chrysalide.arc3.logique.export_langage import exporter
    c,g,a=monde
    c.perception.th_releve.but=('sortie',9,11)
    c.programme,non=exporter(c.perception.th_releve,c.perception.tr.taille)
    assert not non
    source=etendre(c,g,a,11)
    new,d=proposer(source)
    assert d['admis'] and new.perception.th_releve.but==('sortie',9,11)
