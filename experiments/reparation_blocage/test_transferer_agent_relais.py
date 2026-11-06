import json
from types import SimpleNamespace
import numpy as np
import pytest
import transferer_agent_relais as t
from session_sdk_observee import RelaisSDK
from avancer_agent_relais import sauver_agent,charger_agent


def preparer(tmp_path,monkeypatch):
    image=np.zeros((64,64),dtype=int)
    root=tmp_path/'sdk';root.mkdir()
    class Lab:
        def __init__(self,output,level=1,won=True):
            self.output=output;output.parent.mkdir(parents=True,exist_ok=True)
            self.env=object();self.level=level;self.won=won;self.finished=won;self.partie_gagnee=False
            self.rows=[dict(action=1,levels_completed=1,state='NOT_FINISHED')] if won else []
            self.image=image;self.actions_disponibles=[1,2]
            output.with_suffix('.json').write_text(json.dumps({'rows':self.rows}))
            np.savez(output.with_suffix('.npz'),images=[image,image] if won else [image])
        def next_level(self,output):
            nouveau=Lab(output,2,False);nouveau.env=self.env;return nouveau
    lab=Lab(root/'N1/partie');relay=RelaisSDK(lab,root,jeu='faux')
    old=SimpleNamespace(images=[image,image],actions=[1],attente=None,modele_gagnant='preuve')
    source=tmp_path/'gagnant.pkl';sauver_agent(old,source);calls=[]
    def demander(root,cmd):calls.append(cmd['op']);return relay.traiter(cmd)
    monkeypatch.setattr(t,'demander',demander)
    def transfert(old,image,offre):
        return SimpleNamespace(images=[image],actions=[],attente=None,modele_transfere=old.modele_gagnant)
    monkeypatch.setattr(t,'agent_transfere',transfert)
    return source,relay,calls


def test_transfert_aligne_sans_coup_sans_modifier_source(tmp_path,monkeypatch):
    source,relay,calls=preparer(tmp_path,monkeypatch)
    original=source.read_bytes();env=relay.lab.env
    out=tmp_path/'out';etat=t.transferer(tmp_path/'sdk',source,out)
    assert calls==['status','status','next_level']
    assert etat['niveau']==2 and etat['coups_reels']==1 and relay.lab.env is env
    assert source.read_bytes()==original
    assert charger_agent(out/'agent.pkl').actions==[]
    bilan=json.loads((out/'bilan.json').read_text())
    assert bilan['statut']=='transfert_aligne'
    assert bilan['actions_nouvelles']==bilan['initialisations_nouvelles']==bilan['coups_reacces_nouveaux']==0


def test_prevalidation_refusee_ne_transite_pas(tmp_path,monkeypatch):
    source,relay,calls=preparer(tmp_path,monkeypatch)
    def refus(*args):raise ValueError('Modèle ambigu')
    monkeypatch.setattr(t,'agent_transfere',refus)
    with pytest.raises(ValueError,match='ambigu'):t.transferer(tmp_path/'sdk',source,tmp_path/'out')
    assert calls==['status'] and relay.lab.level==1 and relay.lab.won
    assert not json.loads((tmp_path/'out/bilan.json').read_text())['transition_envoyee']
