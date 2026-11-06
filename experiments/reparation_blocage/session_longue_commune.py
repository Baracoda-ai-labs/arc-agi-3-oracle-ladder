"""Propriétaire du pilote existant ; boîte commandes comme RelaisSDK, checkpoints sans fermeture."""
import argparse, hashlib, json, os, queue, subprocess, sys, threading, time, uuid
from pathlib import Path

CONTINUABLES={'prete_nouvelle_boucle','auto_lots_termines_session_conservee','lot_termine_session_conservee','en_cours','defaite_sdk'}


def lire(p):
    try:return json.loads(Path(p).read_text())
    except (FileNotFoundError,json.JSONDecodeError):return {}


def sauver(p,d):
    p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2));tmp.replace(p)


class Proprietaire:
    def __init__(self, root, child, clock=time.monotonic):
        self.root=Path(root);self.child=child;self.clock=clock
        self.debut=clock();self.deadline=None;self.active0=None;self.actif=0.
        self.attente=True;self.dernier={};self.statut='initialisation';self.fermeture=False
        self.commandes=0;self.checkpoints=0

    def etat(self):
        return {'pid_owner':os.getpid(),'pid_session':self.child.pid,'statut':self.statut,
                'session_ouverte':self.child.poll() is None,'commande_en_cours':self.attente,
                'secondes_depuis_lancement':self.clock()-self.debut,
                'secondes_actives':self.actif+(self.clock()-self.active0 if self.active0 is not None else 0),
                'checkpoints':self.checkpoints,'commandes_auto':self.commandes,
                'memoire':'meme_agent_et_meme_SDK_en_RAM_pas_de_reconstruction',
                'session':self.dernier,'cpu_source':'session.cpu_total_recolte_s cumulatif ; enfants actifs non inclus'}

    def pause(self, raison):
        if self.active0 is not None:self.actif+=self.clock()-self.active0
        self.active0=None;self.deadline=None;self.statut=raison;self.checkpoints+=1
        with (self.root/'checkpoints.jsonl').open('a') as f:f.write(json.dumps(self.etat())+'\n')

    def commander(self, cmd):
        op=cmd.get('op')
        if op=='continue':
            duree=cmd.get('secondes',1200)
            if isinstance(duree,bool) or not isinstance(duree,(float,int)) or not 0<duree<=86400:raise ValueError('Duree positive <=86400 requise')
            if self.child.poll() is not None:raise ValueError('Proprietaire SDK perdu : reacces compte requis')
            if self.deadline is not None:raise ValueError('Une periode est deja active')
            if self.attente:raise ValueError('Attendre la fin de la commande en cours')
            if self.dernier.get('niveaux_gagnes',0)>=1 or self.dernier.get('jeu_gagne'):raise ValueError('Portee N1 terminee ; aucun next_level implicite')
            if self.dernier.get('statut') not in CONTINUABLES:raise ValueError('Diagnostic requis avant continuation')
            if self.checkpoints and not cmd.get('preuve_progression'):raise ValueError('Reprise exige reference de preuve ou justification diagnostic explicite')
            self.active0=self.clock();self.deadline=self.active0+duree;self.statut='actif'
        elif op=='pause':self.pause('pause_demandee_apres_commande')
        elif op=='close':
            if self.attente:raise ValueError('Attendre commande avant fermeture explicite')
            self.child.stdin.write('{"op":"close"}\n');self.child.stdin.flush();self.fermeture=True
        elif op!='status':raise ValueError('Commande inconnue')
        return self.etat()

    def recevoir(self, message):
        self.dernier=message;self.attente=False
        if self.active0 is None:self.statut='checkpoint_session_conservee'
        if message.get('jeu_gagne') or message.get('niveaux_gagnes',0)>=1:self.pause('n1_gagne_session_conservee')
        elif message.get('statut') not in CONTINUABLES:self.pause('diagnostic_session_conservee')

    def tick(self):
        if self.child.poll() is not None:
            self.pause('session_terminee');return
        if self.deadline is None or self.attente:return
        if self.clock()>=self.deadline:
            self.pause('checkpoint_session_conservee');return
        self.child.stdin.write('{"op":"auto","lots":1,"coups":1,"reprises":true}\n')
        self.child.stdin.flush();self.attente=True;self.commandes+=1


