import itertools
import pytest
from chrysalide.arc3.logique.theorie import Theorie, VOISINS8
from plan_parite import proposer, resoudre


def cas(erreurs=()):
    f = frozenset({(0, 0)})
    centre = (8, 8)
    pixels = {centre: 7}
    for i, (dx, dy) in enumerate(VOISINS8):
        pixels[8+dx, 8+dy] = 1 if i % 2 else 2
        pixels[8+4*dx, 8+4*dy] = 7 if i % 2 else 6
    for p in erreurs:
        pixels[p] = 13-pixels[p]
    monde = tuple((c, f, x, y) for (x, y), c in pixels.items())
    th = Theorie(bascule={6:7, 7:6}, motif_formes=((f, frozenset({(0,0,f)})),),
                 but=('motif_rel',1,2))
    return th, monde


def test_gf2_compare_exhaustif():
    # Toutes les équations possibles sur trois variables, puis toutes leurs paires.
    equations = list(itertools.product(range(8), range(2)))
    for systeme in itertools.product(equations, repeat=2):
        possibles = [x for x in range(8) if all((x&m).bit_count()%2 == b for m,b in systeme)]
        obtenu = resoudre(systeme,3)
        assert (obtenu is None) == (not possibles)
        if obtenu is not None:
            assert obtenu in possibles


@pytest.mark.parametrize('erreurs', [(), ((4,4),), ((4,4),(8,4)), ((4,4),(12,12)), ((12,4),)])
def test_plan_compare_exhaustif(erreurs):
    th, monde = cas(erreurs)
    actions = [(6,4,4),(6,8,4),(6,12,12)]
    solutions = []
    for bits in itertools.product((0,1), repeat=len(actions)):
        etat=monde
        for a,b in zip(actions,bits):
            if b: etat,_=th.pas(etat,a,(20,20))
        if th.atteint(etat): solutions.append(bits)
    plan, diag=proposer(th,monde,actions,(20,20))
    assert (plan is not None) == bool(solutions)
    assert diag['droit_action'] is False
    if plan is not None:
        fin=monde
        for a in plan: fin,_=th.pas(fin,a,(20,20))
        assert th.atteint(fin)


@pytest.mark.parametrize('champ,valeur', [('moves',{(7,1):(1,0)}),
    ('selection_clic',(7,0,0)),('jauge',(10,1)),('autonomes',{7:6}),
    ('clic_configs',((1,(),()),)),('exclusif',True), ('zone',7), ('tenue',((1,2),)),
    ('tenue_cases',((1,(),(),()),)), ('peint_contact',frozenset({(7,frozenset({(0,0)}))}))])
def test_refuse_mouvement_selection_horloge_et_autres(champ,valeur):
    th,monde=cas();setattr(th,champ,valeur)
    plan,diag=proposer(th,monde,[(6,4,4)],(20,20))
    assert plan is None and diag['statut']=='hors_contrat'


def test_refuse_hitboxes_dependantes_ordre_sans_recouvrement_pixels():
    th,monde=cas()
    f=frozenset({(0,0),(2,0)});g=frozenset({(1,0),(1,1)})
    monde=monde+((6,f,15,15),(7,g,15,15))
    th.hitbox_formes=frozenset({f,g})
    plan,diag=proposer(th,monde,[(6,16,15)],(20,20))
    assert plan is None and diag['raison']=='hitboxes_ambigues_ordre_dependant'


def test_roles_neutres_et_couleurs_non_figees():
    th,monde=cas(((4,4),))
    dx,dy=VOISINS8[0]
    monde=tuple((3 if (x,y)==(8+dx,8+dy) else c,f,x,y) for c,f,x,y in monde)
    th.but=('motif_rel',1,2,(3,))
    plan,diag=proposer(th,monde,[],(20,20))
    assert plan == []
    palette={1:10,2:11,3:12,6:4,7:5}
    monde=tuple((palette[c],f,x,y) for c,f,x,y in monde)
    th.bascule={4:5,5:4};th.but=('motif_rel',10,11,(12,))
    assert proposer(th,monde,[],(20,20))[0] == []


def test_cycle_non_binaire_refuse():
    th,monde=cas();th.bascule={6:7,7:8,8:6}
    assert proposer(th,monde,[],(20,20))[1]['raison']=='bascule_pas_un_unique_cycle_binaire'


@pytest.mark.parametrize('role', ['meme', 'autre'])
def test_role_additionnel_non_neutre(role):
    th,monde=cas()
    dx,dy=VOISINS8[0]
    monde=tuple((3 if (x,y)==(8+dx,8+dy) else c,f,x,y) for c,f,x,y in monde)
    th.but=('motif_rel',1,2,(),((3,role),))
    plan,diag=proposer(th,monde,[(6,8+4*dx,8+4*dy)],(20,20))
    assert plan is not None
    assert len(plan)==(role=='meme')


@pytest.mark.parametrize('formes', [True, False])
def test_motif_fallback_et_metadonnees_sans_effet(formes):
    import copy
    th,monde=cas(((4,4),))
    th.motif=frozenset({(0,0)})
    if not formes: th.motif_formes=()
    actions=[(6,4,4),(6,8,4)]
    plan,diag=proposer(th,monde,actions,(20,20))
    assert plan is not None
    autre=copy.deepcopy(th)
    autre.formes={6:frozenset({(0,0)})}
    autre.hors_jeu=frozenset({(4,4),(8,4)})
    for a in actions:
        assert autre.pas(monde,a,(20,20))==th.pas(monde,a,(20,20))
    assert proposer(autre,monde,actions,(20,20))== (plan,diag)


def test_raccord_chaine_verifie_vraiment_plan_et_conversion(monkeypatch):
    from types import SimpleNamespace
    from chrysalide.arc3.logique.export_langage import exporter
    from chrysalide.arc3.moteur import _sprite
    from chrysalide.arc3.ontologie_exec import Scene
    from chrysalide.arc3 import moteur
    from chaine_coherente import Chaine
    from plan_parite import proposer_chaine
    th,monde=cas(((4,4),))
    texte,non=exporter(th,(20,20));assert not non
    tr=SimpleNamespace(etats=[monde],etat=lambda g:monde,taille=(20,20),
        s=3,ox=2,oy=2,fond=0,exclues=set(),camera=[])
    vue=SimpleNamespace(th_releve=th,tr=tr,
        scene=lambda g:Scene((20,20),0,0,[dict(_sprite(o),couche=0) for o in monde]))
    # Vue20 rendue64 : échelle3, marges2 ; case4 → pixel15.
    c=Chaine(vue,texte,[[[0]]],[],[('MOUSE',15,15)])
    monkeypatch.setattr(moteur,'_clics_offerts',lambda th,tr:[(6,4,4)])
    resultat=proposer_chaine(c)
    assert resultat['statut']=='plan_simule_valide', resultat
    assert c.plan['actions']==[['MOUSE',15,15]]
    assert c._verifie is not None
    assert resultat['preuve']['issue']=='niveau'
    # Un rejet du contrôle ne doit jamais être converti en succès GF2.
    monkeypatch.setattr(c,'adopter_plan',lambda *a,**kw:{'statut':'plan_refuse'})
    assert proposer_chaine(c)['statut']=='plan_refuse'
