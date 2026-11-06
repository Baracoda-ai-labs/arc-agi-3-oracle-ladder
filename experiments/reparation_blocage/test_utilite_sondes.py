import io,json,tarfile
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import chaine_agent_integree as module
from chaine_agent_integree import AgentIntegre
R=Path(__file__).parent

def agent(n,active):
    with tarfile.open(R/'archives/legacy_sans_but_arc1.tar.gz') as t:
        j=json.load(t.extractfile('reel/N1/partie.json'))
        z=np.load(io.BytesIO(t.extractfile('reel/N1/partie.npz').read()))
        return AgentIntegre(z['images'][:n+1],j['actions'][:n],[z[f'film_{i+1}'] for i in range(n)],['continue']*n,
            decouverte_courte=True,legacy_sans_but=True,utilite_sondes=active)

@pytest.mark.parametrize('n',[7,25])
def test_singleton_arret_conserve_modele_pas_fallback(n,monkeypatch):
    ancien=agent(n,False);avant=ancien.decider([6]);assert avant['actions']
    def interdit(*args,**kwargs):raise AssertionError('fallback contourne utilite')
    monkeypatch.setattr(module,'proposer_acquisition',interdit)
    nouveau=agent(n,True);apres=nouveau.decider([6])
    assert apres['statut']=='but_ou_experience_non_couvert' and apres['actions']==[]
    assert nouveau.chaines and nouveau.attente is None and len(nouveau.actions)==n
    assert all(x['raison']=='aucun_departage' for x in apres['utilite']['refus'])

def test_desaccord_observable_classe_sans_issue_inventee(monkeypatch):
    a=agent(7,True)
    a.chaines={n:SimpleNamespace(description_perception=lambda:{'methode':'controle','masque':[]}) for n in ('a','b')}
    monkeypatch.setattr(a,'_predire',lambda c,act:{'image':[[0 if c is a.chaines['a'] else 1]],'issue':None})
    candidate=(1,'perception_sans_but_test',('MOUSE',1,1))
    choix,r=a._choisir_sonde_utile(a.dossier([6]),[candidate])
    assert choix==candidate and r['choix']['cout_total']==1 and r['choix']['information_convention_uniforme']==1
    assert r['obligations']==[]

def test_espaces_distincts_refuses_sans_masquage(monkeypatch):
    a=agent(7,True)
    a.chaines={'a':SimpleNamespace(description_perception=lambda:{'masque':[]}), 'b':SimpleNamespace(description_perception=lambda:{'masque':[[63,0]]})}
    choice,r=a._choisir_sonde_utile(a.dossier([6]),[(1,'perception_sans_but_test',('MOUSE',1,1))])
    assert choice is None and r['refus']=='espaces_observables_non_alignes'
