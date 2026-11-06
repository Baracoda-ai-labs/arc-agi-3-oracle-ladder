"""Une cible non réaffectée suspend le but, pas les lois déjà apprises."""
import copy
from pathlib import Path
import cloudpickle
import numpy as np
from transfert_roles import reaffecter


def test_instance_sans_cible_conserve_physique_et_source():
    path=Path(__file__).parent/'runs/ka59_n4_suite58_prospectif1/agent.pkl'
    a=cloudpickle.loads(path.read_bytes());s=a.modele_gagnant
    original=copy.deepcopy(s.programme);signature=s.signature()
    c,d=reaffecter(s,a.images[-1],[])
    assert c.but_inconnu and c.plan is None
    assert not c.perception.cibles
    assert d['but_suspendu'] and d['validation_dynamique_nouveau_niveau'] is False
    assert c.programme['regles']==[r for r in original['regles'] if r.get('alors')!=[['niveau_suivant']]]
    assert c.preuve_but_suspendu['regles_source']==[r for r in original['regles'] if r.get('alors')==[['niveau_suivant']]]
    check,state=c.rejouer()
    assert state and check['rejeu'] and check['compilation_fidele']
    assert np.array_equal(c.perception.rendu(state[1]),c.perception.vue(a.images[-1]))
    assert s.programme==original and s.signature()==signature
