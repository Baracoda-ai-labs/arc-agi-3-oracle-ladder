"""Rejeu causal d'une observation puis recherche d'un objectif expérimental distinct."""
import argparse,copy,hashlib,json,time
from pathlib import Path
import cloudpickle,numpy as np
from avancer_agent_relais import sauver_agent
from revision_but_roles import couverture
from chrysalide.arc3.logique.plan_langage import planifier_langage,cle_complete,_GELES
from chrysalide.arc3.langage import Programme


def preparer(avant,observe,decision,sortie,secondes=30):
    raw=avant.read_bytes();a=cloudpickle.loads(raw);b=cloudpickle.loads(observe.read_bytes());n=len(a.actions)
    assert len(b.actions)==n+1 and np.array_equal(a.images,b.images[:-1]) and a.actions==b.actions[:-1]
    d=json.loads(decision.read_text());assert d['actions'][0]==b.actions[-1]
    a._suivre_experience(d);a.attente=d
    observation=a.observer(b.actions[-1],b.images[-1],b.films[-1],b.issues[-1],source='trace')
    candidats=[(nom,c) for nom,c in a.chaines.items() if getattr(c,'revision_locale',{}).get('operateur')=='classe_glissable']
    assert candidats,'Reparation automatique absente'
    nom,c=candidats[0];assert c.but_inconnu
    sortie.mkdir(parents=True,exist_ok=True);sauver_agent(a,sortie/'agent.pkl')
    classe=c.preuve_classe_glissable['classe'];hyp=couverture(c.perception)
    groupes=[h for h in hyp if h['classe_cible_candidate']!=classe and any(k['classe_cible_candidate']==classe and k['forme']==h['forme'] for k in hyp)]
    assert len(groupes)==1,'Correspondance experimentale ambigue'
    groupe=groupes[0]
    conditions=[]
    for x,y,w,h in groupe['centres']:
        conditions.append(['existe','$o',['objets',{'couleur':classe}],['et',['=',['x','$o'],x],['=',['y','$o'],y],['=',['largeur','$o'],w],['=',['hauteur','$o'],h]]])
    programme=copy.deepcopy(c.programme)
    programme['regles'].append({'nom':'objectif_correspondance_experimental','phase':99,'quand':['et',*conditions],'alors':[['niveau_suivant']]})
    _,(pc,sc)=c.rejouer();depart=copy.deepcopy(sc);etat=copy.deepcopy(pc.etat);t=time.process_time()
    plan,infos=planifier_langage(programme,depart,[(x,) for x in ['UP','DOWN','LEFT','RIGHT']],noeuds=100000,secondes=secondes,compiler=False,etat=etat)
    etapes=[]
    if plan:
        pi=Programme(c.programme);pi.etat=copy.deepcopy(pc.etat);si=copy.deepcopy(sc)
        for act in plan:
            pc.step(sc,act);pi.step(si,act);_GELES.clear();assert cle_complete(sc,pc.etat)==cle_complete(si,pi.etat)
            assert sc.issue is None
            etapes.append({'action':act,'image':c.perception.rendu(sc).tolist(),'issue':None})
    rapport={'source27_sha256':hashlib.sha256(raw).hexdigest(),'source_observee':str(observe),
        'observation_rejouee':[{k:v for k,v in e.items() if k!='atms'} for e in observation['resultats']],
        'reparation_automatique':True,'modeles':list(a.chaines),'precedents':len(a.precedents),
        'buts_refutes_conserves':list(getattr(a,'modeles_but_refute',{})),
        'but_jeu_inconnu':True,'objectif_experimental':groupe,'plan_experience':plan,
        'etapes':etapes,'infos':infos,'cpu_recherche':time.process_time()-t,'sdk':0,
        'limite':'Objectif de correspondance non confirme par victoire ; sol cache sous autre support non observe.'}
    (sortie/'rapport.json').write_text(json.dumps(rapport,indent=2));return rapport

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('avant','observe','decision','sortie'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--secondes',type=float,default=30);z=p.parse_args()
    r=preparer(z.avant,z.observe,z.decision,z.sortie,z.secondes);print(json.dumps({k:v for k,v in r.items() if k not in ('etapes','objectif_experimental')}))
