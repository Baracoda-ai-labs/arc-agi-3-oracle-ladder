import copy,json
import pytest
import campagne_moteur_commun as c

def manifeste():
 return dict(version=2,recherche_prolongee=False,recherche_workers=1,jeux=['ar25'],graines=[0,1],limites=dict(actions_jeu=80,actions_niveau=40,mur_jeu_s=1200,mur_commande_s=300,cpu_jeu_s=1000),composition_contextuelle_auto=True,reprises=True,memoire_inter_jeux='aucune')

def test_exemple_inexecutable():
 with pytest.raises(ValueError,match='Budget non fixé'):c.valider(json.loads((c.R/'CAMPAGNE_MOTEUR_COMMUN_EXEMPLE.json').read_text()))

@pytest.mark.parametrize('jeu',['cn04','s5i5','tu93','vc33','wa30','inconnu'])
def test_refus_jeux(jeu):
 m=manifeste();m['jeux']=[jeu]
 with pytest.raises(ValueError):c.valider(m)

@pytest.mark.parametrize('champ',['agent.pkl','source','prefixe','memoire_depart'])
def test_aucune_entree_snapshot(champ):
 m=manifeste();m[champ]='interdit'
 with pytest.raises(ValueError):c.valider(m)

def test_commande_aveugle(tmp_path):
 m=c.valider(manifeste());cmd=c.commande('ar25',1,tmp_path,m)
 assert '--neuf' in cmd and '--graine' in cmd and '--composition-contextuelle-auto' in cmd
 assert not any(x in cmd for x in ('--source','--prefixe','--transfert-depuis'))

def test_export_tentatives_victoire_pas_attribution(tmp_path):
 for d,rows in [('N1',[{'action':1,'state':'NOT_FINISHED','levels_completed':0},{'action':2,'state':'GAME_OVER','levels_completed':0}]),('N1/tentative_2',[{'action':0,'state':'NOT_FINISHED','levels_completed':0},{'action':1,'state':'NOT_FINISHED','levels_completed':1}])]:
  p=tmp_path/d;p.mkdir(parents=True,exist_ok=True);(p/'partie.json').write_text(json.dumps({'rows':rows}))
 assert c.niveaux(tmp_path)==[dict(niveau=1,victoire=True,coups=4,resets=1,defaites=1,gagnant=None,attribution='non_evaluable')]

def test_cpu_groupe_garde_enfant_disparu(monkeypatch):
 sorties=iter(['10 10 0:02\n11 10 0:03\n12 12 2:00\n','10 10 0:04\n'])
 monkeypatch.setattr(c.subprocess,'check_output',lambda *a,**k:next(sorties));h={}
 assert c.cpu_groupe(10,h)==5
 assert c.cpu_groupe(10,h)==7

def test_campagne_sequentielle_sources_et_resultats(tmp_path,monkeypatch):
 m=manifeste();m['jeux']=['ar25','ka59'];p=tmp_path/'p.json';p.write_text(json.dumps(m));out=tmp_path/'sortie'
 monkeypatch.setattr(c.sys,'argv',['campagne','--protocole',str(p),'--sortie',str(out)])
 monkeypatch.setattr(c,'sources',lambda:{'module':'sha'})
 monkeypatch.setattr(c.subprocess,'check_output',lambda *a,**kw:'commit\n')
 monkeypatch.setattr(c.platform,'platform',lambda:'plateforme_mock')
 appels=[]
 def execute(jeu,graine,sortie,config):
  appels.append((graine,jeu));return {'attribution_cf2a1f81':'non_evaluable'}
 monkeypatch.setattr(c,'executer',execute);c.main()
 assert appels==[(0,'ar25'),(0,'ka59'),(1,'ar25'),(1,'ka59')]
 assert len(json.loads((out/'resume.json').read_text()))==4

