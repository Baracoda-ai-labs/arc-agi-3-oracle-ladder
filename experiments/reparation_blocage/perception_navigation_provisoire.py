"""Aiguillage vers l'appariement temporel existant sans choisir une copie arbitraire."""
from objets_variables import ObjetsVariables


def construire(images,actions):
    try:return ObjetsVariables(images,actions),{'voie':'identite_unique','provisoire':True}
    except ValueError as exc:
        if 'Aucun objet mobile' not in str(exc) and 'Appariement non unique' not in str(exc):raise
        refus=str(exc)
    vue=ObjetsVariables(images,actions,identites_temporelles=True)
    return vue,{'voie':'identites_temporelles_existantes','refus_unique':refus,
                'pistes_conservees':len(vue.mobiles),'selection_par_coordonnee':False,
                'identite_causale_certifiee':False,'provisoire':True}
