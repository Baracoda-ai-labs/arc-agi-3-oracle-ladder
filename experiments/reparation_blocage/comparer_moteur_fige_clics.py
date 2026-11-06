"""Trois premiers clics de l'inventaire, une seule exécution isolée à la fois."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;ROOT=R.parents[1];SAFE=ROOT/'experiments/GEL27_moteur_seul_v3'
OUT=R/'runs/comparaison_moteur_fige_clics1';OUT.mkdir(exist_ok=False)
records=json.loads((R/'INVENTAIRE_T4_CHAINE_NUIT.json').read_text())['records']
ids=[x['id'] for x in records if 'click' in x['tags']][:3]
assert ids==['y001','y002','y003']
results=[]
for ident in ids:
 source=R/'runs/t4_chaine_finale_1'/ident/'N1/partie';j=json.loads(source.with_suffix('.json').read_text());z=np.load(source.with_suffix('.npz'))
 n=min(8,len(j['actions'])-1);assert n>0
 assert all(row['state']=='GameState.NOT_FINISHED' and row['levels_completed']==0 for row in j['rows'][:n])
 actions=j['actions'][:n];lots=[{'actions':[{'action':'MOUSE','row':a[2],'col':a[1]}]} for a in actions]
 hist={'grilles':z['images'][:n+1].tolist(),'lots':lots,'precedents':[],'films':[z[f'film_{i+1}'].tolist() for i in range(n)]}
 inp=OUT/(ident+'_prefixe.json');inp.write_text(json.dumps(hist));dest=OUT/(ident+'_resultat.json')
 env=dict(os.environ)
 for key in list(env):
  if key.startswith('CHRYS_'):del env[key]
 env.update(PYTHONPATH=str(SAFE),PYTHONDONTWRITEBYTECODE='1',CHRYS_BUT_SUPPOSE='1',CHRYS_P1_MOTEUR_CPU='12',CHRYS_FILMS_P1='3',CHRYS_G_NOUV='1',CHRYS_F_CLE='bande3')
 cmd=[sys.executable,'-B',str(R/'comparer_moteur_fige_worker.py'),str(inp),str(dest)];t=time.monotonic()
 try:
  p=subprocess.run(cmd,env=env,cwd=SAFE,capture_output=True,text=True,timeout=15);status='termine' if p.returncode==0 else 'erreur';log=p.stdout+p.stderr
 except subprocess.TimeoutExpired as e:status='timeout_15s';log=str(e)
 (OUT/(ident+'_worker.log')).write_text(log)
 results.append({'id':ident,'prefixe':n,'statut':status,'secondes_processus':time.monotonic()-t,'prefixe_sha256':hashlib.sha256(inp.read_bytes()).hexdigest(),'source_npz_sha256':hashlib.sha256(source.with_suffix('.npz').read_bytes()).hexdigest(),'commande':cmd})
 (OUT/'bilan.json').write_text(json.dumps(results,indent=2));print(json.dumps(results[-1]),flush=True)
