"""Forme mémorisée, origine géométrique et projection visible séparées."""
from perception_marqueur_candidat import TrajectoireMarqueurCandidat
from chrysalide.arc3.logique.faits import cellules, MARQUEUR


def placements(forme, visible, taille, masque):
    """Origines dont la projection est exactement l'observation, sans pixel ajouté."""
    if not visible:return []
    w,h=taille;x,y=min(visible)
    out=[]
    for dx,dy in forme:
        ox,oy=x-dx,y-dy
        projetee={(ox+a,oy+b) for a,b in forme if 0<=ox+a<w and 0<=oy+b<h and (oy+b,ox+a) not in masque}
        if projetee==visible:out.append((ox,oy))
    return sorted(set(out))


class TrajectoireAncreComplete(TrajectoireMarqueurCandidat):
    def __init__(self,grilles,actions):
        super().__init__(grilles,actions)
        self.modeles_complets={}
        # La forme et son repère ne viennent que d'objets vus avec un marqueur.
        for e in self.etats:
            for o in e:
                if o[0]>=MARQUEUR:continue
                for m in e:
                    if m[0]<MARQUEUR or not cellules(m)<=cellules(o):continue
                    key=(o[0],o[1],m[0],m[2]-o[2],m[3]-o[3])
                    self.modeles_complets[key]=self.modeles_complets.get(key,0)+1
        # Deux observations, même décalage ; garder seulement les plus grandes
        # formes déjà vues pour chaque classe. Pas d'invention de géométrie cachée.
        candidats=[k for k,n in self.modeles_complets.items() if n>=2]
        self.modeles_complets=[k for k in candidats if len(k[1])==max(len(q[1]) for q in candidats if q[0]==k[0])]
        self.ancres={c:(ax,ay) for c,f,m,ax,ay in self.modeles_complets
                     if len({(a,b) for cc,ff,mm,a,b in self.modeles_complets if cc==c})==1}
        self.etats=[self.completer(e) for e in self.etats]

    def completer(self,e):
        resultat=[];marqueurs=[]
        for o in e:
            if o[0]>=MARQUEUR:
                resultat.append(o);continue
            solutions=[]
            for c,f,m,ax,ay in self.modeles_complets:
                if c%16!=o[0]%16 or len(o[1])>len(f):continue
                for x,y in placements(f,cellules(o),self.taille,self.exclues):
                    solutions.append((c,f,x,y,m,ax,ay))
            if len(solutions)!=1:
                resultat.append(o);continue
            c,f,x,y,m,ax,ay=solutions[0]
            resultat.append((c,f,x,y))
            # Le détail disparu est restitué uniquement hors de la vue évaluée.
            mx,my=x+ax,y+ay;w,h=self.taille
            if (not (0<=mx<w and 0<=my<h) or (my,mx) in self.exclues):
                marqueurs.append((m,frozenset({(0,0)}),mx,my))
        return tuple(sorted(set(resultat+marqueurs),key=lambda o:(o[0],o[2],o[3],sorted(o[1]))))

    def etat(self,g):
        return self.completer(super().etat(g))
