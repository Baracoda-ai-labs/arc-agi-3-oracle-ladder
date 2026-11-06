from pathlib import Path
import numpy as np
from economie_film_observee import analyser,composantes,proposer_indicateur


def data():
    p=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_trace21/partie.npz'
    with np.load(p) as z:a=z['images'][20].copy();film=z['film_21'].copy()
    # Forme choisie par le prototype de sélection au18, pas par un mécanisme attendu.
    formes={f for c,f,x,y in composantes(a) if c==14 and len(f)==12}
    assert len(formes)==1
    return a,film,formes.pop()


def test_recoloration_pas_disparition():
    r=analyser(*data())
    assert (r['population_visible_avant'],r['population_visible_apres'])==(5,4)
    assert any(len(e['changements'])==4 and e['image']==16 for e in r['recolorations'])
    assert not r['consommation_validee'] and not r['defaite_validee']
    assert all(v['statut']=='inconnu' for v in r['economie']['reserve_compteurs_vies'].values())


def test_prefixe_ne_devine_pas_recoloration_future():
    a,f,forme=data();r=analyser(a,f[:15],forme)
    assert r['recolorations']==[] and not r['nouveaux_composants']
    assert r['population_visible_apres']==4


def test_permutation_de_couleurs_garde_population():
    a,f,forme=data();palette=np.arange(16)[::-1]
    r=analyser(palette[a],palette[f],forme)
    assert r['population_visible_apres']==4
    assert any(len(e['changements'])==4 for e in r['recolorations'])


def test_proposition_non_terminale_et_pas_clic_hors_offre():
    a,f,forme=data();r=analyser(a,f,forme);d=proposer_indicateur(r,[6])
    assert d and d['risque']=='inconnu' and d['but']=='inconnu'
    assert proposer_indicateur(r,[1,2]) is None
    assert proposer_indicateur(analyser(a,f,forme,'defaite'),[6]) is None
    assert proposer_indicateur(r,[6],d['actions']) is None
