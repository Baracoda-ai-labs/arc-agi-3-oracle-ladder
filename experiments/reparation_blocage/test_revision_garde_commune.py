import copy,json
from pathlib import Path
import cloudpickle,numpy as np
from chaine_agent_integree import AgentIntegre,canon,lots
from chaine_coherente import Chaine
from perception_guidee import proposer_calques
from revision_garde_commune import proposer,parametrer
from chrysalide.arc3.langage import Programme

R=Path(__file__).parent

def sources():
    a=cloudpickle.loads((R/'runs/ar25_contexte8_corrige1/agent.pkl').read_bytes())
    b=AgentIntegre([a.images[3]],[],[],[]);b.installer_modele_jeu(a.memoire_jeu)
    c=next(iter(b.chaines.values()));base=getattr(c.perception,'base',c.perception)
    calques,_=proposer_calques(base,c.programme,[g.tolist() for g in a.images[3:9]], [canon(x) for x in a.actions[3:8]])
    return a,[Chaine(v.perception,v.programme,[g.tolist() for g in a.images[3:14]],lots(a.actions[3:13]),[],films=a.films[3:13]) for _,v in calques]


def test_arret_reel_conserve_deux_calques_et_lois():
    a,cs=sources()
    for source in cs:
        ancien=copy.deepcopy(source.programme)
        c,d=proposer(source)
        assert d['admis'] and d['provisoire'] and not d['generalisation']
        assert d['controle']['transitions']==10 and d['controle']['compilation_fidele']
        assert c.perception.points==source.perception.points
        assert c.perception.base.mouvements==source.perception.base.mouvements
        assert c.programme['regles'][-1]==ancien['regles'][-1]
        assert source.programme==ancien


def test_refus_ecart_natif_et_ancien_contreexemple():
    _,cs=sources();s=cs[0]
    s.grilles[-1][5][5]=(s.grilles[-1][5][5]+1)%16
    assert proposer(s)[0] is None
    _,cs=sources();s=cs[0];s.grilles[1][5][5]=(s.grilles[1][5][5]+1)%16
    assert proposer(s)[1]['refus']=='ancien_contre_exemple'


def test_niveau_source_rejoue_jusqua_victoire():
    a,_=sources();vue,p=a.memoire_jeu.acquis
    base=vue
    while hasattr(base,'base'):base=base.base
    nouveau=parametrer(base,p)
    trace=R/'runs/routage_arc1/reel/N1/partie'
    z=np.load(trace.with_suffix('.npz'));rows=json.loads(trace.with_suffix('.json').read_text())['rows']
    ancien,pc=Programme(p),Programme(nouveau)
    sa,sc=vue.scene(z['images'][0]),vue.scene(z['images'][0])
    for row in rows:
        action=canon(row['action']);ancien.step(sa,action);pc.step(sc,action)
        assert np.array_equal(vue.rendu(sa),vue.rendu(sc)) and sa.issue==sc.issue
    assert sc.issue is not None


def test_observer_conserve_portefeuille_calques():
    archive,cs=sources()
    a=AgentIntegre([archive.images[3]],[],[],[],reparation=True)
    a.images=copy.deepcopy(archive.images[:13]);a.actions=copy.deepcopy(archive.actions[:12])
    a.films=copy.deepcopy(archive.films[:12]);a.issues=copy.deepcopy(archive.issues[:12]);a.debut_contexte=3
    a.chaines={}
    for i,s in enumerate(cs):
        c=Chaine(s.perception,s.programme,s.grilles[:-1],s.lots[:-1],[],films=archive.films[3:12])
        assert c.rejouer()[1] is not None
        c.activer_atms();c.plan={'actions':[canon(4)],**c.signature(),'origine':'trace'};c._tracer_plan()
        a.chaines[str(i)]=c
    a.attente={'actions':[4],'modeles':list(a.chaines)}
    a.observer(4,archive.images[13],archive.films[12],'continue',source='trace')
    assert set(a.chaines)=={'0/garde_commune','1/garde_commune'}
    assert all(c.rejouer()[0]['transitions']==10 for c in a.chaines.values())
