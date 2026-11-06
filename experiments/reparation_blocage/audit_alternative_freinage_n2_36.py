"""Rejeu d'une alternative N1 acquise, sans induction depuis N2."""
import cloudpickle,json,hashlib,time
from pathlib import Path
import numpy as np
from chaine_coherente import Chaine
from chaine_agent_integree import lots
from transfert_roles import reaffecter
from revision_faces_contact import proposer
p=Path('runs/ka59_controleur_corrige72_1/agent.pkl');a=cloudpickle.loads(p.read_bytes());source=a.modele_gagnant
h1=np.asarray(source.grilles);ac1=a.actions[:len(source.lots)];f1=[e['images'] if e else None for e in source.films.entrees]
r=Path('runs/relais_ka59_contact1/N2/partie');z=np.load(r.with_suffix('.npz'));g=z['images'][:37];ac2=json.loads(r.with_suffix('.json').read_text())['actions'][:36];f2=[z[f'film_{i}'] for i in range(1,37)]
out={'sdk':False,'source_N1_sha':hashlib.sha256(p.read_bytes()).hexdigest(),'prefixe_N1':len(ac1),'prefixe_N2':36,'provenance':'modeles_avant_victoire_sans_induction','essais':[]};debut=time.process_time()
for nom,c in a.modeles_avant_victoire.items():
 c1,e1=c.rejouer();ent={'nom':nom,'N1':c1};out['essais'].append(ent)
 if e1 is None:continue
 t,diag=reaffecter(c,g[0],[])
 pref=Chaine(t.perception,t.programme,g[:36].tolist(),lots(ac2[:35]),[],films=f2[:35]);rev,dr=proposer(pref);ent['face35']=dr
 if rev is None:continue
 complet=Chaine(rev.perception,rev.programme,g.tolist(),lots(ac2),[],films=f2)
 ent['N2'],etat=complet.rejouer()
 _,(pc,sc)=rev.rejouer()
 from chaine_agent_integree import canon
 pc.step(sc,canon(ac2[35]))
 pred=rev.perception.rendu(sc);obs=rev.perception.vue(g[36])
 ent['pixels_ecart36']=int((pred!=obs).sum())
 ent['pieces_predites36']=[{'x':p['x'],'y':p['y'],'forme':list(p['pixels'].shape)} for p in sc.sprites if 'piece' in p.get('tags',[])]
 if etat:
  ent['admis36']=True
  Path('runs/audit_alternative_freinage_n2_36').mkdir(exist_ok=True)
  dest=Path('runs/audit_alternative_freinage_n2_36')/(nom+'.pkl');dest.write_bytes(cloudpickle.dumps(complet));ent['candidat']=str(dest)
out['cpu']=time.process_time()-debut
Path('AUDIT_ALTERNATIVE_FREINAGE_N2_36_MEMOIRE.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False))
