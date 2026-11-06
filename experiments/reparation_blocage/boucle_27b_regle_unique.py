"""Observation à la demande puis patch natif borné ; aucune règle de jeu encodée ici."""
import argparse
import ast
import copy
import hashlib
import json
import signal
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI/'paquet'), str(ICI)]

from chaine_coherente import Chaine
from objets_variables import ObjetsVariables
from propositions_python import Proposition
from reprise_flux_27b import appeler_flux

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.moteur import CODES, NOMS
from chrysalide.langue import lire_reponse, vers_python
from chrysalide.qwen.images import PAL

SCHEMA = {'type':'object', 'required':['outils','patch_python','hypothese'], 'properties':{
    'outils':{'type':'array','maxItems':2,'items':{'type':'object','required':['nom','arguments'],
        'properties':{'nom':{'type':'string'},'arguments':{'type':'object'}}}},
    'patch_python':{'type':'string'},'hypothese':{'type':'string'}}, 'additionalProperties':False}
CONTRAT = '''Tu découvres un jeu inconnu. Le modèle actuel échoue au rejeu. Observe avant de corriger.
Réponds en JSON complet: {"outils":[{"nom":"...","arguments":{...}}],"patch_python":"","hypothese":"..."}.
Choisis 1 ou 2 outils, OU propose un patch, jamais les deux. Au moins un outil doit avoir été exécuté avant un patch.
Outils disponibles (indices coup=1..8, image=0..8, coordonnées pixels 0..63):
- regle {"nom":"nom exact"}: code Python d'une règle existante.
- differences {"coup":1}: pixels changés observés et erreurs de prédiction, sans diagnostic.
- film {"coup":1}: image avant puis TOUTES les images renvoyées par cette action, ×10 sans lissage.
- objets {"image":0}: objets de la segmentation actuelle (hypothèses de perception, pas vérité).
- calcul {"expression":"expression Python pure"}: calcul sur grilles (liste d'images aplaties de 4096 entiers) et actions (codes 1=UP,2=DOWN,3=LEFT,4=RIGHT).
Expressions: sum,len,min,max,range,abs,int,compréhensions,indexation; pas def,import,attribut ni exec.
Budget total: 4 appels, 2 propositions de patch maximum. Réponse ≤1200 jetons; privilégie une petite modification.
Patch: REPONSE = Reponse(patch=Patch(retire=["nom"], ajoute=[Regle("nom", quand=..., alors=[...], phase=...)]))
Remplace exactement UNE règle de même nom. Autres règles et état global inchangés. Une recopie identique sera refusée.
Syntaxe native: action(), objets({"tag":"..."}), x(o),y(o),largeur(o),hauteur(o),pixel(o,dx,dy),libre(o,dx,dy,filtre),
chevauche(o,p), etat("nom"), comparaisons et and/or/not; effets: deplacer(o,dx,dy),placer(o,x,y),
pour(o,objets(...),[effets]),si_alors(condition,[effets],[sinon]),poser("nom",valeur),niveau_suivant().
libre teste l'absence de chevauchement des pixels opaques après déplacement avec les objets du filtre.
Le patch entier est vérifié sur toutes les observations, sans accepter de victoire prédite absente.
Ne donne pas une vérité présumée; une hypothèse doit expliquer les pixels. Tu peux t'abstenir (outils=[],patch_python="").
'''


def sauver(p, x):
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2))


def normaliser_reponse(texte):
    """Accepte l'expression Reponse seule ; aucune modification de ses arguments."""
    arbre=ast.parse(texte)
    if (len(arbre.body)==1 and isinstance(arbre.body[0],ast.Expr)
            and isinstance(arbre.body[0].value,ast.Call)
            and isinstance(arbre.body[0].value.func,ast.Name)
            and arbre.body[0].value.func.id=='Reponse'):
        return 'REPONSE = '+texte, True
    return texte, False


