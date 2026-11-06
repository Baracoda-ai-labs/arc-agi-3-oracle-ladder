"""Gardes et compteurs avec faux laboratoire ; aucune ouverture SDK."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
import banc_t4_integre as banc
import boucle_agent_integree as pilote


def faux_catalogue(tmp_path,monkeypatch):
    root=tmp_path/'environment_files';root.mkdir();rows=[]
    for i in range(104):
        ident=f'y{i:03d}';version='abc';p=root/ident/version/'metadata.json';p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'game_id':ident+'-'+version}))
        rows.append({'id':ident,'version':version,'game_id':ident+'-'+version,'metadata_sha256':banc.sha(p)})
    inventaire=tmp_path/'inventaire.json';inventaire.write_text(json.dumps({'root':str(root),'records':rows}))
    monkeypatch.setattr(banc,'RACINE_T4',root.resolve())
    return root,inventaire


def test_catalogue_exact_et_racine_publique_refusee(tmp_path,monkeypatch):
    root,inv=faux_catalogue(tmp_path,monkeypatch)
    ids,rows=banc.catalogue(inv,root)
    assert len(ids)==104 and ids==sorted(ids)
    with pytest.raises(ValueError,match='Racine'):
        banc.catalogue(inv,tmp_path/'publics20c')
    p=root/'y000'/'abc'/'metadata.json';p.write_text('{}')
    with pytest.raises(ValueError,match='Métadonnées'):
        banc.catalogue(inv,root)


def test_cli_public_ne_devient_pas_synthetique(tmp_path):
    args=argparse.Namespace(jeu='y000',sortie=tmp_path/'run',coups=80,secondes=240,sans_reparation=False)
    with pytest.raises(ValueError,match='non autorisé'):
        pilote.main(args)
    with pytest.raises(ValueError,match='ensemble'):
        pilote.main(args,dossier_jeux=tmp_path)


@pytest.mark.parametrize('synthetique',[False,True])
def test_memes_offres_et_compteurs_avec_adaptateur(tmp_path,synthetique):
    calls=[]
    class Labo:
        def __init__(self,jeu,niveau,racine,out):
            calls.append((jeu,niveau,racine))
            avant=json.loads((out.parent.parent/'bilan.json').read_text())
            assert avant['initialisations_tentees']==1 and avant['initialisations']==0
            out.parent.mkdir(parents=True)
            np.savez(out.with_suffix('.npz'),images=np.zeros((1,64,64),dtype=np.int16))
            self.rows=[];self.actions_disponibles=[5];self.finished=False;self.won=False;self.partie_gagnee=False
        def play(self,a,purpose):
            assert a in self.actions_disponibles
            self.rows.append({'action':a,'purpose':purpose,'state':'GAME_OVER','levels_completed':0})
            self.finished=True
            return np.zeros((64,64),dtype=np.int16),np.zeros((1,64,64),dtype=np.int16)
    class Agent:
        def __init__(self,*a):self.revisions=0;self.journal=[]
        def decider(self,offre,*a,**k):
            assert offre==[5]
            return {'actions':[5],'statut':'experience_conditionnelle','predictions':[]}
        def observer(self,*a):return {'type':'observation'}
    jeu='y000' if synthetique else 'ar25'
    args=argparse.Namespace(jeu=jeu,sortie=tmp_path/'run',coups=8,secondes=2,sans_reparation=False)
    kwargs={'dossier_jeux':tmp_path/'t4','jeux_autorises':['y000']} if synthetique else {}
    with patch.object(pilote,'LaboP1',Labo),patch.object(pilote,'AgentIntegre',Agent),patch.object(pilote,'empreintes',return_value={}):
        pilote.main(args,**kwargs)
    bilan=json.loads((args.sortie/'bilan.json').read_text())
    assert bilan['coups_reels']==bilan['appels_step_tentes']==1
    assert bilan['initialisations']==1 and bilan['initialisations_tentees']==1
    assert calls==[(jeu,1,str(tmp_path/'t4') if synthetique else '/Users/ts/models/chrysalide3/experiments/G/publics20c')]


def test_reprise_saute_termines_et_refuse_partiel(tmp_path,monkeypatch):
    root,inv=faux_catalogue(tmp_path,monkeypatch)
    monkeypatch.setattr(banc,'sources',lambda:{'code':'fige'})
    count=[]
    def run(cmd,log,timeout):
        dest=Path(cmd[cmd.index('--sortie')+1]);dest.mkdir()
        (dest/'bilan.json').write_text(json.dumps({'niveaux_gagnes':0,'coups_reels':8,'appels_step_tentes':8,'initialisations':1}))
        count.append(dest.name)
        return 'termine',0
    monkeypatch.setattr(banc,'executer_worker',run)
    args=argparse.Namespace(racine=root,inventaire=inv,coups=80,secondes=240,sortie=tmp_path/'out',reprendre=False)
    res=banc.lancer(args)
    assert len(count)==104 and res['coups_confirmes']==832 and res['complet']
    args.reprendre=True;banc.lancer(args)
    assert len(count)==104
    (args.sortie/'y103'/'resultat_runner.json').unlink()
    with pytest.raises(ValueError,match='partielle'):
        banc.lancer(args)
    assert len(count)==104


def test_preparation_aucun_worker_puis_reprise(tmp_path,monkeypatch):
    root,inv=faux_catalogue(tmp_path,monkeypatch)
    monkeypatch.setattr(banc,'sources',lambda:{'code':'fige'})
    def interdit(*a,**k):raise AssertionError('Aucun worker en préparation')
    monkeypatch.setattr(banc,'executer_worker',interdit)
    args=argparse.Namespace(racine=root,inventaire=inv,coups=80,secondes=240,
                            sortie=tmp_path/'out',reprendre=False,preparer=True)
    res=banc.lancer(args)
    assert res['jeux_termines']==0 and res['jeux_prevus']==104
    assert (args.sortie/'manifeste.json').exists()
    assert not list(args.sortie.glob('*.stdout'))
    args.reprendre=True
    assert banc.lancer(args)['jeux_termines']==0


def test_timeout_tue_seulement_groupe_worker_cree(monkeypatch):
    import signal,subprocess
    appels=[]
    class Process:
        pid=987654321  # PID fictif ; os.killpg est remplacé ci-dessous.
        returncode=None
        def wait(self,timeout=None):
            appels.append(('wait',timeout))
            if timeout is not None:raise subprocess.TimeoutExpired(['worker'],timeout)
            self.returncode=-signal.SIGKILL
            return self.returncode
    def popen(cmd,**kwargs):
        assert kwargs['start_new_session'] is True
        appels.append(('create',tuple(cmd)))
        return Process()
    monkeypatch.setattr(banc.subprocess,'Popen',popen)
    monkeypatch.setattr(banc.os,'killpg',lambda pid,sig:appels.append(('killpg',pid,sig)))
    status,code=banc.executer_worker(['worker'],None,255)
    assert status=='timeout_superviseur' and code==-signal.SIGKILL
    assert appels==[('create',('worker',)),('wait',255),('killpg',987654321,signal.SIGKILL),('wait',None)]


def test_agregat_initialisations_inconnues_non_confondues_avec_zero(tmp_path):
    for ident,bilan in [('y000',{'initialisations':0,'initialisations_tentees':1}),('y001',{})]:
        dossier=tmp_path/ident;dossier.mkdir()
        banc.ecrire(dossier/'resultat_runner.json',{'jeu':ident,'bilan':bilan,'coups_incident_inconnus':not bool(bilan)})
    res=banc.agreger(tmp_path,['y000','y001'])
    assert res['initialisations_confirmees']==0 and res['initialisations_tentees']==1
    assert res['initialisations_tentees_inconnues']==1 and res['incidents_coups_inconnus']==1
