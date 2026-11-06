from types import SimpleNamespace
import numpy as np
import pytest
from session_sdk_observee import RelaisSDK,empreinte_image

class Lab:
    def __init__(self):
        self.image=np.zeros((64,64),int);self.rows=[];self.level=1
        self.won=self.partie_gagnee=self.finished=False;self.actions_disponibles=[1,6]
        self.env=object();self.output=__import__('pathlib').Path('/tmp/test_trace')
    def play(self,a,purpose):
        self.rows.append({'action':a});self.image[0,0]+=1
    def next_level(self,path):
        l=Lab();l.env=self.env;l.level=self.level+1;l.output=path;return l

def test_action_perimee_ne_joue_pas_et_compteur_persiste(tmp_path):
    l=Lab();r=RelaisSDK(l,tmp_path,20);h=empreinte_image(l.image)
    r.traiter({'op':'play','action':1,'image_sha256':h,'coup_total_avant':20})
    assert r.etat()['coups_reels']==21 and r.etat()['coups_nouveaux']==1
    with pytest.raises(ValueError,match='périmée'):r.traiter({'op':'play','action':1,'image_sha256':h,'coup_total_avant':20})
    assert len(l.rows)==1 and r.tentes==21
    l.won=True;l.finished=True
    r.traiter({'op':'next_level'})
    assert r.lab.env is l.env and r.etat()['coups_reels']==21
    r.traiter({'op':'play','action':1,'image_sha256':empreinte_image(r.lab.image),'coup_total_avant':21})
    assert r.etat()['coups_reels']==22


def test_coup_inerte_ne_peut_pas_etre_double(tmp_path):
    l=Lab();r=RelaisSDK(l,tmp_path)
    l.play=lambda a,purpose:l.rows.append({'action':a})
    cmd={'op':'play','action':1,'image_sha256':empreinte_image(l.image),'coup_total_avant':0}
    r.traiter(cmd)
    with pytest.raises(ValueError,match='périmée'):r.traiter(cmd)
    assert len(l.rows)==1
