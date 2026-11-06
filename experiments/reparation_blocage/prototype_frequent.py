"""Alternative perceptive : forme marquée répétée plutôt que plus grande fusion."""
from collections import Counter
from perception_ancre_complete import TrajectoireAncreComplete
from perception_marqueur_candidat import TrajectoireMarqueurCandidat
from chrysalide.arc3.logique.faits import cellules,MARQUEUR

class TrajectoirePrototypeFrequent(TrajectoireAncreComplete):
    def __init__(self,grilles,actions):
        TrajectoireMarqueurCandidat.__init__(self,grilles,actions)
        comptes=Counter()
        for e in self.etats:
            for o in e:
                if o[0]>=MARQUEUR:continue
                for m in e:
                    if m[0]>=MARQUEUR and cellules(m)<=cellules(o):
                        comptes[o[0],o[1],m[0],m[2]-o[2],m[3]-o[3]]+=1
        candidats=[k for k,n in comptes.items() if n>=2]
        self.modeles_complets=[k for k in candidats if comptes[k]==max(
            comptes[q] for q in candidats if q[0]%16==k[0]%16)]
        self.ancres={c:(ax,ay) for c,f,m,ax,ay in self.modeles_complets
            if len({(a,b) for cc,ff,mm,a,b in self.modeles_complets if cc==c})==1}
        self.etats=[self.completer(e) for e in self.etats]
