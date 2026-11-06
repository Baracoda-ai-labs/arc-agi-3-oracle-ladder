from avancer_agent_relais import divergence_plan


def test_ecart_proprietaire_seulement_et_victoire_acceptee():
    d={'modele_plan':'retenu'}
    assert divergence_plan(d,{'resultats':[{'nom':'retenu','statut':'but_refute'}]})
    assert divergence_plan(d,{'resultats':[{'nom':'retenu','statut':'modele_refute'}]})
    assert not divergence_plan(d,{'resultats':[{'nom':'autre','statut':'but_refute'},
        {'nom':'retenu','statut':'transition_confirmee'}]})
    assert not divergence_plan(d,{'resultats':[{'nom':'retenu','statut':'victoire_reelle'}]})
    assert not divergence_plan({}, {'resultats':[{'nom':'retenu','statut':'modele_refute'}]})


def test_decision_sauvegardee_garde_suffixe_sans_redecider():
    from types import SimpleNamespace
    from avancer_agent_relais import decision_suivante
    import pytest
    vus=[]
    c=SimpleNamespace(refute=False,verifier_plan=lambda p:(vus.append(p) or True,{}))
    d={'actions':[['clic',15,13]],'modele_plan':'p','suite_plan':[['MOUSE',21,15]]}
    def interdit(*a,**kw):raise AssertionError('Ne pas effacer le suffixe sauvegardé')
    a=SimpleNamespace(attente=d,chaines={'p':c},decider=interdit)
    assert decision_suivante(a,[6]) is d
    assert vus==[[('MOUSE',13,15),['MOUSE',21,15]]]
    c.refute=True
    with pytest.raises(ValueError,match='non validee'):decision_suivante(a,[6])
