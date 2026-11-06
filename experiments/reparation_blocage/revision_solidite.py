"""Réviser une seule hypothèse de blocage, sans changer perception ni mouvements."""
import copy
from chaine_coherente import Chaine
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.langage import Programme

def proposer(chaine, limite=8, projection=False):
    m=chaine.perception
    th=getattr(m,'th_releve',None)
    if th is None or not hasattr(m,'tr'):
        return [], {'statut':'representation_non_applicable'}
    candidats=[];essais=[]
    hypotheses=[('non_solide',c) for c in sorted(th.solides)[:limite]]
    if projection:
        hypotheses += [('debord_visible',c) for c in
            sorted({c for c,a in th.moves}-set(th.debordent))[:limite]]
    for operateur,classe in hypotheses:
        vue=copy.deepcopy(m)
        if operateur=='non_solide':
            vue.th_releve.solides=frozenset(th.solides-{classe})
        else:
            vue.th_releve.debordent=frozenset(th.debordent|{classe})
        programme,non=exporter(vue.th_releve,vue.tr.taille)
        if non:
            essais.append({'operateur':operateur,'classe':classe,'admis':False,'non_exporte':non});continue
        c=Chaine(vue,programme,chaine.grilles,chaine.lots,[],
                 coups_deja_joues=chaine.coups,reserve=chaine.limite,
                 films=[e['images'] if e else None for e in chaine.films.entrees])
        controle,etat=c.rejouer()
        admis=etat is not None and all(controle.get(k) for k in
                  ('catalogue_shacl','traduction_python','rejeu','compilation_fidele'))
        essais.append({'operateur':operateur,'classe':classe,'admis':admis,'controle':controle})
        if admis:
            c.activer_atms()
            c.contraste_revision=copy.deepcopy(chaine.programme)
            c.revision_locale={'operateur':operateur,'classe':classe,
                              'portee':'prefixe_observe','generalisation':False}
            candidats.append((f'{operateur}_{classe}',c))
    return candidats,{'statut':'revision_une_hypothese','essais':essais,
                     'perception_changee':False,'mouvements_changes':False,
                     'programme_avant':chaine.programme if candidats else None,
                     'patches_admis':[{'revision':c.revision_locale,'programme_apres':c.programme,
                                      'signature':c.signature()} for _,c in candidats]}

def predire_contraste(chaine,action):
    """Ancienne loi réfutée simulée sur l'état courant validé, jamais modèle admis."""
    _,etat=chaine.rejouer()
    if etat is None:return None
    pc,scene=etat
    ancien=Programme(chaine.contraste_revision)
    ancien.etat=copy.deepcopy(pc.etat)
    ancien.step(scene,action)
    return {'image':chaine.perception.rendu(scene).tolist(),'issue':scene.issue}
