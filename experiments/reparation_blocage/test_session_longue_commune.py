import io,json
import pytest
from session_longue_commune import Proprietaire

class Clock:
    now=0
    def __call__(self):return self.now

class FauxSession:
    pid=1234
    def __init__(self):
        self.stdin=self;self.commands=[];self.pending='';self.memory=[];self.cpu=0;self.closed=False
    def write(self,text):self.pending+=text
    def flush(self):
        cmd=json.loads(self.pending);self.pending='';self.commands.append(cmd)
        if cmd['op']=='auto':self.memory.append(len(self.memory)+1);self.cpu+=2
        elif cmd['op']=='close':self.closed=True
    def poll(self):return 0 if self.closed else None
    def etat(self):return {'pid':self.pid,'statut':'auto_lots_termines_session_conservee','coups_reels':len(self.memory),'cpu_total_recolte_s':self.cpu,'niveaux_gagnes':0}


def preparer(tmp_path):
    clock=Clock();child=FauxSession();owner=Proprietaire(tmp_path,child,clock)
    owner.recevoir({'statut':'prete_nouvelle_boucle','pid':1234,'niveaux_gagnes':0})
    return owner,child,clock


def test_checkpoint_conserve_pid_memoire_compteurs_sans_reset(tmp_path):
    p,c,t=preparer(tmp_path);memoire=c.memory
    p.commander({'op':'continue','secondes':1200});p.tick()
    assert p.attente and c.memory==[1]
    t.now=1201;p.tick() # Ne coupe pas une commande en cours.
    assert not c.closed and p.attente
    p.recevoir(c.etat());p.tick()
    assert p.statut=='checkpoint_session_conservee' and p.deadline is None
    assert [x['op'] for x in c.commands]==['auto']
    t.now=1300;p.commander({'op':'continue','secondes':1200,'preuve_progression':'observation nouvelle journal#8'});p.tick();p.recevoir(c.etat())
    assert c.memory is memoire and c.memory==[1,2] and c.pid==1234
    assert p.etat()['session']['cpu_total_recolte_s']==4
    assert p.etat()['session']['coups_reels']==2
    assert p.etat()['secondes_actives']==1201
    assert not c.closed and all(x['op']=='auto' for x in c.commands)


def test_pas_commandes_concurrentes(tmp_path):
    p,c,t=preparer(tmp_path);p.commander({'op':'continue'});p.tick();p.tick()
    assert len(c.commands)==1
    with pytest.raises(ValueError):p.commander({'op':'continue'})
    assert p.commander({'op':'status'})['commande_en_cours']
    with pytest.raises(ValueError):p.commander({'op':'close'})


def test_victoire_n1_pas_next_level(tmp_path):
    p,c,t=preparer(tmp_path);p.commander({'op':'continue'});p.tick()
    p.recevoir({**c.etat(),'niveaux_gagnes':1,'statut':'niveau_gagne'});p.tick()
    assert p.statut=='n1_gagne_session_conservee' and len(c.commands)==1 and not c.closed
    with pytest.raises(ValueError):p.commander({'op':'continue','preuve_progression':'victoire'})


def test_diagnostic_ne_boucle_pas_et_pause_ne_ferme_pas(tmp_path):
    p,c,t=preparer(tmp_path);p.commander({'op':'continue'});p.tick()
    p.recevoir({**c.etat(),'statut':'diagnostic_requis'});p.tick()
    assert len(c.commands)==1 and not c.closed
    with pytest.raises(ValueError):p.commander({'op':'continue','preuve_progression':'x'})
    p.commander({'op':'close'});assert c.closed


def test_reprise_exige_reference_et_processus_vivant(tmp_path):
    p,c,t=preparer(tmp_path);p.commander({'op':'pause'})
    with pytest.raises(ValueError,match='preuve'):p.commander({'op':'continue'})
    c.closed=True
    with pytest.raises(ValueError,match='perdu'):p.commander({'op':'continue','preuve_progression':'trace'})

@pytest.mark.parametrize('v',[0,-1,True,float('nan'),float('inf')])
def test_duree_invalide(tmp_path,v):
    p,c,t=preparer(tmp_path)
    with pytest.raises(ValueError):p.commander({'op':'continue','secondes':v})

def test_boite_commandes_avec_vrai_processus_factice_sans_sdk(tmp_path):
    import sys,threading,time
    from session_longue_commune import owner,lire,sauver
    script=tmp_path/'fake.py'
    script.write_text('''import sys,json,os
n=0
print(json.dumps(dict(statut='prete_nouvelle_boucle',pid=os.getpid(),niveaux_gagnes=0)),flush=True)
for line in sys.stdin:
 c=json.loads(line)
 if c['op']=='close':break
 n+=1
 print(json.dumps(dict(statut='auto_lots_termines_session_conservee',pid=os.getpid(),coups_reels=n,cpu_total_recolte_s=n*2,niveaux_gagnes=0,memoire=list(range(n)))),flush=True)
''')
    sauver(tmp_path/'lancement.json',{'argv':[sys.executable,'-u',str(script)],'cwd':str(tmp_path)})
    worker=threading.Thread(target=owner,args=(tmp_path,),daemon=True);worker.start()
    def attendre(pred):
        limite=time.monotonic()+4
        while time.monotonic()<limite:
            d=lire(tmp_path/'owner.json')
            if pred(d):return d
            time.sleep(.02)
        pytest.fail('reponse proprietaire factice absente')
    d=attendre(lambda d:d.get('statut')=='checkpoint_session_conservee');pid=d['pid_session']
    sauver(tmp_path/'commande_1.json',{'op':'continue','secondes':.08})
    d=attendre(lambda d:d.get('checkpoints',0)>=1);n=d['session']['coups_reels']
    sauver(tmp_path/'commande_2.json',{'op':'continue','secondes':.08,'preuve_progression':'test observation'})
    d=attendre(lambda d:d.get('checkpoints',0)>=2)
    assert d['pid_session']==pid and d['session']['coups_reels']>n
    assert d['session']['memoire']==list(range(d['session']['coups_reels']))
    assert d['session']['cpu_total_recolte_s']==2*d['session']['coups_reels']
    sauver(tmp_path/'commande_3.json',{'op':'close'});worker.join(timeout=4)
    assert not worker.is_alive()
