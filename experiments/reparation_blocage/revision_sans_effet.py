"""Condition observée sans effet, appliquée aux lois conservées, jamais à un nouveau masque."""
import copy
import time
import numpy as np
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import _codes_c
from chrysalide.arc3.logique.faits import cases
from chrysalide.arc3.logique.induction import trouver_sans_effet
from chrysalide.arc3.logique.export_langage import exporter


def proposer(source):
    debut = time.process_time()
    diag = {'admis': False, 'hypothese': 'sans_effet_contextuel',
            'generalisation': False, 'masque_change': False}
    def fini(c=None, **infos):
        return c, {**diag, **infos, 'cpu': time.process_time() - debut}
    m = source.perception
    th, tr = getattr(m, 'th_releve', None), getattr(m, 'tr', None)
    if th is None or tr is None or not th.moves or len(source.grilles) < 2:
        return fini(refus='representation_non_applicable')
    actes = _codes_c(source.lots)
    if actes is None or any(isinstance(a, tuple) for a in actes):
        return fini(refus='actions_non_atomiques')
    programme, non = exporter(th, tr.taille)
    if non or programme != source.programme:
        return fini(refus='theorie_non_synchronisee')
    avant, apres = map(np.asarray, source.grilles[-2:])
    if not np.array_equal(m.vue(avant), m.vue(apres)):
        return fini(refus='observation_avec_mouvement')
    # Un échantillonnage grossier ne doit pas cacher un effet nouveau entre deux cases.
    for y, x in np.argwhere(avant != apres):
        if ((int(y)-tr.oy)//tr.s, (int(x)-tr.ox)//tr.s) not in tr.exclues:
            return fini(refus='changement_natif_hors_masque')
    n = len(tr.grilles)
    if n > len(source.grilles) or any(not np.array_equal(a,b) for a,b in zip(tr.grilles,source.grilles[:n])):
        return fini(refus='historique_perception_non_aligne')
    vue = copy.deepcopy(m)
    t = vue.tr
    nouveaux = [t.etat(g) for g in source.grilles[n:]]
    t.etats = list(t.etats) + nouveaux
    t.grilles = copy.deepcopy(source.grilles)
    t.cases = [cases(g,t.s,t.ox,t.oy) for g in t.grilles]
    t.actions = actes
    ancien = copy.deepcopy(vue.th_releve.sans_effet)
    trouver_sans_effet(vue.th_releve, [(t,None,None)])
    ajoutes = vue.th_releve.sans_effet - ancien
    if not ajoutes:
        return fini(refus='aucune_condition_nouvelle')
    if any(any(o[0] >= 1024 for o in (cle[2] or ())) for cle in ajoutes):
        return fini(refus='contexte_cache_non_exporte')
    vue.th_releve.sans_effet |= ancien
    if hasattr(vue,'th_plan'):
        vue.th_plan = vue.th_releve
    for k in ('_index_tr','_index'):
        vue.__dict__.pop(k,None)
    p, non = exporter(vue.th_releve,t.taille)
    if non:
        return fini(refus='export_incomplet',non_exporte=non)
    c = Chaine(vue,p,source.grilles,source.lots,source.actions,
               coups_deja_joues=source.coups,reserve=source.limite,
               films=[e['images'] if e else None for e in source.films.entrees])
    controle, etat = c.rejouer()
    if etat is None or not all(controle.get(k) for k in
            ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):
        return fini(refus='rejeu_prefixe',controle=controle)
    c.activer_atms()
    c.contraste_revision = copy.deepcopy(source.programme)
    c.revision_locale = {'operateur':'sans_effet_contextuel','portee':'prefixe_observe','generalisation':False}
    return fini(c,admis=True,controle=controle,conditions_ajoutees=len(ajoutes))
