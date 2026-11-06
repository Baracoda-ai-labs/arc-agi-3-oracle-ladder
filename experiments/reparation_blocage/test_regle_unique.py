"""Portée du patch et conservation des animations, sans jeu ni appel IA."""
import copy

import numpy as np
import pytest
from boucle_27b_regle_unique import Observation, patch_unique
from test_chaine_coherente import exemple


class ChaineFactice:
    def __init__(self):
        from chrysalide.langue import depuis_python
        self.programme=depuis_python('PROGRAMME=Programme(regles=[Regle("a",quand=False,alors=[]),Regle("b",quand=False,alors=[])])')
        self.appels=[]

    def patch(self,texte):
        self.appels.append(texte)
        return {'statut':'controle_natif_appele'}


@pytest.mark.parametrize('patch',[
    'Patch(retire=["a","b"],ajoute=[Regle("a",quand=True,alors=[])])',
    'Patch(retire=["a"],ajoute=[Regle("z",quand=True,alors=[])])',
    'Patch(retire=["a"],ajoute=[])',
    'Patch(retire=["a"],ajoute=[Regle("a",quand=False,alors=[])])',
])
def test_refuse_portee_ou_identite_sans_mutation(patch):
    c=ChaineFactice();avant=copy.deepcopy(c.programme)
    with pytest.raises(ValueError): patch_unique(c,'REPONSE=Reponse(patch='+patch+')')
    assert c.programme==avant and not c.appels


def test_une_regle_transmise_au_verificateur():
    c=ChaineFactice()
    assert patch_unique(c,'REPONSE=Reponse(patch=Patch(retire=["a"],ajoute=[Regle("a",quand=True,alors=[])]))')['statut']=='controle_natif_appele'
    assert len(c.appels)==1


def test_refus_natif_conserve_modele_avec_une_regle_fausse():
    c,_=exemple();avant=copy.deepcopy(c.programme)
    nom=next(r['nom'] for r in c.programme['regles'] if r['nom'].startswith('move'))
    resultat=patch_unique(c,f'REPONSE=Reponse(patch=Patch(retire={[nom]!r},ajoute=[Regle({nom!r},quand=False,alors=[])]))')
    assert resultat['statut']=='patch_refuse' and c.programme==avant


def test_film_conserve_transitoire_meme_si_final_identique(tmp_path):
    initial=np.zeros((64,64),dtype=np.uint8);trans=initial.copy();trans[2,3]=5
    o=Observation([initial,initial],{'film_1':np.array([trans,initial])},['UP'],None,tmp_path)
    r,images=o.outil('film',{'coup':1})
    assert r['nombre_frames']==2 and r['toutes_frames'] and len(images)==3
    from PIL import Image
    assert all(Image.open(p).size==(640,640) for p in images)
    assert images[1].read_bytes()!=images[2].read_bytes()


def test_calcul_reutilise_expression_pure(tmp_path):
    g=np.zeros((64,64),dtype=np.uint8);h=g.copy();h[1,1]=4
    o=Observation([g,h],{},['UP'],None,tmp_path)
    r,_=o.outil('calcul',{'expression':'sum(1 for i in range(4096) if grilles[0][i]!=grilles[1][i])'})
    assert r['resultat']==1


def test_suffixe_revalide_apres_chaque_coup(monkeypatch,tmp_path):
    import boucle_objets_variables
    from boucle_27b_regle_unique import jeu_reel
    c,image=exemple()

    class FauxLabo:
        def __init__(self,*args):
            self.x=3;self.image=np.array(image(3));self.actions_disponibles=[4]
            self.rows=[];self.finished=False;self.won=False;self.partie_gagnee=False

        def play(self,a,purpose):
            assert a==4
            self.x+=1;self.image=np.array(image(self.x));self.rows.append({'purpose':purpose})
            self.won=self.finished=self.x==6
            return self.image,np.array([self.image])

    monkeypatch.setattr(boucle_objets_variables,'LaboP1',FauxLabo)
    b=jeu_reel(c,np.array([image(3),image(4)]),['RIGHT'],tmp_path)
    assert b['statut']=='victoire_niveau_reelle' and b['coups_reels']==3
    assert b['initialisations_sdk']==1 and b['niveaux_gagnes']==1


def test_normalisation_conserve_arguments_sans_elargir_python():
    from boucle_27b_regle_unique import normaliser_reponse

    from chrysalide.langue import lire_reponse
    texte='Reponse(patch=Patch(retire=["a"],ajoute=[Regle("a",quand=False,alors=[])]))'
    normalise,change=normaliser_reponse(texte)
    assert change and lire_reponse(normalise)==lire_reponse('REPONSE = '+texte)
    for brut in ('open("x")','import os\n'+texte):
        assert normaliser_reponse(brut)==(brut,False)
        with pytest.raises(ValueError): lire_reponse(brut)


def test_grille_texte_sans_perte_avec_toutes_couleurs(tmp_path):
    from reprise_flux_27b import images_texte
    g=(np.arange(4096).reshape(64,64)%16).astype(np.uint8)
    o=Observation([g],{},[],None,tmp_path);p=o.image(g,'palette')
    r=images_texte([p])[0]
    reconstruit=[[c for c,n in row for _ in range(n)] for row in r['lignes']]
    assert np.array_equal(reconstruit,g)


@pytest.mark.parametrize('texte',[True,False])
def test_transport_selectionne_modele_et_modalite(monkeypatch,tmp_path,texte):
    import base64
    import json

    import reprise_flux_27b as transport
    bodies=[]

    class FauxFlux:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def raise_for_status(self): pass
        def iter_lines(self):
            yield json.dumps({'message':{'content':'{}'},'done_reason':'stop'}).encode()

    def post(url,**kw): bodies.append(kw['json']);return FauxFlux()
    monkeypatch.setattr(transport.requests,'post',post)
    g=np.zeros((64,64),dtype=np.uint8)
    p=Observation([g],{},[],None,tmp_path).image(g,'image')
    modele='petit-test' if texte else 'gemma3:4b'
    transport.appeler_flux('contrat',[p],tmp_path,1,{},modele=modele,texte_images=texte)
    assert bodies[0]['model']==modele
    if texte:
        assert 'images' not in bodies[0]['messages'][0]
        assert 'IMAGES EXACTES EN TEXTE' in bodies[0]['messages'][0]['content']
    else:
        assert base64.b64decode(bodies[0]['messages'][0]['images'][0])==p.read_bytes()
        assert bodies[0]['messages'][0]['content']=='contrat'
