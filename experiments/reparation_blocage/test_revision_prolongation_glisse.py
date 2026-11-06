from pathlib import Path
import copy,cloudpickle
from revision_prolongation_glisse import proposer
R=Path(__file__).parent/'runs/ka59_n4_prolongation42_auto1'
def charger():return cloudpickle.loads((R/'source42_refute.pkl').read_bytes()),cloudpickle.loads((R/'precedents.pkl').read_bytes())

def test_induction_existante_et_acquis():
 s,ps=charger();p=copy.deepcopy(s.programme);c,d=proposer(s,ps)
 assert c and d['preuve']['base']==15 and d['preuve']['classes_prolongeantes']==[15]
 assert [x['transitions'] for x in d['controles']]==[62,42]
 assert all(x['compilation_fidele'] for x in d['controles'])
 non_glisse=lambda p:[r for r in p['regles'] if not r['nom'].startswith('glissade ') and r['nom']!='sélecteur observé pour glissade']
 assert non_glisse(c.programme)==non_glisse(p) and s.programme==p
 assert c.preuve_but_elargi==s.preuve_but_elargi and c.preuve_transfert_roles==s.preuve_transfert_roles

def test_pas_de_prolongation_sans_observation_longue():
 s,ps=charger();s.grilles=s.grilles[:-1];s.lots=s.lots[:-1]
 assert proposer(s,ps)[0] is None

def test_contre_exemple_natif_pas_absorbe():
 s,ps=charger();s.grilles[-1][10][10]=7
 assert proposer(s,ps)[0] is None
