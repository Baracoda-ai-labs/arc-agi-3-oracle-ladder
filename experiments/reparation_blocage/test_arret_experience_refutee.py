from avancer_agent_relais import divergence_plan


def test_experience_tous_modeles_refutes():
    assert divergence_plan({'statut':'experience_conditionnelle'}, {'resultats':[
        {'nom':'a','statut':'modele_refute'}, {'nom':'b','statut':'modele_refute'}]})


def test_hypothese_survivante_et_absence_prediction():
    assert not divergence_plan({}, {'resultats':[]})
    assert not divergence_plan({}, {'resultats':[
        {'nom':'a','statut':'modele_refute'}, {'nom':'b','statut':'transition_confirmee'}]})


def test_proprietaire_reste_prioritaire():
    assert divergence_plan({'modele_plan':'a'}, {'resultats':[
        {'nom':'a','statut':'modele_refute'}, {'nom':'b','statut':'transition_confirmee'}]})
