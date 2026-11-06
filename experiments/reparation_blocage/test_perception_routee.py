import os,json
from pathlib import Path
import numpy as np
import pytest
from chaine_agent_integree import AgentIntegre
from perception_routee import proposer,completion_causale
R=Path(__file__).parent

def test_route_trace_admet_projection_apres_refus_anciens_profils():
 p=R/'runs/publics_ref_g0/re86/N1/partie';z=np.load(p.with_suffix('.npz'));rows=json.loads(p.with_suffix('.json').read_text())['rows'];before=os.environ.get('CHRYS_AMODAL')
 a=AgentIntegre(z['images'][:9],[x['action'] for x in rows[:8]],[z[f'film_{i+1}'] for i in range(8)],['continue']*8,routage_classes=True)
 a.reconstruire();r=next(x for x in a.journal if x['type']=='perception_routee')
 assert a.chaines and r['diagnostics_accessibles']==2
 small,pixels,projection=r['candidats']
 assert small['contradictions_perceptives'] and not pixels['contradictions_perceptives']
 assert pixels['diagnostic']['lois'] and pixels['corrections_evaluees']
 assert not small['droit_planifier'] and not pixels['droit_planifier']
 assert projection['droit_planifier'] and projection['controle']['admis']
 assert not any(c['adoptee'] for c in pixels['corrections_evaluees'])
 assert os.environ.get('CHRYS_AMODAL')==before

def test_pas_de_route_sur_interface_seule():
 candidates,r=proposer({'transformation_motif':{'preuves':[{'region_bord':True}]}},{})
 assert not candidates and r['statut']=='non_requis'

def test_restaurer_profil_meme_sur_exception(monkeypatch):
 monkeypatch.setenv('CHRYS_AMODAL','2')
 with pytest.raises(RuntimeError):
  with completion_causale():
   assert os.environ['CHRYS_AMODAL']=='1'
   raise RuntimeError('test')
 assert os.environ['CHRYS_AMODAL']=='2'
