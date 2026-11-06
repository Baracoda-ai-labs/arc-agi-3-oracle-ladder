import copy
import pytest
import cache_fidelite_traduction as c

@pytest.fixture(autouse=True)
def propre():
    c.vider();yield;c.vider()

def test_ast_entier_inclus_mots_et_fonctions(monkeypatch):
    calls=[]
    def encoder(p):calls.append(1);return copy.deepcopy(p)
    decoder=lambda p:p
    p={'regles':[],'mots':{'x':{'corps':1}}}
    assert c.fidele(p,encoder,decoder) and c.fidele(copy.deepcopy(p),encoder,decoder)
    assert len(calls)==1
    p['mots']['x']['corps']=2
    assert c.fidele(p,encoder,decoder) and len(calls)==2
    assert c.fidele(p,encoder,lambda p:p) and len(calls)==3

def test_version_code_ontologie_invalide(monkeypatch,tmp_path):
    f=tmp_path/'ontologie.py';f.write_text('a');calls=[]
    monkeypatch.setattr(c,'versions',lambda:c._empreinte_fichiers([f]))
    def encoder(p):calls.append(1);return p
    decoder=lambda p:p
    assert c.fidele({},encoder,decoder)
    f.write_text('b')
    assert c.fidele({},encoder,decoder) and len(calls)==2

def test_refus_cache_et_exception_pas_admise():
    enc=lambda p:p;dec=lambda p:{'different':True}
    assert not c.fidele({},enc,dec) and not c.fidele({},enc,dec)
    assert c.statistiques()['hits']==1
    def erreur(p):raise ValueError('refus')
    with pytest.raises(ValueError):c.fidele({},enc,erreur)
    assert c.statistiques()['entrees']==1

def test_borne_lru_et_cache_contient_uniquement_booleens(monkeypatch):
    monkeypatch.setattr(c,'versions',lambda:())
    identity=lambda p:p
    for n in range(c.MAX_ENTREES+2):assert c.fidele({'n':n},identity,identity)
    assert len(c._CACHE)==c.MAX_ENTREES
    assert all(type(v) is bool for v in c._CACHE.values())
    avant=c.statistiques()['misses'];c.fidele({'n':0},identity,identity)
    assert c.statistiques()['misses']==avant+1

def test_traducteur_reel_meme_contrat_froid_chaud():
    import json
    from chrysalide.langue import vers_python,depuis_python
    p={'regles':[],'mots':{}}
    attendu=json.dumps(depuis_python(vers_python(p)),sort_keys=True)==json.dumps(p,sort_keys=True)
    assert c.fidele(p,vers_python,depuis_python)==attendu
    assert c.fidele(copy.deepcopy(p),vers_python,depuis_python)==attendu
    assert c.statistiques()['hits']==1
