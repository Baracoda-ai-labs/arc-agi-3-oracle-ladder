from types import SimpleNamespace
from chrysalide.arc3.logique.presence import preuves_presence
from chrysalide.arc3.logique.induction import faits, resoudre_asp
from ontologie_extensible import decrire_economie

P=frozenset({(0,0)})
def obj(c,x,y=1,f=P):return (c,f,x,y)
def tr(etats,enabled=True):
    return SimpleNamespace(etats=etats, actions=[4]*(len(etats)-1), taille=(5,5), exclues=frozenset(),presence_prudente=enabled)

def test_coexistence_refute_consommation_inconditionnelle():
    t=tr([(obj(1,1),obj(2,1)),(obj(1,2),obj(2,2))])
    f,_,_=faits([(t,[0])])
    assert ':- consomme(1,2).' in f
    syms,_,_=resoudre_asp(f+'\nconsomme(1,2).',1)
    assert not syms

def test_hors_champ_inconnu_pas_detruit():
    t=tr([(obj(1,3),),(obj(1,4),),()])
    assert preuves_presence(t,1)['absences'][0]['statut']=='presence_inconnue'
    f,_,_=faits([(t,[0,1])])
    assert 'doit_disparaitre(1,0)' not in f and 'present(1,0)' not in f

def test_decoupe_exacte_reste_presente():
    f=frozenset({(0,0),(1,0)})
    t=tr([(obj(1,2,f=f),),(obj(1,3,f=f),),(obj(1,4),)])
    assert preuves_presence(t,1)['absences'][0]['statut']=='partiellement_visible'
    texte,_,_=faits([(t,[0,1])])
    assert 'present(1,0)' in texte and 'doit_disparaitre(1,0)' not in texte

def test_absence_interieure_et_ramassage_restent_possibles():
    t=tr([(obj(1,1),obj(2,2)),(obj(1,2),)])
    f,_,_=faits([(t,[0])])
    assert ':- consomme(1,2)' not in f
    syms,_,_=resoudre_asp(f+'\nconsomme(1,2).',1)
    assert 'consomme(1,2)' in syms

def test_brique_desactivee_preserve_faits_anciens():
    t=tr([(obj(1,3),),(obj(1,4),),()],False)
    f,_,_=faits([(t,[0,1])])
    assert 'doit_disparaitre(1,0)' in f

def test_pas_d_inference_par_avenir():
    t=tr([(obj(1,3),),(obj(1,4),),()])
    before=preuves_presence(t,1)
    t.etats.append((obj(2,2),));t.actions.append(4)
    assert preuves_presence(t,1)==before

def test_economie_decrite_sans_inventer_ressources():
    e=decrire_economie()
    assert all(x['statut']=='inconnu' for x in e['reserve_compteurs_vies'].values())
    assert not e['droit_action'] and 'PERCEPTION.indice_de_rendu' in e['contrats']
