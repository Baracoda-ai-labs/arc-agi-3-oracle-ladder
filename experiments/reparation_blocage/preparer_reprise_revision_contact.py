"""Rejouer des observations déjà acquises, puis sauvegarder une sonde non exécutée."""
import argparse,copy,hashlib,json
from pathlib import Path
import numpy as np
from avancer_agent_relais import charger_agent,sauver_agent
from chaine_agent_integree import canon,NOMS


def preparer(avant,observe,decisions,sortie,offre):
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (avant,observe)}
    a=charger_agent(avant);b=charger_agent(observe)
    n=len(a.actions)
    if not np.array_equal(a.images,b.images[:n+1]) or a.actions!=b.actions[:n]:
        raise ValueError('Prefixe non aligne')
    sortie.mkdir(parents=True,exist_ok=False)
    resultats=[]
    for i in range(n,len(b.actions)):
        paths=list(decisions.rglob(f'decision_{i+1:05}.json'))
        if len(paths)!=1:raise ValueError('Decision historique ambigue ou absente')
        d=json.loads(paths[0].read_text())
        if d['actions'][0]!=b.actions[i]:raise ValueError('Action historique differente')
        a._suivre_experience(d);a.attente=d
        r=a.observer(b.actions[i],b.images[i+1],b.films[i],b.issues[i],source='trace')
        resultats.append({'coup':i+1,'resultats':[{k:v for k,v in e.items() if k!='atms'} for e in r.get('resultats',[])]})
    repairs=[e for e in a.journal if e.get('type')=='revision_faces_contact' and e.get('admis')]
    if not repairs or not a.chaines:raise ValueError('Revision automatique absente')
    diag=repairs[-1];c=next(c for c in a.chaines.values() if getattr(c,'revision_locale',{}).get('operateur')=='face_contact')
    orientation=tuple(diag['orientation'])
    codes=[code for code,delta in c.perception.source.mouvements.items() if tuple(delta)==orientation and code in offre]
    if len(codes)!=1:raise ValueError('Commande vers contact non univoque')
    code=codes[0]
    if any(canon(x)==(NOMS[code],) and np.array_equal(c.perception.vue(im),c.perception.vue(a.images[-1])) for im,x in zip(a.images,a.actions)):
        raise ValueError('Experience deja observee')
    d={'statut':'experience_contact_role_inconnu','actions':[code], 'but':'inconnu',
       'origine':'orientation_face_observee','risque':'inconnu',
       'question':'La commande vers le support produit-elle le blocage predit ?',
       'alternative':'interaction inconnue, aucun second modele admis','arret_apres':1}
    a._suivre_experience(d)
    if not d.get('modeles'):raise ValueError('Prediction coherente absente')
    a.attente=d;sauver_agent(a,sortie/'agent.pkl')
    (sortie/'decision_preparee.json').write_text(json.dumps(d,indent=2))
    rapport={'sources_sha256':hashes,'observations_rejouees':resultats,'modeles':list(a.chaines),
       'but_inconnu':all(getattr(x,'but_inconnu',False) for x in a.chaines.values()),
       'precedents':len(a.precedents),'buts_refutes_conserves':list(getattr(a,'modeles_but_refute',{})),
       'prochaine_action':code,'actions_sdk':0,'installation':'observer reparation automatique, pas injection du candidat',
       'sources_inchangees':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())}
    (sortie/'rapport.json').write_text(json.dumps(rapport,indent=2))
    (sortie/'PROTOCOLE.md').write_text('Une seule sonde préparée vers le support, après révision automatique sur observations existantes.\nPrédictions dans decision_preparee.json ; utiliser ce contrôleur avec arrêt sur écart et plafond 1 action.\nAucun but de jeu ni mouvement du support ajouté. Après observation, arrêter et examiner le résultat.\n')
    return rapport

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--avant',type=Path,required=True);p.add_argument('--observe',type=Path,required=True);p.add_argument('--decisions',type=Path,required=True);p.add_argument('--sortie',type=Path,required=True);p.add_argument('--offre',type=int,nargs='+',required=True)
    z=p.parse_args();print(json.dumps(preparer(z.avant,z.observe,z.decisions,z.sortie,z.offre)))
