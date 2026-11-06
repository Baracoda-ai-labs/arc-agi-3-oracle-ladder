"""Complétion géométrique existante sans confondre candidat visuel et sélection prouvée."""
from chrysalide.arc3.logique.faits import (Trajectoire,objets,recoller_marqueurs,MARQUEUR,
    cellules,apparier,formes_mobiles,reclasser_formes,comportements,desouder)

def formes_visibles(etats, actions, taille, exclues):
    """Conserve les classes déjà étayées ; étend aux découpes exactes au bord.

    Les vecteurs viennent exclusivement de translations de formes intactes.
    Une forme tronquée ambiguë ne reçoit aucune classe nouvelle.
    """
    fm = {}
    for fin in range(3, len(etats)+1):
        for key, code in formes_mobiles(etats[:fin]).items():
            fm.setdefault(key, code)
    vecteurs = {}
    for t, (avant, apres) in enumerate(zip(etats, etats[1:])):
        pairs, _ = apparier(avant, apres)
        for i,j in pairs:
            o=avant[i]
            if j is not None and (o[0],o[1]) in fm:
                v=(apres[j][2]-o[2], apres[j][3]-o[3])
                if v != (0,0):vecteurs.setdefault((fm[o[0],o[1]],actions[t]),set()).add(v)
    w,h=taille
    for t, (avant, apres) in enumerate(zip(etats, etats[1:])):
        for o in apres:
            candidats=set()
            for prev in avant:
                code=fm.get((prev[0],prev[1]))
                vs=vecteurs.get((code,actions[t]),set())
                if prev[0]!=o[0] or len(vs)!=1:continue
                dx,dy=next(iter(vs))
                entier={(x+dx,y+dy) for x,y in cellules(prev)}
                visible={(x,y) for x,y in entier if 0<=x<w and 0<=y<h and (y,x) not in exclues}
                if visible and visible!=entier and visible==cellules(o):candidats.add(code)
            if len(candidats)==1:fm.setdefault((o[0],o[1]),next(iter(candidats)))
    return fm

class TrajectoireMarqueurCandidat(Trajectoire):
    def __init__(self,grilles,actions):
        super().__init__(grilles,actions,ech=(1,0,0))
        raw=[objets(c,self.fond,self.exclues,self.diagonales) for c in self.cases]
        merged=[recoller_marqueurs(e,diagonales=self.diagonales) for e in raw]
        self.marqueurs=frozenset(o[0]-MARQUEUR for e in merged for o in e if o[0]>=MARQUEUR)
        if not self.marqueurs:raise ValueError('Aucune coupure par marqueur géométrique')
        self.marqueur=True
        merged=desouder(merged)
        self.formes=formes_visibles(merged,self.actions,self.taille,self.exclues)
        self.details=frozenset();self.atomiques=frozenset();self.tuiles=None
        self._bruts=[reclasser_formes(e,self.formes) for e in merged]
        self.etats,self._carte=comportements(self._bruts,self.actions,self.atomiques)
