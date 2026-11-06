from perception_ancre_complete import placements,TrajectoireAncreComplete
from auditer_presence_economie import load,R
from chaine_agent_integree import lots
from representation_legacy_sans_but import construire
from chrysalide.arc3.logique.theorie import rejeu

def test_ambiguite_conservee():
    f=frozenset({(0,0),(0,1),(0,2)})
    assert len(placements(f,{(0,0)},(1,1),frozenset()))==3

def test_pixel_interieur_manquant_pas_complete():
    f=frozenset({(0,0),(1,0),(2,0)})
    assert placements(f,{(2,2),(4,2)},(8,8),frozenset())==[]

def test_chaine_et_ancre_latente_prefixe():
    gs,rows=load(R/'runs/publics_ref_g0/re86/N1/partie')
    c,r=construire({'grilles':gs[:9],'lots':lots([x['action'] for x in rows[:8]])},trajectoire_factory=TrajectoireAncreComplete,presence_prudente=True,dedoublonne_poussee=True,ancre_complete=True,limite_s=2)
    tr=c.perception.tr;th=c.perception.th_releve
    assert r['admis'] and rejeu(th,tr)==(8,8,None)
    # La géométrie complète est conservée alors que son aire visible diminue.
    for cl,offset in tr.ancres.items():
        tailles={len(o[1]) for e in tr.etats for o in e if o[0]==cl}
        assert len(tailles)==1
    assert c.rejouer()[0]['cache_verifie']
    assert not r['droit_action']


def test_ancre_inapplicable_a_un_fragment_non_reconstruit():
    from chrysalide.arc3.logique.theorie import Theorie
    f=frozenset({(0,0),(0,1),(0,2)})
    t=Theorie(moves={(3,1):(0,-2)},formes={3:f},ancres_bornees={3:(0,1)})
    fragment=((3,frozenset({(0,0)}),2,1),)
    assert t.pas(fragment,1,(5,5))[0]==fragment
