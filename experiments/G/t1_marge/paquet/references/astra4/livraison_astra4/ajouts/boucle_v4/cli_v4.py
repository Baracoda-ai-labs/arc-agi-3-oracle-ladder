import argparse,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--game',choices=['g50t','ka59'],required=True);p.add_argument('--level',type=int,required=True);p.add_argument('--jeux',required=True);p.add_argument('--output',required=True);p.add_argument('--budget',type=int,default=150);p.add_argument('--seconds',type=float,default=90)
 a=p.parse_args()
 if a.game=='g50t':from .agent_fantome import run
 else:from .agent_poussee import run
 r=run(a.level,a.jeux,a.output,a.budget,a.seconds);print(json.dumps({k:r[k] for k in ('game','level','victory','actions','seconds','reason')}))
if __name__=='__main__':main()