@pytest.mark.parametrize('intermediaire',[None,'auto_lots_termines_session_conservee','diagnostic_requis','statut_inconnu'])
def test_session_mock_pilote_auto_un_coup_et_ferme(tmp_path,monkeypatch,intermediaire):
 import io
 monkeypatch.setattr('attestation_moteur_commun.construire',lambda *args,**kw:{'fixture':True})
 monkeypatch.setattr('attestation_moteur_commun.verifier',lambda *args,**kw:{'statut':'non_atteste'})
 class Processus:
  pid=12345;returncode=None
  def __init__(self,*args,**kwargs):
   messages=[{'statut':'prete_nouvelle_boucle','niveau':1,'coups_reels':8}]
   if intermediaire:messages.append({'statut':intermediaire,'niveau':1,'coups_reels':9})
   messages.append({'statut':'jeu_gagne','jeu_gagne':True,'niveau':1,'coups_reels':10})
   self.stdin=io.StringIO();self.stdout=iter(json.dumps(x)+'\n' for x in messages)
   assert kwargs['start_new_session'] is True
  def poll(self):return self.returncode
  def wait(self,timeout):self.returncode=0;return 0
 proc=Processus(start_new_session=True)
 def ouvrir(*args,**kw):
  assert kw['start_new_session'] is True
  return proc
 monkeypatch.setattr(c.subprocess,'Popen',ouvrir)
 monkeypatch.setattr(c,'cpu_groupe',lambda *args:0)
 b=c.executer('ar25',0,tmp_path/'jeu',manifeste())
 lignes=[json.loads(x) for x in proc.stdin.getvalue().splitlines()]
 nb_auto=2 if intermediaire=='auto_lots_termines_session_conservee' else 1
 assert lignes==[{'op':'auto','lots':1,'coups':1,'reprises':True}]*nb_auto+[{'op':'close'}]
 assert b['statut']==(intermediaire if intermediaire in ('diagnostic_requis','statut_inconnu') else 'jeu_gagne')
 assert b['attribution_cf2a1f81']=='non_evaluable'


@pytest.mark.parametrize('actif,workers',[(False,1),(False,2),(True,1),(True,2)])
def test_options_recherche_explicites_dans_commande(actif,workers,tmp_path):
 m=manifeste();m.update(recherche_prolongee=actif,recherche_workers=workers)
 cmd=c.commande('ar25',0,tmp_path,c.valider(m))
 assert ('--recherche-prolongee' in cmd)==actif
 assert cmd[cmd.index('--recherche-workers')+1]==str(workers)

@pytest.mark.parametrize('valeur',[0,3,True,1.0,'1',None])
def test_limite_workers_stricte(valeur):
 m=manifeste();m['recherche_workers']=valeur
 with pytest.raises(ValueError):c.valider(m)

@pytest.mark.parametrize('champ',['recherche_prolongee','recherche_workers'])
def test_options_absentes_pas_activation_cachee(champ):
 m=manifeste();del m[champ]
 with pytest.raises(ValueError,match='Schéma'):c.valider(m)

def test_ancienne_version_refusee_et_activation_booleenne():
 m=manifeste();m['version']=1
 with pytest.raises(ValueError,match='Schéma'):c.valider(m)
 m=manifeste();m['recherche_prolongee']='oui'
 with pytest.raises(ValueError,match='booléen'):c.valider(m)

@pytest.mark.parametrize('phase',['acquisition','decision'])
def test_n1_arrete_avant_next_level(tmp_path,monkeypatch,phase):
 import io
 monkeypatch.setattr('attestation_moteur_commun.construire',lambda *args,**kw:{})
 monkeypatch.setattr('attestation_moteur_commun.verifier',lambda *args,**kw:{'statut':'non_atteste'})
 debut={'statut':'prete_nouvelle_boucle','niveau':1,'coups_reels':8,'niveaux_gagnes':int(phase=='acquisition')}
 fin={'statut':'niveau_gagne','niveau':1,'coups_reels':9,'niveaux_gagnes':1}
 class Processus:
  pid=12345;returncode=None
  stdin=io.StringIO();stdout=iter([json.dumps(x)+'\n' for x in ([debut] if phase=='acquisition' else [debut,fin])])
  def poll(self):return self.returncode
  def wait(self,timeout):self.returncode=0;return 0
 p=Processus();monkeypatch.setattr(c.subprocess,'Popen',lambda *a,**kw:p)
 monkeypatch.setattr(c,'cpu_groupe',lambda *a:0)
 m=manifeste();m.update(version=3,portee='n1',graines=[0]);c.valider(m)
 b=c.executer('ar25',0,tmp_path/'jeu',m)
 cmds=[json.loads(x) for x in p.stdin.getvalue().splitlines()]
 assert b['statut']=='n1_gagne_arret_protocole'
 assert [x['op'] for x in cmds]==(['close'] if phase=='acquisition' else ['auto','close'])

def test_n1_graine_unique_et_liste_complete():
 m=manifeste();m.update(version=3,portee='n1',graines=[0],jeux=sorted(c.autorises()))
 assert len(c.valider(m)['jeux'])==20
 m['graines']=[0,1]
 with pytest.raises(ValueError,match='Graines'):c.valider(m)
