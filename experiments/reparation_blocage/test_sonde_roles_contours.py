import copy
from pathlib import Path
import cloudpickle
import tarfile
import numpy as np
from sonde_roles_non_couverts import contours_adjacents, proposer


def test_frontiere_complete_connexe_seule_est_admise():
    support={'x':5,'y':7,'pixels':np.ones((2,3),dtype=int)}
    contour={'x':4,'y':6,'pixels':np.pad(np.full((2,3),-1),1,constant_values=8)}
    lointain={'x':25,'y':27,'pixels':np.ones((4,5),dtype=int)}
    fond={'x':0,'y':0,'pixels':np.ones((40,40),dtype=int)}
    proche={'x':4,'y':7,'pixels':np.ones((2,1),dtype=int)}
    result=contours_adjacents([support],[contour,lointain,fond,proche])
    assert len(result)==1 and result[0] is contour


def test_archive18_contour_nouveau_sans_repetition_des_clics17_18():
    root=Path(__file__).parent
    with tarfile.open(root/'archives/ka59_n3_sondes18.tar.gz') as archive:
        a=cloudpickle.loads(archive.extractfile('runs/ka59_n3_but_reouvert8_1/agent.pkl').read())
    c=next(iter(a.chaines.values()));before=copy.deepcopy(c.programme)
    e,d=proposer(c,a.images,a.actions,[1,2,3,4,6])
    assert e and d['support_vise']=='contour_adjacent'
    assert e['actions'][0] not in a.actions[-2:]
    assert d['contours_adjacents']==2
    assert np.array_equal(e['predictions'][0][0]['image'],c.perception.vue(a.images[-1]))
    assert c.programme==before
    episode={'grilles':[a.images[-1],a.images[-1]],'actions':e['actions']}
    suivant,_=proposer(c,a.images,a.actions,[1,2,3,4,6],[episode])
    assert suivant is None or suivant['actions'] != e['actions']
