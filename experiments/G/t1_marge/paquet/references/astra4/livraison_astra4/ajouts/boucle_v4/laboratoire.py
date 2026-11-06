from pathlib import Path
import json,time,numpy as np
class Laboratoire:
 def __init__(self,game,level,jeux,output):
  from chrysalide.arc3.logique.jeux import environnement
  self.env=environnement(game,jeux);f=self.env.reset();self.injected=level!=1
  if self.injected:
   self.env._game.set_level(level-1)
   image=self.env._game.camera.render(self.env._game.current_level.get_sprites())
  else:image=f.frame[-1]
  self.image=np.asarray(image);self.images=[self.image.copy()];self.films={};self.rows=[];self.start=time.monotonic();self.output=Path(output);self.output.parent.mkdir(parents=True,exist_ok=True)
  from .economie import Economie
  self.economy=Economie(self.image)
  self.completed_baseline=0
  self.game=game;self.level=level;self.finished=False;self.won=False;self.save()
 def play(self,a,purpose='experience'):
  from chrysalide.arc3.logique.jeux import jouer_action
  from .economie import BudgetInconnu
  if not self.economy.admissible([a]):raise BudgetInconnu('coût conservateur incompatible avec jauge restante ou jauge inconnue')
  before=self.image.copy()
  f=jouer_action(self.env,tuple(a) if isinstance(a,list) else a)
  self.image=np.asarray(f.frame[-1]);self.images.append(self.image.copy());self.films['film_'+str(len(self.rows)+1)]=np.asarray(f.frame)
  self.won=f.levels_completed>self.completed_baseline;self.finished=self.won or 'GAME_OVER' in str(f.state)
  self.economy.update(a,before,self.image,self.finished,self.won)
  self.rows.append(dict(step=len(self.rows)+1,action=a,purpose=purpose,levels_completed=f.levels_completed,state=str(f.state),elapsed=time.monotonic()-self.start));self.save();return self.image,np.asarray(f.frame)
 def save(self):
  tmp=self.output.with_suffix('.tmp.npz')
  np.savez_compressed(tmp,images=np.asarray(self.images),**self.films)
  tmp.replace(self.output.with_suffix('.npz'))
  self.economy.save(self.output.parent/'economie.json')
  self.output.with_suffix('.json').write_text(json.dumps(dict(game=self.game,level=self.level,injected=self.injected,actions=[r['action'] for r in self.rows],rows=self.rows,victory=self.won),indent=2))

 def next_level(self,output):
  if not self.won:raise ValueError('niveau précédent non gagné')
  from .economie import Economie
  nxt=object.__new__(Laboratoire)
  nxt.env=self.env;nxt.injected=self.injected;nxt.image=self.image.copy();nxt.images=[nxt.image.copy()];nxt.films={};nxt.rows=[];nxt.start=time.monotonic();nxt.output=Path(output);nxt.output.parent.mkdir(parents=True,exist_ok=True)
  nxt.economy=Economie(nxt.image);nxt.game=self.game;nxt.level=self.level+1;nxt.completed_baseline=self.rows[-1]['levels_completed'];nxt.finished=False;nxt.won=False;nxt.save();return nxt
