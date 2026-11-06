from types import SimpleNamespace as S
import numpy as np
import session_chaine_generique as session
import transfert_modele_c


def test_transfert_garde_les_deux_hypotheses_confirmees_pas_le_but_non_valide(monkeypatch):
    def modele(n):return S(perception=S(),nom=n,grilles=[],lots=[],films=S(entrees=[]))
    un,deux,inconnu=map(modele,('un','deux','inconnu'));calls=[]
    def reaffecter(source,*args,**kwargs):
        calls.append(source.nom);return S(perception=S(),nom=source.nom),{}
    monkeypatch.setattr(transfert_modele_c,'reaffecter',reaffecter)
    monkeypatch.setattr(session,'nouvel_agent',lambda *args,**kwargs:S(journal=[]))
    ancien=S(modele_gagnant=un,modeles_avant_victoire={'un':un,'deux':deux,'inconnu':inconnu},
        journal=[{'type':'memoire_issue_observee','candidats':[
            {'nom':'un','but_confirme_par_prediction':True},
            {'nom':'deux','but_confirme_par_prediction':True},
            {'nom':'inconnu','but_confirme_par_prediction':False}]}],
        precedents=[],actions=[1],commandes_connues={1})
    a=session.agent_transfere(ancien,np.zeros((64,64)),[1])
    assert calls==['un','deux']
    assert len(a.chaines)==2 and a.journal[-1]['regles_reapprises']==0
