from types import SimpleNamespace
import pytest
import recherche_selection_prolongee as mod
from test_recherche_selection_prolongee import contexte,echec
from session_chaine_generique import configurer_recherche,arguments_session


def test_palier_local_sans_processus_et_sans_repetition_poids3(monkeypatch):
    agent=SimpleNamespace(recherche_prolongee_workers=1);taches=[]
    monkeypatch.setattr(mod,'sauver_agent',lambda *a:None)
    monkeypatch.setattr(mod,'portefeuille',lambda *a,**k:pytest.fail('processus supplémentaire'))
    monkeypatch.setattr(mod,'rechercher',lambda t:(taches.append(t) or {'plan':None,'poids':t[2],'cpu_s':2,'preuve':{}}))
    r=mod._executer(agent,'c',120)
    assert len(r)==1 and [t[2:] for t in taches]==[(10,120)]


def test_adoption_et_cpu_local_pas_compte_deux_fois(monkeypatch):
    a,c=contexte();a.recherche_prolongee_workers=1
    monkeypatch.setattr(mod,'_executer',lambda *args:[{'plan':[('UP',)],'poids':10,'cpu_s':2,'preuve':{}}])
    r=mod.prolonger(a,[1],echec(c))
    assert r['statut']=='plan_simule_valide' and c.adoptions==[[('UP',)]]
    assert r['workers']==1 and r['poids']==[10] and r['cpu_enfants_s']==0
    assert r['cpu_total_s']==r['cpu_parent_s'] and r['cpu_recherches_s']==2
    assert mod.prolonger(a,[1],echec(c))['statut']=='plan_deja_present'


def test_cli_et_heritage_anciens_snapshots():
    args=arguments_session().parse_args(['--jeu','inconnu','--neuf','--sortie','sans_sdk',
                                        '--recherche-prolongee','--recherche-workers','1'])
    a=SimpleNamespace();configurer_recherche(a,activation=args.recherche_prolongee,workers=args.recherche_workers)
    assert a.recherche_prolongee and a.recherche_prolongee_workers==1
    b=SimpleNamespace();configurer_recherche(b,ancien=a)
    assert b.recherche_prolongee and b.recherche_prolongee_workers==1
    ancien=SimpleNamespace(recherche_prolongee=True);configurer_recherche(b,ancien=ancien)
    assert b.recherche_prolongee_workers==2
    with pytest.raises(ValueError):configurer_recherche(b,workers=3)
