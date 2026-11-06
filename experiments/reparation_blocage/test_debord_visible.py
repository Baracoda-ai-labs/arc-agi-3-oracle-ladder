import numpy as np
from representation_legacy_sans_but import bord_masque,construire
from auditer_presence_economie import load,R,factory
from chaine_agent_integree import lots
from chrysalide.arc3.logique.theorie import rejeu

def test_masque_interieur_non_franchissable():
    mask=frozenset({(4,x) for x in range(5)}|{(2,2)})
    assert bord_masque((5,5),mask)==mask-{(2,2)}

def test_prefixe_re86_chaine_admise_et_signature_stable():
    gs,rows=load(R/'runs/publics_ref_g0/re86/N1/partie')
    h={'grilles':gs[:9],'lots':lots([r['action'] for r in rows[:8]])}
    c,r=construire(h,limite_s=2,trajectoire_factory=factory,presence_prudente=True,dedoublonne_poussee=True,debord_visible=True)
    assert r['admis'],r
    assert rejeu(c.perception.th_releve,c.perception.tr)==(8,8,None)
    assert c.rejouer()[0]['cache_verifie']
    assert len(c.perception.tr.exclues)==64
    assert not r['droit_action'] and 'but' in r['inconnus']
