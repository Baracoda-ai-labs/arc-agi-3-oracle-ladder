"""Parcours réel depuis RESET; arrêt impératif avant toute action sur N6 en développement."""
import argparse,json
from pathlib import Path
from .laboratoire import Laboratoire

def run(game,jeux,output,max_level=5,budget=150,seconds=90):
 if max_level>5:raise ValueError('Ce protocole de développement interdit N6/N7')
 if game=='g50t':from .agent_fantome import run as agent
 else:from .agent_poussee import run as agent
 root=Path(output);root.mkdir(parents=True,exist_ok=True);lab=Laboratoire(game,1,jeux,root/'N1'/'partie');results=[]
 for level in range(1,max_level+1):
  r=agent(level,jeux,root/f'N{level}',budget,seconds,lab=lab);results.append({k:r[k] for k in ('game','level','victory','actions','seconds','reason')})
  (root/'progression.json').write_text(json.dumps(results,indent=2))
  if not r['victory'] or level==max_level:break
  lab=lab.next_level(root/f'N{level+1}'/'partie')
 return results
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--game',required=True);p.add_argument('--jeux',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(run(a.game,a.jeux,a.output)))
