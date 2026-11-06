import unittest,os,json,itertools
from pathlib import Path
import numpy as np
from .economie import Economie
from .contrats_v4 import ajouter_memoire,porte,compiler_portes,compiler_budget
from .poussee_generale import PousseeGenerale
from .fantome_general import FantomeGeneral
ROOT=Path(os.environ.get('ASTRA4_ROOT','autonomie4'))

def gauge(value,color=4,width=64):
 im=np.ones((64,64),dtype=np.int8)*2;im[63,:]=0;im[63,:min(value,width)]=color
 if width<64:im[63,width:]=5
 return im
class Tests(unittest.TestCase):
 def test_capacity_clear(self):
  r=((0,0),);self.assertEqual(ajouter_memoire((r,r),r,2,'clear'),())
 def test_capacity_fifo(self):
  a=((0,0),);b=((1,0),);c=((2,0),);self.assertEqual(ajouter_memoire((a,b),c,2,'fifo'),(b,c))
 def test_memory_contract(self):
  with self.assertRaises(ValueError):ajouter_memoire((),(),0,'clear')
 def test_portes_asp_equivalence(self):
  import clingo
  ctl=clingo.Control();ctl.add('base',[],compiler_portes());ctl.ground([('base',[])]);got=[]
  ctl.solve(on_model=lambda m:got.extend(str(s) for s in m.symbols(shown=True)))
  expected={f'ouvert({k},{a},{b})' for k in ('held','inverse','toggle') for a,b in itertools.product((0,1),repeat=2) if porte(k,a,b)}
  self.assertEqual(set(got),expected)
 def test_budget_asp_strict(self):
  import clingo
  ctl=clingo.Control();ctl.add('base',[],compiler_budget(2,[1,2,3]));ctl.ground([('base',[])]);got=[];ctl.solve(on_model=lambda m:got.extend(str(s) for s in m.symbols(shown=True)));self.assertEqual(got,['autorise(0)'])
 def test_memory_asp_equivalence(self):
  import clingo
  from .contrats_v4 import compiler_memoire
  for cap in (1,2,4):
   for n in range(cap+2):
    for policy in ('clear','fifo'):
     ctl=clingo.Control();ctl.add('base',[],compiler_memoire(n,cap,policy));ctl.ground([('base',[])]);got=[];ctl.solve(on_model=lambda m:got.extend(int(v.arguments[0].number) for v in m.symbols(shown=True)))
     self.assertEqual(sorted(got),list(ajouter_memoire(tuple(range(n)),n,cap,policy)))
 def test_budget_unknown_abstains(self):self.assertFalse(Economie(np.zeros((64,64),dtype=np.int8)).admissible([1]))
 def test_budget_learns_capacity(self):
  e=Economie(gauge(64));prev=gauge(64)
  for k in range(1,81):
   im=gauge(int(np.floor(64*(100-k)/100)));prev[10,10]=k%2;im[10,10]=(k+1)%2;e.update(1,prev,im);prev=im
  r=e.report();self.assertTrue(r['valid']);self.assertEqual(r['capacity_interval'],[100,100]);self.assertFalse(e.admissible([1]*20));self.assertTrue(e.admissible([1]*19))
 def test_budget_click_cost(self):
  e=Economie(gauge(64));prev=gauge(64);used=0
  for k in range(1,36):
   a=[6,10,10] if k%3==0 else 1;used+=2 if isinstance(a,list) else 1;im=gauge(int(np.floor(64*(100-used)/100)));prev[10,10]=k%2;im[10,10]=(k+1)%2;e.update(a,prev,im);prev=im
  self.assertEqual(e.report()['costs']['clic'],[2])
 def test_recharge_observation(self):
  e=Economie(gauge(64));b=gauge(64)
  for k in range(1,20):
   a=gauge(64-k);b[10,10]=k%2;a[10,10]=(k+1)%2;e.update(1,b,a);b=a
  a=gauge(60);e.update(5,b,a);self.assertEqual(len(e.recharges),1);self.assertTrue(e.valid)
 def test_terminal_not_recharge(self):
  e=Economie(gauge(64));e.update(1,gauge(64),gauge(64),True,True);self.assertEqual(e.recharges,[]);self.assertEqual(e.rows[-1]['excluded_reason'],'nouveau_niveau')
 def test_variable_piece_count(self):
  for level,n in [(1,2),(2,4),(3,3),(4,3),(5,1)]:
   m=PousseeGenerale(np.load(ROOT/f'developpement/ka59_{level}_initial.npy'));self.assertEqual(m.n,n);self.assertTrue(m.assignments)
 def test_motion_simultaneous_mechanism(self):
  ims=np.load(ROOT/'developpement/sonde_g50t_5/partie.npz')['images'];m=FantomeGeneral(ims[0],ims[1],1);self.assertEqual(m.color,9);self.assertEqual(m.step,6)
 def test_portal_geometry(self):
  p=ROOT/'developpement/identifier_g50t_4/partie';ims=np.load(p.with_suffix('.npz'))['images'];a=json.loads(p.with_suffix('.json').read_text())['actions'][-1];m=FantomeGeneral(ims[-2],ims[-1],a);self.assertTrue(any(g['kind']=='portal' and len(g['doors'])==2 for g in m.groups))
 def test_cues_do_not_lose_player(self):
  ims=np.load(ROOT/'developpement/k_v2_3/partie.npz')['images'];m=PousseeGenerale(ims[0]);s=m.start
  for k,a in enumerate([2,2,4,4],1):s=m.observe(ims[k],m.step(s,a-1));self.assertIsNotNone(s)
 def test_subgoal_derived_not_coordinates(self):
  m=PousseeGenerale(np.load(ROOT/'developpement/ka59_2_initial.npy'));r=m.subgoal(m.start,seconds=4);self.assertEqual(r['status'],'PALIER');s=m.start
  for a in r['actions']:s=m.step(s,a)
  self.assertGreater(len(m.matched(s)),0)
if __name__=='__main__':unittest.main(verbosity=2)
