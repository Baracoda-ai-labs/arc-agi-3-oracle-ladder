from pathlib import Path
import sys
import pytest
import attestation_moteur_commun as a


def attester(tmp_path,monkeypatch):
 p=tmp_path/'agent.py';p.write_text('code')
 monkeypatch.setattr(a,'natives_et_metadonnees',lambda:({},{}))
 return p,a.construire(tmp_path,env={'PYTHONPATH':'explicit','PYTHONHASHSEED':'0'})

@pytest.mark.parametrize('cas',['modifie','absent','inconnu'])
def test_dependance_non_conforme(tmp_path,monkeypatch,cas):
 p,m=attester(tmp_path,monkeypatch);declaration={str(p):a.sha(p)}
 if cas=='modifie':p.write_text('nouveau code')
 elif cas=='absent':p.unlink()
 else:
  q=tmp_path/'non_prevue.py';q.write_text('import tardif');declaration[str(q)]=a.sha(q)
 r=a.verifier(m,declaration)
 assert r['statut']=='non_atteste' and r['problemes']
 assert not r['fermeture_complete']

def test_reference_astra_json_et_natif_inventories(tmp_path):
 dossier=tmp_path/'paquet/references/astra4/livraison_astra4/ajouts/boucle_v4';dossier.mkdir(parents=True)
 paths=[dossier/'economie.py',dossier/'contrats.json',dossier/'native.so']
 for p in paths:p.write_bytes(b'contenu_test')
 assert set(a.inventaire(tmp_path))=={str(p) for p in paths}

def test_interpreteur_environnement_declaration_requise(tmp_path,monkeypatch):
 p,m=attester(tmp_path,monkeypatch)
 assert m['interpreteur']['chemin_resolu']==str(Path(sys.executable).resolve())
 assert m['environnement']['PYTHONPATH']=='explicit'
 assert a.verifier(m)['statut']=='non_atteste'
 assert a.verifier(m,{str(p):a.sha(p)})['statut']=='inventaire_declare_conforme_couverture_partielle'


def test_natif_modifie_detecte(tmp_path,monkeypatch):
 native=tmp_path/'extension.so';native.write_bytes(b'original')
 monkeypatch.setattr(a,'natives_et_metadonnees',lambda:({str(native):a.sha(native)},{'module':{'version':'1'}}))
 m=a.construire(tmp_path,env={});native.write_bytes(b'modifie')
 assert any(p['raison']=='modifie' for p in a.verifier(m,{} )['problemes'])
