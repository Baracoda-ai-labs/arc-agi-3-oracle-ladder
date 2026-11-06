from types import SimpleNamespace
import numpy as np
import pytest
from suite_apres_reparation import reprendre


def candidat(valide=True,image=None):
    c=SimpleNamespace(refute=False,but_inconnu=False,grilles=[np.zeros((2,2)) if image is None else image],adoptions=[])
    c.verifier_plan=lambda seq:(valide,{'issue':'niveau' if valide else None})
    def adopter(seq,origine):
        c.adoptions.append((seq,origine));return {'statut':'plan_simule_valide'}
    c.adopter_plan=adopter
    return c


def appeler(c,statut='modele_refute',nom='owner/face',sources=('owner',)):
    return reprendre({nom:c},{'modele_plan':'owner','suite_plan':[('UP',),('LEFT',)]},
        [{'nom':'owner','statut':statut}],sources,np.zeros((2,2)))


def test_suite_adoptee_seulement_apres_validation_du_descendant():
    c=candidat();r=appeler(c)
    assert len(c.adoptions)==1 and r[0]['statut']=='plan_simule_valide'

@pytest.mark.parametrize('cas',['but_refute','autre','invalide','futur','but_inconnu','parent_intermediaire'])
def test_ne_reanime_pas_une_suite_sans_preuve(cas):
    c=candidat(valide=cas!='invalide',image=np.ones((2,2)) if cas=='futur' else None)
    c.but_inconnu=cas=='but_inconnu'
    appeler(c,statut='but_refute' if cas=='but_refute' else 'modele_refute',
        nom='autre/face' if cas=='autre' else 'owner/enfant/face' if cas=='parent_intermediaire' else 'owner/face',
        sources=('owner','owner/enfant') if cas=='parent_intermediaire' else ('owner','autre'))
    assert c.adoptions==[]
