from lecons_revision import extraire

def test_validation_ulterieure_ne_modifie_pas_entree_ou_cible():
    r={'type':'revision_solidite','depuis':'m','programme_avant':['avant'],
       'patches_admis':[{'revision':{'operateur':'non_solide','classe':7},
                        'programme_apres':['apres']}], 'essais':[]}
    o={'type':'observation','coup':11,'resultats':[{'nom':'m','statut':'modele_refute'}]}
    future={'type':'observation','coup':12,'resultats':[
        {'nom':'m/non_solide_7','statut':'transition_confirmee','source':'jeu'}]}
    initial=extraire([r,o])[0];complet=extraire([r,o,future])[0]
    assert initial['id']==complet['id']
    assert initial['entree']==complet['entree'] and initial['cible']==complet['cible']
    assert not initial['validation_ulterieure']
    assert len(complet['validation_ulterieure'])==1
    assert complet['cible']['action_optimale'] is None
