"""Propose des rôles concurrents lorsque l'alphabet d'un motif hérité couvre trop peu de cibles."""
import numpy as np
from chrysalide.arc3.logique.theorie import cells,centres_motifs


def proposer(th,tr,grilles):
    bases=[b for b in th.buts_motifs if b[0]=='motif_rel' and len(b)==3]
    if th.but and th.but[0]=='motif_rel' and len(th.but)==3:bases.append(th.but)
    if not bases or not grilles:return [],[]
    monde=tr.etat(grilles[-1]);col={p:o[0] for o in monde for p in cells(o)}
    gs=[np.asarray(g) for g in grilles]
    fixes={int(k) for k in np.unique(gs[0]) if all(np.array_equal(gs[0]==k,g==k) for g in gs[1:])}
    fixes.discard(tr.fond)
    buts=[];preuves=[]
    for b in dict.fromkeys(bases):
        marques=set(b[1:]);anciens=set(centres_motifs(col,marques))
        for neutre in sorted(fixes-marques):
            centres=set(centres_motifs(col,marques|{neutre}))
            if not anciens or not anciens < centres:continue
            for role in ('neutre', 'meme', 'autre'):
                nouveau=(*b,(neutre,)) if role=='neutre' else (*b,(),((neutre,role),))
                preuve={'base':b,'candidat':nouveau, 'centres_avant':len(anciens),
                    'centres_apres':len(centres), 'marque_stable':True,
                    'role_propose':role, 'roles_non_confirmes':True}
                if role=='neutre':preuve['role_neutre']='hypothese_non_confirmee'
                buts.append(nouveau);preuves.append(preuve)
    return buts,preuves
