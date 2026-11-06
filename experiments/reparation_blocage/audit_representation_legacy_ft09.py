"""Une comparaison sur préfixe déjà payé, sans but ni SDK."""
import copy,json,os,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parent;SAFE=R.parents[1]/'experiments/GEL27_moteur_seul_v3'
if '--worker' in sys.argv:
    from chrysalide.arc3.moteur import MoteurC
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.logique.theorie import rejeu
    from chaine_coherente import Chaine
    from objets_variables import ObjetsVariables
    h=json.loads(Path(sys.argv[-2]).read_text());out={'portee':'prefixe8 uniquement, aucune issue couverte','plans_non_utilises':True}
    try: ObjetsVariables(h['grilles'],h['actions_sdk']);out['objets_variables']='construit'
    except Exception as e:out['objets_variables']=repr(e)
    m=MoteurC(budget=10);m.proposer({k:v for k,v in h.items() if k!='actions_sdk'})
    out['infos_moteur']=m.infos;th=getattr(m,'th_releve',None);out['theorie_presente']=th is not None
    if th is not None:
        th=copy.deepcopy(th);th.but=None
        out['rejeu_C']=rejeu(th,m.tr)[:2];out['mouvements']=len(th.moves);out['bascules']=repr(th.bascule);out['motif']=repr(th.motif)
        prog,non=exporter(th,m.tr.taille);out['non_exporte']=non
        m._couches=th.couches()
        c=Chaine(m,prog,h['grilles'],h['lots'],[],coups_deja_joues=8,films=h['films'])
        check,state=c.rejouer();out['controle_chaine']=check;out['etat_rejoue']=state is not None
        out['perception']=c.description_perception()
        Path(sys.argv[-1]).with_name('programme_sans_but.json').write_text(json.dumps(prog,default=repr,indent=2))
    Path(sys.argv[-1]).write_text(json.dumps(out,default=repr,indent=2));sys.exit()
import numpy as np
out=R/'runs/representation_legacy_ft09_1';out.mkdir(exist_ok=False)
p=R/'runs/arc_integre_cegar_atms_g2/ft09/N1/partie';z=np.load(p.with_suffix('.npz'));j=json.loads(p.with_suffix('.json').read_text());a=j['actions'][:8]
assert all(r['levels_completed']==0 and r['state']=='GameState.NOT_FINISHED' for r in j['rows'][:8])
h={'grilles':z['images'][:9].tolist(),'lots':[{'actions':[{'action':'MOUSE','row':x[2],'col':x[1]}]} for x in a],'films':[z[f'film_{i}'].tolist() for i in range(1,9)],'precedents':[],'actions_sdk':a}
(out/'prefixe.json').write_text(json.dumps(h));env={k:v for k,v in os.environ.items() if not k.startswith('CHRYS_')};env.update(PYTHONPATH=f'{SAFE}:{R}',PYTHONDONTWRITEBYTECODE='1',CHRYS_BUT_SUPPOSE='1')
try:
 p=subprocess.run([sys.executable,'-B',__file__,'--worker',str(out/'prefixe.json'),str(out/'resultat.json')],env=env,cwd=SAFE,capture_output=True,text=True,timeout=15)
 (out/'worker.log').write_text(p.stdout+p.stderr);print('code',p.returncode)
except subprocess.TimeoutExpired as e:(out/'worker.log').write_text(str(e));print('timeout')
