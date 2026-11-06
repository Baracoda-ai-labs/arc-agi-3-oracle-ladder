from types import SimpleNamespace
import numpy as np
from plan_selection_dynamique import actions_selection


def test_marqueur_rectangulaire_instance_et_deplacement():
    image=np.full((6,9),14);image[2:4,3:6]=5
    p={'pixels':image,'x':10,'y':20,'tags':['piece'],
       'attrs':{'marqueur_x':3,'marqueur_y':2,'marqueur_largeur':3,'marqueur_hauteur':2}}
    vue=SimpleNamespace(mx=1,my=1,selection=0)
    assert actions_selection(SimpleNamespace(sprites=[p]),vue)[-1]==('MOUSE',23,14)
    p['x']+=7;p['y']-=4
    assert actions_selection(SimpleNamespace(sprites=[p]),vue)[-1]==('MOUSE',19,21)
    p['pixels'][2:4,3:6]=0
    assert len(actions_selection(SimpleNamespace(sprites=[p]),vue))==4


def test_ancien_marqueur_sans_attributs_conserve():
    p={'pixels':np.full((3,3),5),'x':10,'y':20,'tags':['piece']}
    vue=SimpleNamespace(mx=1,my=1,selection=0)
    assert actions_selection(SimpleNamespace(sprites=[p]),vue)[-1]==('MOUSE',21,11)


def test_recherche_peut_depasser_quarante_actions():
    from chrysalide.arc3.langage import Programme
    from chrysalide.arc3.ontologie_exec import Scene
    from plan_selection_dynamique import chercher
    programme={'mode':'lois','etat':{},'regles':[
        {'nom':'avance','phase':0,'quand':['=',['action'],'RIGHT'],
         'alors':[['pour','$o',['objets',{'tag':'piece'}],[['deplacer','$o',1,0]]]]},
        {'nom':'but','phase':1,'quand':['existe','$o',['objets',{'tag':'piece'}],['=',['x','$o'],45]],
         'alors':[['niveau_suivant']]}]}
    def initial():
        return Programme(programme),Scene((64,64),0,0,[
            {'pixels':np.array([[1]]),'x':0,'y':0,'tags':['piece'],'couche':1},
            {'pixels':np.array([[2]]),'x':45,'y':0,'tags':['cible'],'couche':0}])
    def verifier(plan):
        pc,sc=initial()
        for action in plan:pc.step(sc,action)
        return sc.issue=='niveau',{'pas':len(plan)}
    chaine=SimpleNamespace(rejouer=lambda:({},initial()),verifier_plan=verifier)
    vue=SimpleNamespace(mx=0,my=0,selection=1,coque=np.ones((1,1)))
    plan,preuve=chercher(chaine,vue,secondes=2,max_noeuds=100)
    assert plan==[('RIGHT',)]*45 and preuve['valide']
