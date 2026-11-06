import time
import multiprocessing
from rechercher_selection_portefeuille import portefeuille


def faux_worker(tache, stop, canal):
    poids=tache[2]
    if poids==3:
        canal.send({'poids':poids,'plan':[('INVALIDE',)],'cpu_s':0,'preuve':{}})
    else:
        time.sleep(.1)
        canal.send({'poids':poids,'plan':[('UP',)],'cpu_s':0,'preuve':{'stop_avant':stop.is_set()}})
    canal.close()


def worker_annulable(tache, stop, canal):
    poids=tache[2]
    if poids==10:
        canal.send({'poids':poids,'plan':[('UP',)],'cpu_s':0,'preuve':{}})
    else:
        assert stop.wait(5)
        canal.send({'poids':poids,'plan':None,'cpu_s':.01,'preuve':{'refus':'annulation'}})
    canal.close()


def test_invalide_ne_declenche_pas_annulation():
    r=portefeuille([('', '',w,1) for w in (3,10)],lambda p:p==[('UP',)],worker=faux_worker)
    gagnant=next(x for x in r if x.get('premier_plan_valide'))
    assert gagnant['poids']==10 and not gagnant['preuve']['stop_avant']
    assert all(x['enfants_termines'] for x in r)


def test_annulation_recoltee_et_aucun_enfant_vivant():
    avant={p.pid for p in multiprocessing.active_children()}
    r=portefeuille([('', '',w,1) for w in (3,10)],lambda p:True,worker=worker_annulable)
    assert any(x['preuve'].get('refus')=='annulation' for x in r)
    assert all(x['enfants_termines'] for x in r)
    assert {p.pid for p in multiprocessing.active_children()}==avant
    assert sum(x['cpu_s'] for x in r)==.01
