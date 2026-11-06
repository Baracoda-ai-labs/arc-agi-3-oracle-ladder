"""Le cache sans but du niveau source ne remplace pas la théorie réaffectée."""
from types import SimpleNamespace
import numpy as np
import session_chaine_generique as session
import transfert_modele_c


def test_transfert_herite_exactement_theorie_reaffectee(monkeypatch):
    source=SimpleNamespace(perception=SimpleNamespace(th_plan=SimpleNamespace(but=None),
        th_releve=SimpleNamespace(but=('but_source',),roles=['ancienne_instance'])),
        grilles=[],lots=[],films=SimpleNamespace(entrees=[]))
    validee=SimpleNamespace(but=('but_valide',),roles=['nouvelle_instance'])
    c=SimpleNamespace(perception=SimpleNamespace(th_releve=validee))
    monkeypatch.setattr(transfert_modele_c,'reaffecter',lambda *args,**kwargs:(c,{}))
    monkeypatch.setattr(session,'nouvel_agent',lambda *args,**kwargs:SimpleNamespace(journal=[]))
    ancien=SimpleNamespace(modele_gagnant=source,precedents=[],actions=[1],commandes_connues={1})
    a=session.agent_transfere(ancien,np.zeros((64,64)),[1])
    assert a.theorie_precedente.but==validee.but
    assert a.theorie_precedente.roles==['nouvelle_instance']
    assert a.theorie_precedente is not validee
    a.theorie_precedente.roles.append('mutation_locale')
    assert validee.roles==['nouvelle_instance']
    assert source.perception.th_plan.but is None
