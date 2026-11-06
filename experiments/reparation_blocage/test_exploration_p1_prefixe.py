import numpy as np
from test_utilite_sondes import agent
from exploration_p1_prefixe import GrapheIntegral, proposer
from types import SimpleNamespace


def test_prefixe7_choix_nouveau_sans_sdk():
    ancien=agent(7,True)
    assert ancien.decider([6])['actions']==[]
    nouveau=agent(7,True); nouveau.exploration_p1=True
    r=nouveau.decider([6])
    assert r['actions'] and r['origine']=='p1_graphe_observe'
    assert r['risque']=='inconnu' and r['masque']==[]
    assert r['modeles'] and r['modeles']==[p['nom'] for p in r['predictions'][0]]
    assert set(r['modeles']) <= set(nouveau.chaines)
    assert all(nouveau.chaines[n].plan['origine']=='experience_p1_observee' for n in r['modeles'])
    assert len(nouveau.actions)==7 and nouveau.attente==r
    print('PREFIXE7',r)


def test_bord_conserve_et_retour_connu():
    im=np.zeros((64,64),dtype=int); im[10:13,10:13]=2
    autre=im.copy();autre[-1,0]=1
    e=GrapheIntegral(SimpleNamespace(image=im,actions_disponibles=[6]),None)
    assert e.cle(im)!=e.cle(autre)
    r=proposer([im,autre,im],[['clic',11,11],['clic',11,11]],['continue']*2,[6])
    # Return serves an actual untried frontier (the observed border object).
    assert r['raison']=='vers_meilleure_frontiere'
    assert proposer([im,im],[['clic',11,11]],['continue'],[6]) is None


def test_releve_borne_et_sans_historique_future(monkeypatch):
    from chrysalide.arc3.moteur import MoteurC
    a=agent(25,True);a.exploration_p1=True
    calls=[]
    def proposer_m(self,h):
        calls.append(h);self.infos={'refus':'controle'};return None
    monkeypatch.setattr(MoteurC,'proposer',proposer_m)
    a._relever_p1(1);a._relever_p1(1)
    assert len(calls)==1 and len(calls[0]['lots'])==25 and calls[0]['precedents']==[]


def test_releve_reelle_prefixe25_et_plan_consomme(monkeypatch):
    monkeypatch.setenv('CHRYS_BUT_SUPPOSE','1')
    monkeypatch.setenv('CHRYS_CHAINE_COHERENTE','1')
    a=agent(25,True);a.exploration_p1=True
    decision=a.decider([6])
    assert decision['modele_plan']=='p1_but_hypothese'
    c=a.chaines['p1_but_hypothese']
    assert c.plan and decision['but']=='hypothese_non_prouvee'
    # Simulation seulement : restituer l'image prédite dans la vue conservée.
    from chaine_agent_integree import canon
    prediction=a._predire(c,canon(decision['actions'][0]))
    im=a.images[-1].copy(); m=c.perception; tr=m.tr
    view=np.asarray(prediction['image'])
    for y in range(view.shape[0]):
        for x in range(view.shape[1]):
            if view[y,x]>=0:
                im[tr.oy+y*tr.s:tr.oy+(y+1)*tr.s,tr.ox+x*tr.s:tr.ox+(x+1)*tr.s]=view[y,x]
    suite=[list(action) for action in decision['suite_plan']]
    assert suite
    a.observer(decision['actions'][0],im,[im],'continue')
    assert c.plan and c.plan['actions']==suite
    assert c.plan['origine']=='suite_revalidee_apres_observation'
    assert c.verifier_plan(c.plan['actions'])[0]
    assert a.attente is None and len(a.actions)==26
    suivant=a.decider([6])
    from chaine_agent_integree import sdk
    assert suivant['actions']==[sdk(tuple(suite[0]))] and a.attente is suivant
    assert suivant['modele_plan']=='p1_but_hypothese'


def test_catalogue_non_tronque_sur_prefixe_reel46():
    import json
    from pathlib import Path
    from agent_p1.generique import objets, Explorateur
    p=Path(__file__).parent/'runs/exploration_solution_ft09_1/reel/N1/partie'
    z=np.load(p.with_suffix('.npz'));images=z['images']
    actions=json.loads(p.with_suffix('.json').read_text())['actions']
    assert len(actions)==46 and all(np.array_equal(images[0],im) for im in images)
    lab=SimpleNamespace(image=images[0],actions_disponibles=[6])
    ancien=Explorateur(lab,None); nouveau=GrapheIntegral(lab,None)
    avant=ancien.candidats(images[0]);apres=nouveau.candidats(images[0])
    assert len(avant)==46 and set(avant)<set(apres)
    assert {(a[1],a[2]) for a in apres}=={(o['x'],o['y']) for o in objets(images[0])}
    r=proposer(images,actions,['continue']*46,[6])
    assert r is not None and r['actions'][0] not in actions
    assert tuple(r['actions'][0]) not in avant
    print('CATALOGUE',len(avant),len(apres),'NEXT',r['actions'])