def patch_unique(c, texte):
    """Contrôle de portée avant le vérificateur existant, aucune correction du code."""
    lu = lire_reponse(texte, mots=c.programme.get('mots',{}))
    p = lu.get('patch',{})
    if set(p)-{'retire','ajoute'} or len(p.get('retire',[])) != 1 or len(p.get('ajoute',[])) != 1:
        raise ValueError('Un remplacement de règle exactement, sans autre champ')
    nom = p['retire'][0]
    anciennes = [r for r in c.programme['regles'] if r['nom']==nom]
    if len(anciennes)!=1 or p['ajoute'][0].get('nom')!=nom:
        raise ValueError('Le nom de la règle doit être conservé et connu')
    if anciennes[0] == p['ajoute'][0]:
        raise ValueError('Programme inchangé : règle identique après parsing')
    return c.patch(texte)


class Observation:
    def __init__(self, images, films, actions, chaine, out):
        self.images, self.films, self.actions = np.asarray(images), films, actions
        self.c, self.out = chaine, out

    def image(self,g,nom):
        p=self.out/f'{nom}.png'
        Image.fromarray(PAL[np.asarray(g)]).resize((640,640),Image.Resampling.NEAREST).save(p)
        return p

    def outil(self,nom,a):
        if nom=='regle':
            rs=[r for r in self.c.programme['regles'] if r['nom']==a['nom']]
            if len(rs)!=1: raise ValueError('Règle inconnue')
            return {'python':vers_python({'mode':'lois','etat':self.c.programme.get('etat',{}),'regles':rs})}, []
        if nom in ('film','differences'):
            k=a['coup']
            if type(k) is not int or not 1<=k<len(self.images): raise ValueError('Coup hors archive')
            if nom=='film':
                fs=self.films[f'film_{k}']
                paths=[self.image(self.images[k-1],f'avant_{k}')]
                paths += [self.image(g,f'film_{k}_{i}') for i,g in enumerate(fs)]
                return {'action':self.actions[k-1], 'images':['avant']+[f'frame_{i}' for i in range(len(fs))],
                        'nombre_frames':len(fs),'toutes_frames':True},paths
            def diff(a,b):
                yy,xx=np.nonzero(a!=b)
                return {'total':len(xx),'tronque':len(xx)>128,'pixels_y_x_avant_apres':
                        [[int(y),int(x),int(a[y,x]),int(b[y,x])] for y,x in list(zip(yy,xx))[:128]]}
            scene=self.c.perception.scene(self.images[0]); pc=Programme(self.c.programme)
            for action in self.actions[:k]: pc.step(scene,(action,))
            pred=self.c.perception.rendu(scene)
            return {'action':self.actions[k-1], 'changement_observe':diff(self.images[k-1],self.images[k]),
                    'prediction_depuis_initial':diff(pred,self.c.perception.vue(self.images[k]))},[]
        if nom=='objets':
            i=a['image']
            if type(i) is not int or not 0<=i<len(self.images): raise ValueError('Image hors archive')
            scene=self.c.perception.scene(self.images[i]); result=[]
            for s in scene.sprites:
                px=np.asarray(s['pixels'])
                result.append({'tags':s['tags'],'x':s['x'],'y':s['y'],'forme':list(px.shape),
                    'couleurs':np.unique(px).tolist(),'pixels':px.tolist() if px.size<=100 else None})
            return {'objets_hypotheses':result,'grandes_formes_sans_pixels':True},[]
        if nom=='calcul':
            code='PROGRAMME = Programme(regles=[], fonctions='+repr({'analyse':{
                'params':['grilles','actions'],'expr':a['expression']}})+')'
            result=Proposition(code).appeler('analyse',[g.ravel().tolist() for g in self.images],[CODES[a] for a in self.actions])
            return {'resultat':result},[]
        raise ValueError('Outil inconnu')


