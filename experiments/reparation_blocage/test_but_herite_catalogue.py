"""But transféré conservé au catalogue, sauf réfutation par état non terminal."""
import copy
import numpy as np
import pytest
from test_motif_neutre import cible
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import MoteurC
from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.logique.export_langage import exporter
from transfert_modele_c import reaffecter
from buts_modele_conserve import candidats


@pytest.mark.parametrize('deja_atteint',[False,True])
def test_but_herite_reexamine_apres_vrai_transfert(monkeypatch,deja_atteint):
    monkeypatch.setenv('CHRYS_PAIRES_COULEUR','0')
    monde=cible(neutre=True,erreur=not deja_atteint)
    g=np.zeros((64,64),dtype=int)
    for couleur,forme,x,y in monde:
        for dx,dy in forme:g[y+dy,x+dx]=couleur
    but=('motif_rel',1,2,(3,))
    tr=Trajectoire([g.tolist()],[],ech=(1,0,0))
    th=Theorie(but=but,buts_motifs=[but])
    m=MoteurC();m.tr=tr;m.th_releve=th;m._couches=th.couches()
    programme,non=exporter(th,tr.taille);assert not non
    source=Chaine(m,programme,[g.tolist()],[],[('RIGHT',)])
    original=copy.deepcopy(th);signature=source.signature()
    transferee,_=reaffecter(source,g,[('RIGHT',)])
    assert transferee.perception.th_releve.but==but
    assert not transferee.perception.th_releve.buts_motifs
    assert transferee.perception.th_releve.atteint(transferee.perception.tr.etats[0])==deja_atteint
    buts=[b for b,_ in candidats(transferee,[('RIGHT',)])]
    assert (but in buts)==(not deja_atteint)
    assert source.perception.th_releve==original and source.signature()==signature
    assert transferee.perception.th_releve.buts_motifs==[]
