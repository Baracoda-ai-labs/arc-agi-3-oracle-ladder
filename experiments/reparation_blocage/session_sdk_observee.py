"""Propriétaire SDK indépendant du contrôleur ; reprise du relais fichiers existant."""
import argparse,hashlib,json,time,os
from pathlib import Path
import numpy as np


def empreinte_image(image):
    return hashlib.sha256(np.asarray(image,dtype=np.int16).tobytes()).hexdigest()


class RelaisSDK:
    def __init__(self, lab, root, acces=0, jeu=None, cpu_acces=0):
        self.lab,self.root,self.acces=lab,Path(root),acces
        self.jeu,self.cpu_acces=jeu,cpu_acces
        self.stop=False;self.t0=time.process_time();self.initial=acces+len(lab.rows)
        self.journal=[];self.tentes=self.initial

    def etat(self):
        return dict(jeu=self.jeu,cpu_acces=self.cpu_acces,pid=os.getpid(),session_ouverte=not self.stop,niveau=self.lab.level,
            coups_reels=self.acces+len(self.lab.rows),coups_reacces=self.initial,
            coups_nouveaux=self.acces+len(self.lab.rows)-self.initial,initialisations=1,
            appels_tentes=self.tentes,image_sha256=empreinte_image(self.lab.image),
            niveau_gagne=self.lab.won,jeu_gagne=self.lab.partie_gagnee,termine=self.lab.finished,
            actions_disponibles=self.lab.actions_disponibles,cpu_relais=time.process_time()-self.t0,
            trace=str(self.lab.output.resolve()))

    def traiter(self, cmd):
        if cmd['op']=='play':
            if self.lab.finished:raise ValueError('Niveau terminé')
            if (cmd['image_sha256']!=empreinte_image(self.lab.image) or
                    cmd['coup_total_avant']!=self.acces+len(self.lab.rows)):
                raise ValueError('Observation périmée')
            action=cmd['action'];code=6 if isinstance(action,list) else action
            if code not in self.lab.actions_disponibles or code==0:raise ValueError('Action indisponible')
            self.tentes+=1
            self.lab.play(action,purpose=cmd.get('purpose','controleur_generique'))
        elif cmd['op']=='next_level':
            if not self.lab.won or self.lab.partie_gagnee:raise ValueError('Transition impossible')
            ancien=self.lab
            suivant=ancien.next_level(self.root/f'N{ancien.level+1}/partie')
            assert suivant.env is ancien.env
            self.acces+=len(ancien.rows);self.lab=suivant
        elif cmd['op']=='close':self.stop=True
        elif cmd['op']!='status':raise ValueError('Commande inconnue')
        return self.etat()

    def boucle(self):
        self.root.mkdir(parents=True,exist_ok=True)
        while not self.stop:
            for p in sorted(self.root.glob('commande_*.json')):
                sortie=p.with_suffix('.resultat.json')
                if p.name.endswith('.resultat.json') or sortie.exists():continue
                cmd=json.loads(p.read_text())
                try:r=self.traiter(cmd)
                except Exception as e:r={**self.etat(),'erreur':repr(e)}
                self.journal.append({'commande':cmd,'resultat':r})
                sortie.write_text(json.dumps(r,indent=2))
                (self.root/'journal_sdk.json').write_text(json.dumps(self.journal,indent=2))
            tmp=self.root/'etat.tmp';tmp.write_text(json.dumps(self.etat(),indent=2));tmp.replace(self.root/'etat.json')
            time.sleep(.1)


def reprendre(source,root):
    from boucle_agent_integree import AUTORISES
    from boucle_objets_variables import LaboP1
    t0=time.process_time()
    meta=json.loads((source/'etat.json').read_text())
    jeu=meta['jeu']
    if jeu not in AUTORISES:raise ValueError('Jeu non autorisé')
    root.mkdir(parents=True,exist_ok=False)
    lab=LaboP1(jeu,1,'/Users/ts/models/chrysalide3/experiments/G/publics20c',root/'N1/partie')
    acces=0
    for niveau in range(1,meta['niveau']+1):
        if niveau>1:
            acces+=len(lab.rows);lab=lab.next_level(root/f'N{niveau}/partie')
        z=np.load(source/f'N{niveau}/partie.npz')
        rows=json.loads((source/f'N{niveau}/partie.json').read_text())['rows']
        if not np.array_equal(lab.image,z['images'][0]):raise ValueError('Entrée niveau divergente')
        for i,row in enumerate(rows):
            if lab.finished:raise ValueError('Fin pendant accès')
            image,film=lab.play(row['action'],purpose='reacces_compte_relais_sdk')
            if not np.array_equal(image,z['images'][i+1]) or not np.array_equal(film,z[f'film_{i+1}']):
                raise ValueError('Accès divergent')
    relais=RelaisSDK(lab,root,acces,jeu,time.process_time()-t0)
    (root/'provenance.json').write_text(json.dumps({'jeu':jeu,'source':str(source.resolve()),
        'sha256_relais':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'acces':relais.initial},indent=2))
    return relais


def demander(root,commande,timeout=60):
    import uuid
    root=Path(root);p=root/f'commande_{time.time_ns()}_{uuid.uuid4().hex}.json'
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(commande));tmp.replace(p)
    resultat=p.with_suffix('.resultat.json');fin=time.monotonic()+timeout
    while True:
        try:
            r=json.loads(resultat.read_text())
            break
        except (FileNotFoundError, json.JSONDecodeError):
            if time.monotonic()>fin:
                raise TimeoutError('Commande conservee, ne pas la renvoyer sans lire resultat')
            time.sleep(.05)
    if 'erreur' in r:raise ValueError(r['erreur'])
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True)
    a=p.parse_args();reprendre(a.source,a.sortie).boucle()