def jeu_reel(c, images, actions, out):
    # Import tardif : aucun SDK avant validation du modèle complet.
    from boucle_objets_variables import LaboP1

    from chrysalide.arc3.moteur import CODES
    lab=LaboP1('ka59',1,'/Users/ts/models/chrysalide3/experiments/G/publics20c',out/'N1/partie')
    b={'initialisations_sdk':1,'statut':'en_cours','appels_step_tentes':0}
    journal=[]
    try:
        if not np.array_equal(lab.image,images[0]):
            b['statut']='initial_different';return b
        for k,a in enumerate(actions):
            code=CODES[a]
            offre=[int(getattr(x,'value',x)) for x in lab.actions_disponibles]
            if code not in offre: b['statut']='action_indisponible';return b
            b['appels_step_tentes']+=1
            g,_=lab.play(code,purpose='restauration_comptee')
            if lab.finished or not np.array_equal(g,images[k+1]):
                b['statut']='restauration_divergente';return b
        plan=c.proposer(secondes=3);sauver(out/'plan.json',plan)
        if plan['statut']!='plan_simule_valide': b['statut']='aucun_plan';return b
        for rang,a in enumerate(plan['plan']['actions'][:12]):
            if rang and c.adopter_plan(plan['plan']['actions'][rang:])['statut']!='plan_simule_valide':
                b['statut']='suffixe_refuse';return b
            code=CODES[a[0]]
            offre=[int(getattr(x,'value',x)) for x in lab.actions_disponibles]
            if code not in offre: b['statut']='action_indisponible';return b
            b['appels_step_tentes']+=1
            image,film=lab.play(code,purpose='plan_patch_27b')
            if lab.finished:
                b['statut']='victoire_niveau_reelle' if lab.won else 'defaite_reelle';return b
            r=c.observer(tuple(a),image,source='jeu',film=film);journal.append(r)
            if r['statut']!='transition_confirmee': b['statut']='divergence_future';return b
        b['statut']='plan_ou_budget_sans_victoire'
    finally:
        b.update(coups_reels=len(lab.rows),niveaux_gagnes=int(lab.won),jeu_gagne=lab.partie_gagnee)
        sauver(out/'sdk.json',b);sauver(out/'journal_sdk.json',journal)
    return b


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sortie',type=Path,required=True)
    ap.add_argument('--modele',choices=['qwen3.8:27b-mlx','qwen3:4b-instruct-2507-q4_K_M','gemma3:4b'],default='qwen3.8:27b-mlx')
    ap.add_argument('--reprendre-interruption',action='store_true');args=ap.parse_args()
    out=args.sortie
    texte_images=args.modele=='qwen3:4b-instruct-2507-q4_K_M'
    if args.reprendre_interruption and args.modele!='qwen3.8:27b-mlx': raise ValueError('Reprise réservée à l’essai 27B documenté')
    if args.reprendre_interruption:
        if (out/'sdk.json').exists() or (out/'metriques_5.json').exists():
            raise ValueError('Reprise unique avant tout SDK uniquement')
        for nom in ('journal.json','bilan.json','sources.json'):
            cible=out/(nom+'.avant_interruption')
            with cible.open('x') as f: f.write((out/nom).read_text())
    else:
        out.mkdir(parents=True,exist_ok=False)
    r=ICI/'runs/guidage_ka59_fige1/N1'
    with np.load(r/'partie.npz') as z:
        images=z['images'].copy();films={k:z[k].copy() for k in z.files if k.startswith('film_')}
    codes=[row['action'] for row in json.loads((r/'partie.json').read_text())['rows']]
    actions=[NOMS[a] for a in codes]
    v=ObjetsVariables(images,codes);p=v.programme(v.buts[0])
    c=Chaine(v,p,images.tolist(),[{'actions':[{'action':a}]} for a in actions],
             [(NOMS[k],) for k in range(1,5)],coups_deja_joues=8,reserve=20)
    sauver(out/'reference.json',c.rejouer()[0]);(out/'programme_initial.py').write_text(vers_python(p))
    sauver(out/'sources.json',{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in
        [Path(__file__),ICI/'reprise_flux_27b.py',ICI/'objets_variables.py',ICI/'chaine_coherente.py',r/'partie.npz']})
    ob=Observation(images,films,actions,c,out)
    fichiers=[ob.image(images[0],'initial'),ob.image(images[1],'apres_coup_1')]
    base=CONTRAT+'\nARCHIVE\n'+json.dumps({'actions':actions,'regles':[r['nom'] for r in p['regles']],
        'premiere_divergence':1,'images_initiales':['avant coup 1','après coup 1'],
        'films_n_frames':{k:len(f) for k,f in films.items()}},ensure_ascii=False)
    historique=[];journal=[];cout=0.;n_outils=0;n_patch=0
    bilan={'statut':'budget','coups_reels':0,'initialisations_sdk':0,'niveaux_gagnes':0}
    try:
        for i in range(1,5):
            reste=int(600-cout)
            if reste<=0: break
            prompt=base+'\nECHANGES ET RETOURS EXACTS\n'+json.dumps(historique,ensure_ascii=False)
            prompt+=f'\nAppel {i}/4, outils exécutés {n_outils}, propositions patch {n_patch}/2. Images jointes : '+json.dumps([f.name for f in fichiers])
            if args.reprendre_interruption and i<=3:
                raw=(out/f'reponse_{i}.json').read_text();met=json.loads((out/f'metriques_{i}.json').read_text())
            elif args.reprendre_interruption:
                # Reprise strictement identique du seul appel interrompu par le contrôleur.
                cout+=json.loads((out/'metriques_4.json').read_text())['mur_s']
                prompt=(out/'prompt_4.txt').read_text()
                fichiers=[Path(p) for p in json.loads((out/'images_4.json').read_text())]
                raw,met=appeler_flux(prompt,fichiers,out,5,SCHEMA,delai=min(180,int(600-cout)))
            else:
                raw,met=appeler_flux(prompt,fichiers,out,i,SCHEMA,delai=min(180,reste),
                                    modele=args.modele,texte_images=texte_images)
            cout+=met['mur_s']
            fichiers=[]
            ligne={'appel':i};journal.append(ligne)
            historique.append({'reponse_modele_brute':raw})
            def expire(_sig,_frame): raise TimeoutError('Opération contrôleur >10 s')
            signal.signal(signal.SIGALRM,expire);signal.alarm(10)
            try:
                rep=json.loads(raw)
                demandes,patch=rep['outils'],rep['patch_python']
                if not isinstance(demandes,list) or len(demandes)>2 or not isinstance(patch,str):
                    raise ValueError('Format outils/patch invalide')
                if demandes and patch: raise ValueError('Outils OU patch, pas les deux')
                if demandes:
                    retours=[]
                    for d in demandes:
                        resultat,fs=ob.outil(d['nom'],d['arguments']);n_outils+=1;fichiers+=fs
                        texte=json.dumps(resultat,ensure_ascii=False)
                        retours.append({'outil':d,'resultat':resultat if len(texte)<=12000 else
                            {'tronque':True,'debut':texte[:12000]}})
                    ligne['retours']=retours
                elif patch:
                    if not n_outils: raise ValueError('Observer via un outil avant le patch')
                    if n_patch>=2: break
                    n_patch+=1
                    patch,ligne['normalisation_syntaxique']=normaliser_reponse(patch)
                    ligne['controle_patch']=patch_unique(c,patch)
                    if ligne['controle_patch']['statut']=='patch_valide_sur_observations':
                        (out/'programme_corrige.py').write_text(vers_python(c.programme))
                        bilan['statut']='patch_valide_sur_traces'
                        signal.alarm(0)
                        bilan['sdk']=jeu_reel(c,images,actions,out)
                        for k in ('coups_reels','initialisations_sdk','niveaux_gagnes'): bilan[k]=bilan['sdk'][k]
                        break
                    if n_patch>=2: bilan['statut']='deux_patchs_refuses';break
                else: bilan['statut']='abstention';break
            except Exception as e:  # noqa: BLE001 — refus exact, pas de réécriture
                ligne['erreur']=repr(e)
            finally:
                signal.alarm(0)
                historique.append({'retour_controleur':copy.deepcopy(ligne)})
                sauver(out/'journal.json',journal)
    finally:
        metriques=[json.loads(p.read_text()) for p in out.glob('metriques_*.json')]
        bilan.update(modele=args.modele,appels_ia=len(metriques),outils_executes=n_outils,patchs_proposes=n_patch,
                     temps_ia_s=sum(m['mur_s'] for m in metriques))
        sauver(out/'bilan.json',bilan);print(json.dumps(bilan),flush=True)


if __name__=='__main__': main()
