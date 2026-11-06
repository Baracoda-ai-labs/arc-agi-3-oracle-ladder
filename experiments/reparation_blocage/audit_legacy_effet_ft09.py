"""Préfixe sélectionné au premier changement final, effet suivant tenu à part."""
import json,os,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parent;SAFE=R.parents[1]/'experiments/GEL27_moteur_seul_v3'
if '--worker' in sys.argv:
    import numpy as np
    from representation_legacy_sans_but import construire
    from chrysalide.arc3.moteur import nom_action
    h=json.loads(Path(sys.argv[-3]).read_text());c,report=construire(h)
    Path(sys.argv[-1]).write_text(json.dumps(report,default=repr,indent=2))
    # Suffixe ouvert seulement après construction du candidat figé.
    held=json.loads(Path(sys.argv[-2]).read_text());check,state=c.rejouer();rows=[]
    if state is not None:
        pc,sc=state
        for item in held:
            pc.step(sc,nom_action(item['lot']['actions'][0]))
            pred=c.perception.rendu(sc);obs=c.perception.vue(item['image'])
            rows.append({'coup':item['coup'],'pixels_differents_vue':int(np.sum(pred!=obs)),'issue_predite':sc.issue,'issue_couverte':False})
    report['suffixe_predictions_figees']=rows
    Path(sys.argv[-1]).write_text(json.dumps(report,default=repr,indent=2));sys.exit()
import numpy as np
out=R/'runs/legacy_effet_ft09_1';out.mkdir(exist_ok=False)
p=R/'runs/arc_integre_cegar_atms_g2/ft09/N1/partie';z=np.load(p.with_suffix('.npz'));j=json.loads(p.with_suffix('.json').read_text());changes=[i+1 for i in range(len(j['actions'])) if np.any(z['images'][i]!=z['images'][i+1])];n,k=changes[:2]
assert all(r['levels_completed']==0 and r['state']=='GameState.NOT_FINISHED' for r in j['rows'][:k])
def lot(a):return {'actions':[{'action':'MOUSE','row':a[2],'col':a[1]}]}
h={'grilles':z['images'][:n+1].tolist(),'lots':[lot(a) for a in j['actions'][:n]],'films':[z[f'film_{i}'].tolist() for i in range(1,n+1)]}
(out/'prefixe.json').write_text(json.dumps(h));(out/'reserve.json').write_text(json.dumps([{'coup':i+1,'lot':lot(j['actions'][i]),'image':z['images'][i+1].tolist()} for i in range(n,k)]))
(out/'selection.json').write_text(json.dumps({'prefixe':n,'prochain_effet':k,'critere':'premiers changements finaux non nuls, sans connaissance mecanisme'}))
env={key:v for key,v in os.environ.items() if not key.startswith('CHRYS_')};env.update(PYTHONPATH=f'{SAFE}:{R}',PYTHONDONTWRITEBYTECODE='1')
try:
 q=subprocess.run([sys.executable,'-B',__file__,'--worker',str(out/'prefixe.json'),str(out/'reserve.json'),str(out/'resultat.json')],env=env,cwd=SAFE,capture_output=True,text=True,timeout=15);(out/'worker.log').write_text(q.stdout+q.stderr);print('retour',q.returncode,n,k)
except subprocess.TimeoutExpired as e:(out/'worker.log').write_text(str(e));print('timeout15s')
