import json
from pathlib import Path
from revision_orientation import Revision
R=Path(__file__).parent
def moteur():return Revision([json.loads((R/n).read_text())['fonctions'] for n in ('orientations_dc.json','orientations_dc_arithmetique.json','orientations_dc_conditions.json')])
def test_extension_et_contradiction():
 l=moteur();l.ajouter(2,0,0);l.ajouter(2,1,2)
 assert not l.candidats(2);assert l.ajuster(2);assert l.niveaux['2']==1
 assert all(f['valeurs'][0]==0 and f['valeurs'][1]==2 for f in l.candidats(2))
 l.ajouter(2,1,3);assert not l.ajuster(2)
 assert l.revisions[-1]['statut']=='representation_insuffisante'
 assert not l.memoire()['promotion_durable']
def test_choix_exclut_repetition_et_route_connue():
 l=moteur()
 for a in (1,2,3,4):
  l.ajouter(a,0,1);l.ajouter(a,3,0);assert l.ajuster(a)
 choix=l.choix([0],[1,2,3,4]);assert choix['acces'] and len(choix['route'])==2
 assert l.nouveau(choix['route'][-1],[1])