def owner(root):
    root=Path(root);config=lire(root/'lancement.json');env=dict(os.environ)
    env.update(PYTHONPATH='.:livraison_p1/code:..',PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1')
    for k in list(env):
        if k.startswith('CHRYS_') or k=='GEL27_TEMOINS':env.pop(k)
    q=queue.Queue()
    with (root/'stderr.log').open('w') as err,(root/'stdout.log').open('w') as log:
        child=subprocess.Popen(config['argv'],cwd=config['cwd'],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True)
        p=Proprietaire(root,child)
        def reader():
            for line in child.stdout:
                log.write(line);log.flush()
                try:q.put(json.loads(line))
                except json.JSONDecodeError:pass
        threading.Thread(target=reader,daemon=True).start()
        while child.poll() is None:
            while not q.empty():
                msg=q.get()
                if isinstance(msg,dict) and 'statut' in msg:p.recevoir(msg)
            for path in sorted(root.glob('commande_*.json')):
                result=path.with_suffix('.resultat.json')
                if path.name.endswith('.resultat.json') or result.exists():continue
                cmd=lire(path)
                try:r=p.commander(cmd)
                except Exception as e:r={**p.etat(),'erreur':repr(e)}
                sauver(result,r)
                with (root/'commandes.jsonl').open('a') as f:f.write(json.dumps({'commande':cmd,'resultat':r})+'\n')
            if not p.fermeture:p.tick()
            sauver(root/'owner.json',p.etat());time.sleep(.05)
        p.pause('session_terminee');sauver(root/'owner.json',p.etat())


def start(root,runtime,jeu,mode):
    # Réutiliser validation/commande du runner sans importer le moteur ou ouvrir les jeux.
    import importlib.util
    runtime=Path(runtime).resolve();root=Path(root).resolve()
    spec=importlib.util.spec_from_file_location('campagne_owner',runtime/'campagne_moteur_commun.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if jeu not in module.autorises() or jeu in module.INTERDITS:raise ValueError('Jeu non autorise')
    root.mkdir(parents=True,exist_ok=False)
    cmd=module.commande(jeu,0,root/'session',{'composition_contextuelle_auto':True,'recherche_prolongee':False,'recherche_workers':1})
    fichiers={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime.glob('*.py')}
    sauver(root/'lancement.json',{'argv':cmd,'cwd':str(runtime/'paquet'),'mode':mode,'graine':0,'sources_entree':fichiers,
           'portee':'N1','depart':'neuf_sans_memoire_importee','reprise':'continue conserve acquis memejeu en RAM',
           'limite':'aucune attache a un SDK deja possede par un autre processus ; pas de restauration pickle'})
    with (root/'owner.log').open('w') as log:
        proc=subprocess.Popen([sys.executable,'-u','-B',str(Path(__file__).resolve()),'owner','--root',str(root)],stdout=log,stderr=log,start_new_session=True,stdin=subprocess.DEVNULL)
    sauver(root/'pid.json',{'pid':proc.pid});return {'pid_owner':proc.pid,'root':str(root),'statut':'demarre_en_attente'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('op',choices=['start','owner','status','continue','pause','close'])
    ap.add_argument('--root',type=Path,required=True);ap.add_argument('--runtime',type=Path);ap.add_argument('--jeu')
    ap.add_argument('--mode',choices=['budget_comparatif','developpement'],default='developpement')
    ap.add_argument('--secondes',type=float,default=1200);ap.add_argument('--preuve-progression');a=ap.parse_args()
    if a.op=='owner':owner(a.root);return
    if a.op=='start':
        if not a.runtime or not a.jeu:ap.error('start exige --runtime et --jeu')
        print(json.dumps(start(a.root,a.runtime,a.jeu,a.mode)));return
    if not (a.root/'pid.json').exists():ap.error('Proprietaire absent')
    if a.op=='status':print(json.dumps(lire(a.root/'owner.json')));return
    path=a.root/f'commande_{time.time_ns()}_{uuid.uuid4().hex[:6]}.json'
    sauver(path,{'op':a.op,'secondes':a.secondes,'preuve_progression':a.preuve_progression})
    print(json.dumps({'commande':str(path),'reponse':str(path.with_suffix('.resultat.json'))}))

if __name__=='__main__':main()
