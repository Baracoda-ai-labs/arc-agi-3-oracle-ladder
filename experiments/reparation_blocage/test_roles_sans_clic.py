import copy,json
from pathlib import Path
import numpy as np
import pytest
from freinage_passif import candidats
from selection_observee import SelectionObservee
from chaine_coherente import Chaine
from chaine_agent_integree import lots,canon
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.logique.plan_langage import cle_complete

@pytest.fixture(scope='module')
def traces():
    r=Path(__file__).parent/'runs/ka59_anti_cycles1/N1'
    z=np.load(r/'partie.npz');return z['images'],json.loads((r/'partie.json').read_text())['actions'],[z[f'film_{i}'] for i in range(1,73)]

@pytest.mark.parametrize('n',[47,48,68,72])
def test_prefixes_et_suffixes_separes(traces,n):
    g,a,f=traces
    cs=candidats(g[:n+1],a[:n],f[:n],sans_clic=True)
    assert len(cs)==2
    for nom,m in cs:
        c=Chaine(m,m.programme(),g[:n+1].tolist(),lots(a[:n]),[],films=f[:n])
        check,cur=c.rejouer();assert check['transitions']==n and cur
        assert m.roles_sans_clic['role_commande']=='hypothese_depuis_mouvement'
        if n<60:assert m.roles_sans_clic['selection_clic']=='non_observee'
        else:assert m.roles_sans_clic['selection_clic']=='observee_sur_prefixe'
        pc,sc=cur;pi=Programme(c.programme);pi.etat=copy.deepcopy(pc.etat);si=copy.deepcopy(sc)
        ecarts={}
        for i in range(n,72):
            pc.step(sc,canon(a[i]));pi.step(si,canon(a[i]))
            assert cle_complete(sc,pc.etat)==cle_complete(si,pi.etat)
            ecarts[i+1]=int((m.rendu(sc)!=m.vue(g[i+1])).sum())
        if n<60:
            assert all(ecarts[i]==0 for i in range(n+1,60))
            assert ecarts[60]==1  # sélection nonobservée : prédiction provisoire réfutée
        else:assert all(v==0 for v in ecarts.values())
        assert len(c.grilles)==n+1


def test_defaut_exige_toujours_clic(traces):
    g,a,f=traces
    with pytest.raises(StopIteration):SelectionObservee(g[:48],a[:47],films=f[:47])


def test_attribut_pas_une_couleur_codee(traces):
    from roles_sans_clic import amorcer
    g,a,f=traces
    palette=np.array([7,8,9,10,11,12,13,14,15,0,1,2,3,4,5,6])
    base,m,point,ina,preuve=amorcer(g[:46],a[:45],f[:45])
    _,mr,point_r,ina_r,_=amorcer(palette[g[:46]],a[:45],[palette[x] for x in f[:45]])
    assert point_r==point and ina_r==palette[ina] and np.array_equal(mr,palette[m])
