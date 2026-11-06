import json
from pathlib import Path
import pytest
from export_attribution_commune import exporter,exiger_evaluable


def preparer(tmp_path,rows,decisions=None,argv=None):
 out=tmp_path/'graine_0'/'ar25';p=out/'session'/'N1';p.mkdir(parents=True)
 (out/'commande.json').write_text(json.dumps({'argv':argv if argv is not None else ['python','session.py','--neuf']}))
 (p/'partie.json').write_text(json.dumps({'rows':rows,'injected':False}))
 for i,d in (decisions or {}).items():
  folder=out/'session'/f'decision_coup_{i:05}';folder.mkdir()
  (folder/'decision.json').write_text(json.dumps(d))
 lignes=[dict(niveau=1,coups=len(rows),victoire=any(r.get('levels_completed',0)>=1 for r in rows))]
 return out,lignes

def test_exploration_est_intervention_et_victoire_moteur(tmp_path):
 rows=[dict(action=1,purpose='acquisition_generique',levels_completed=0),dict(action=['clic',2,3],purpose='experience_conditionnelle',levels_completed=1)]
 out,l=preparer(tmp_path,rows,{2:{'actions':[['clic',2,3]],'origine':'p1_graphe_observe'}})
 result,m=exporter(out,l)
 assert m['attribution_cf2a1f81']=='preuves_actions_completes'
 assert result[0]['gagnant']=='moteur'
 events=[json.loads(x) for x in (out/'journal_jeu.jsonl').read_text().splitlines()]
 assert [e['coup'] for e in events[1:]]==[1,2]
 assert events[2]['origine']=='decision_controleur_commun'

@pytest.mark.parametrize('probleme',['absent','action_differente','interruption','injection','sans_neuf'])
def test_preuves_incompletes_non_evaluables(tmp_path,probleme):
 out,l=preparer(tmp_path,[dict(action=2,purpose='experience',levels_completed=1)],{1:{'actions':[1 if probleme=='action_differente' else 2]}} if probleme!='absent' else {},argv=['python'] if probleme=='sans_neuf' else None)
 if probleme=='injection':
  p=out/'session'/'N1'/'partie.json';j=json.loads(p.read_text());j['injected']=True;p.write_text(json.dumps(j))
 result,m=exporter(out,l,interruption=probleme=='interruption')
 assert m['attribution_cf2a1f81']=='non_evaluable' and result[0]['gagnant'] is None
 (out/'resultat.json').write_text(json.dumps(result))
 with pytest.raises(ValueError,match='non évaluable'):exiger_evaluable([out.parent])

def test_perte_sans_victoire_intervention_presentee(tmp_path):
 out,l=preparer(tmp_path,[dict(action=3,purpose='experience',levels_completed=0)],{1:{'actions':[3]}})
 result,m=exporter(out,l)
 (out/'resultat.json').write_text(json.dumps(result));exiger_evaluable([out.parent])
 assert not result[0]['victoire'] and result[0]['gagnant'] is None
 events=[json.loads(x) for x in (out/'journal_jeu.jsonl').read_text().splitlines()]
 assert events[1]['etape']=='intervention' and events[1]['coup']==1

def test_aucun_fichier_ne_vaut_preuve(tmp_path):
 with pytest.raises(ValueError):exiger_evaluable([tmp_path])

def test_imputation_historique_cf2a1f81_fixture_synthetique(tmp_path):
 import importlib.util
 path=Path(__file__).parents[1]/'controle'/'controle_passages.py'
 spec=importlib.util.spec_from_file_location('controle_fixture',path)
 controle=importlib.util.module_from_spec(spec);spec.loader.exec_module(controle)
 out,l=preparer(tmp_path,[dict(action=3,purpose='experience',levels_completed=0)],{1:{'actions':[3]}})
 resultat,meta=exporter(out,l);(out/'resultat.json').write_text(json.dumps(resultat))
 ref=tmp_path/'reference_fictive'/'ar25';ref.mkdir(parents=True)
 (ref/'resultat.json').write_text(json.dumps([{'niveau':1,'victoire':True,'coups':2,'gagnant':'generique'}]))
 exiger_evaluable([out.parent])
 verdict=controle.imputation(ref.parent,out.parent)
 assert verdict['imputables']==[('ar25',1,1,2)] and verdict['indirects']==[]
 # Règle historique stricte AVANT : égalité n'est pas transformée artificiellement.
 (ref/'resultat.json').write_text(json.dumps([{'niveau':1,'victoire':True,'coups':1,'gagnant':'generique'}]))
 assert controle.imputation(ref.parent,out.parent)['indirects']==[('ar25',1,1,1)]
 assert controle.entonnoir(out.parent)['intervention']==1
