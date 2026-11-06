from pathlib import Path
import copy,cloudpickle
from revision_poussee_chaine import proposer
P=Path(__file__).parent/'runs/ka59_n4_poussee51_auto1/source51_refute.pkl'

def test_poussee_existante_et_acquis():
 s=cloudpickle.loads(P.read_bytes());old=copy.deepcopy(s.programme);c,d=proposer(s)
 assert c and d['chemin_secondaire']==[(38,47),(38,50),(38,53)]
 assert [x['transitions'] for x in d['controles']]==[62,51]
 assert all(x['compilation_fidele'] for x in d['controles'])
 hors=lambda p:[r for r in p['regles'] if not r['nom'].startswith('glissade c')]
 assert hors(c.programme)==hors(old) and s.programme==old
 assert c.preuve_but_elargi==s.preuve_but_elargi and c.preuve_transfert_roles==s.preuve_transfert_roles
 assert c.perception.classes_bloquantes_poussee

def test_secondaire_non_filme_refuse():
 s=cloudpickle.loads(P.read_bytes());s.films.entrees[-1]=None
 assert proposer(s)[1]['refus']=='film_insuffisant'

def test_erreur_native_hors_interaction_refusee():
 s=cloudpickle.loads(P.read_bytes());s.grilles[-1][10][10]=7
 assert proposer(s)[0] is None
