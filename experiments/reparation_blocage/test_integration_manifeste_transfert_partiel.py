"""Pipeline réel, seul LaboP1 est simulé ; aucun import/appel SDK."""
import io,json
from pathlib import Path
import numpy as np
import pytest
import campagne_moteur_commun as campagne
import session_chaine_generique as session
from test_campagne_moteur_commun import manifeste

@pytest.mark.parametrize('actif',[False,True])
def test_manifeste_neuf_victoire_partielle_transfert_et_decision(tmp_path,monkeypatch,actif):
    class LaboSimule:
        def __init__(self,jeu,niveau,dossier,output):
            self.output=Path(output);self.output.parent.mkdir(parents=True,exist_ok=True)
            self.level=niveau;self.completed_baseline=niveau-1;self.rows=[];self.films={}
            self.finished=False;self.won=False;self.partie_gagnee=False;self.actions_disponibles=[1,7]
            self.images=[np.full((8,8),niveau-1,dtype=int)]
        @property
        def image(self):return self.images[-1]
        def play(self,action,purpose):
            gagne=self.level==1 and action==7
            self.finished=self.won=gagne
            image=np.full((8,8),1 if gagne or self.level==2 else 0,dtype=int)
            self.rows.append({'action':action,'purpose':purpose,'state':'NOT_FINISHED','levels_completed':1 if gagne else self.completed_baseline})
            self.images.append(image);film=np.array([image]);self.films[f'film_{len(self.rows)}']=film
            np.savez(self.output.with_suffix('.npz'),images=self.images,**self.films)
            return image,film
        def next_level(self,output):
            assert self.won
            return LaboSimule('fixture',2,None,output)
    agents=[];original=session.nouvel_agent
    def conserver_agent(*a,**kw):
        agent=original(*a,**kw);agents.append(agent);return agent
    monkeypatch.setattr(session,'LaboP1',LaboSimule)
    monkeypatch.setattr(session,'nouvel_agent',conserver_agent)
    monkeypatch.setattr(session,'empreintes',lambda *a:{'fixture':'sans_sdk'})
    monkeypatch.setattr(session.sys,'stdin',io.StringIO('\n'.join([
        '{"op":"advance","coups":1}','{"op":"next_level"}',
        '{"op":"advance","coups":1}','{"op":"close"}'])+'\n'))
    m=manifeste();m.update(recherche_prolongee=actif,recherche_workers=1)
    argv=campagne.commande('ar25',1,tmp_path/'run',campagne.valider(m))
    args=session.arguments_session().parse_args(argv[3:])
    session.main(args)
    assert len(agents)==2
    source,suivant=agents
    assert source.issues[-1]=='niveau' and source.modele_gagnant is None
    assert any(e['type']=='memoire_issue_observee' for e in source.journal)
    assert source.recherche_prolongee is actif and suivant.recherche_prolongee is actif
    assert source.recherche_prolongee_workers==suivant.recherche_prolongee_workers==1
    assert suivant.composition_contextuelle_auto and suivant.graine_exploration==1
    assert suivant.modele_gagnant is None and suivant.theorie_precedente is None
    assert suivant.memoire_relation_clic is None
    transfert=next(x for x in suivant.journal if x['type']=='transfert_memoire_partielle')
    assert transfert['relation_non_transferee']=='Relation partielle insuffisante'
    assert transfert['but_certifie'] is False
    assert suivant.actions==[1] and len(suivant.observations_episodes)==1
    ep=suivant.observations_episodes[0]
    assert ep['actions']==source.actions and ep['issues'][-1]=='niveau'
    assert ep['provenance']['but_certifie'] is False
    assert np.array_equal(ep['grilles'][-1],source.images[-1])
    source.images[0][0,0]=9
    assert ep['grilles'][0][0,0]==0
    decision=json.loads((args.sortie/'N2/decision_coup_00001/decision.json').read_text())
    assert decision['actions']==[1] and decision['statut']=='experience_contexte_commande'
    etat=json.loads((args.sortie/'etat.json').read_text())
    assert etat['niveau']==2 and etat['coups_reels']==4 and etat['coups_reacces']==0
    assert etat['recherche_prolongee'] is actif and etat['recherche_workers']==1
    assert etat['cpu_total_recolte_s']>=etat['cpu_parent_s']>=0
