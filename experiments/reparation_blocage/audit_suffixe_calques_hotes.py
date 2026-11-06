"""Décisions gelées après six coups ; observations archive seulement si même action."""
from pathlib import Path
exec(compile((Path(__file__).parent/'audit_integration_calques_hotes.py').read_text().split("rap={'sdk'")[0], __file__, 'exec'))
resultats=[]
rep=R/'runs/audit_suffixe_calques_hotes'
rep.mkdir(exist_ok=True)
for numero in range(20):
    i=len(a.actions)
    avant=cloudpickle.dumps(a)
    t=time.monotonic();d=a.decider([1,2,3,4,5],secondes=10)
    item={'coup':i+1,'secondes':time.monotonic()-t,'actions':d.get('actions'),
          'origine':d.get('origine'),'statut':d.get('statut'),'action_archive':rows[i]['action'],
          'modeles':list(a.chaines)}
    identique=bool(d.get('actions')) and d['actions'][0]==rows[i]['action']
    item['identique_archive']=identique
    resultats.append(item)
    print(json.dumps(item),flush=True)
    if not identique:
        (rep/'agent_avant_decision.pkl').write_bytes(avant)
        (rep/'agent_apres_decision.pkl').write_bytes(cloudpickle.dumps(a))
        (rep/'decision.json').write_text(json.dumps(d,default=str,indent=2)+'\n')
        np.savez_compressed(rep/'image_avant_decision.npz',image=a.images[-1])
        break
    # La décision porte sa propre attente et sa suite de plan éventuelle.
    a.observer(rows[i]['action'],z['images'][i+1],z[f'film_{i+1}'],'continue')
rapport={'sdk':0,'prefixe_initial':6,'observations_finales':len(a.actions),
         'decisions':resultats,'premiere_difference':next((r['coup'] for r in resultats if not r['identique_archive']),None)}
(R/'AUDIT_SUFFIXE_CALQUES_HOTES.json').write_text(json.dumps(rapport,indent=2)+'\n')
