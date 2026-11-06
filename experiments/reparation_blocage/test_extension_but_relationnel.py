from types import SimpleNamespace
import numpy as np
from extension_but_relationnel import proposer
from chrysalide.arc3.logique.theorie import VOISINS8,Theorie


def exemple():
    g=np.full((20,24),4)
    for x,y in ((5,5),(15,5)):
        g[y,x]=12
        for dx,dy in VOISINS8:g[y+dy,x+dx]=0 if dx>=0 else 2
    g[4,14]=3
    def etat(image):
        return tuple((int(k),frozenset({(0,0)}),int(x),int(y)) for (y,x),k in np.ndenumerate(image))
    return g,SimpleNamespace(fond=4,etat=etat),Theorie(buts_motifs=[('motif_rel',0,2)])


def test_extension_depuis_couverture_et_marque_stable_sans_modifier_lois():
    g,tr,th=exemple();avant=list(th.buts_motifs)
    b,d=proposer(th,tr,[g,g.copy()])
    assert b==[('motif_rel',0,2,(3,)), ('motif_rel',0,2,(),((3,'meme'),)),
               ('motif_rel',0,2,(),((3,'autre'),))]
    assert [p['role_propose'] for p in d] == ['neutre', 'meme', 'autre']
    assert all(p['roles_non_confirmes'] for p in d)
    assert d[0]['centres_avant']==1 and d[0]['centres_apres']==2
    assert th.buts_motifs==avant and th.but is None


def test_marque_mobile_ne_devient_pas_neutre_par_defaut():
    g,tr,th=exemple();precedent=g.copy();precedent[4,14]=2
    b,_=proposer(th,tr,[precedent,g])
    assert not b


def test_generation_equivariante_au_remappage_de_palette():
    g,tr,th=exemple()
    palette={0:7,2:11,3:6,4:8,12:5}
    remappe=np.vectorize(palette.__getitem__)(g)
    tr.fond=palette[tr.fond]
    th.buts_motifs=[('motif_rel',palette[0],palette[2])]
    buts,preuves=proposer(th,tr,[remappe,remappe.copy()])
    assert buts==[('motif_rel',7,11,(6,)),('motif_rel',7,11,(),((6,'meme'),)),
                  ('motif_rel',7,11,(),((6,'autre'),))]
    assert all(p['centres_avant']==1 and p['centres_apres']==2 for p in preuves)
