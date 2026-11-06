"""Réaffectation exacte des motifs appris, y compris au bord ; pas d'induction."""
import copy
import numpy as np
from objets_variables import ObjetsVariables, localiser
from chaine_coherente import Chaine, empreinte


def reaffecter(source, image):
    diag={'admis':False,'provisoire':True,'but_ajoute':False,
          'programme_modifie':False,'masque_herite_provisoire':True}
    def refus(raison):return None,{**diag,'refus':raison}
    v=source.perception
    if type(v) is not ObjetsVariables or source.refute:
        return refus('contrat_source_non_applicable')
    if source.programme != v.programme():
        return refus('programme_hors_contrat_sans_but')
    check,state=source.rejouer()
    if state is None or not check.get('compilation_fidele'):
        return refus('source_non_admissible')
    image=np.asarray(image)
    if image.shape!=np.asarray(source.grilles[0]).shape:
        return refus('dimensions_instance_differentes')
    v=copy.deepcopy(v);v._positions_connues={}
    propre=v.vue(image)
    try:
        positions=[localiser(propre,m) for m in v.mobiles]
        statiques=[localiser(propre,s['pixels']) for s in v.statiques]
    except (ValueError,TypeError) as exc:
        return refus(str(exc))
    # Aucun fragment d'un mobile n'est assimilé à un autre rôle mobile.
    occupations=[]
    for motif,(x,y) in zip(v.mobiles,positions):
        pts={(y+int(dy),x+int(dx)) for dy,dx in np.argwhere(motif>=0)}
        if any(pts & anciens for anciens in occupations):return refus('mobiles_superposes')
        occupations.append(pts)
    v.initiales=positions
    for s,(x,y) in zip(v.statiques,statiques):s['x'],s['y']=x,y
    v.buts=[]
    v.decor=propre.copy()
    for pts in occupations:
        for y,x in pts:v.decor[y,x]=v.fond
    scene=v.scene(image)
    if not np.array_equal(v.rendu(scene),propre):return refus('image_non_reconstruite')
    c=Chaine(v,copy.deepcopy(source.programme),[image.tolist()],[],source.actions)
    check,state=c.rejouer()
    if state is None or not all(check.get(k) for k in ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
        return refus('instance_non_admissible')
    c.activer_atms()
    diag.update(admis=True,controle=check,positions_mobiles=positions,
                positions_statiques=statiques,programme_sha256=empreinte(source.programme),
                portee='image_initiale_seulement',mouvements_reappris=0)
    c.preuve_reaffectation_sans_but=copy.deepcopy(diag)
    return c,diag
