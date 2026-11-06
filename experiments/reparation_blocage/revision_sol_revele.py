"""Réaffecter un sol directement révélé, sans changer le programme dynamique."""
import copy
import numpy as np
from chaine_coherente import Chaine
from transfert_roles import RolesReaffectes


def proposer(source):
    diagnostic = {'admis': False, 'programme_modifie': False, 'provisoire': True}
    def refus(raison):
        return None, {**diagnostic, 'refus': raison}
    if type(source.perception) is not RolesReaffectes or not source.lots:
        return refus('representation_non_applicable')
    films = [e['images'] if e else None for e in source.films.entrees]
    avant = Chaine(source.perception, source.programme, source.grilles[:-1],
                   source.lots[:-1], source.actions, films=films[:-1])
    _, courant = avant.rejouer()
    if courant is None:
        return refus('prefixe_deja_refute')
    if len(source.lots[-1]['actions']) != 1:
        return refus('action_non_atomique')
    pc, scene = courant
    anciens = copy.deepcopy(scene.sprites)
    pc.step(scene, source.action_tuple(source.lots[-1]['actions'][0]))
    m = source.perception
    pred, obs = m.rendu(scene), m.vue(source.grilles[-1])
    erreurs = {tuple(map(int, p)) for p in np.argwhere(pred != obs)}
    if not erreurs:
        return refus('aucun_ecart')
    if len(anciens) != len(scene.sprites):
        return refus('identites_non_conservees')
    liberes = set()
    for ancien, actuel in zip(anciens, scene.sprites):
        if (ancien['x'], ancien['y']) == (actuel['x'], actuel['y']):
            continue
        # L'identité et le support sont conservés : aucun objet ajouté ou remodelé.
        if ancien.get('tags') != actuel.get('tags') or not np.array_equal(ancien['pixels'], actuel['pixels']):
            return refus('support_mobile_modifie')
        ys, xs = np.where(np.asarray(ancien['pixels']) >= 0)
        avant_support = {(int(y + ancien['y']), int(x + ancien['x'])) for y, x in zip(ys, xs)}
        apres_support = {(int(y + actuel['y']), int(x + actuel['x'])) for y, x in zip(ys, xs)}
        liberes |= avant_support - apres_support
    if not erreurs <= liberes:
        return refus('ecart_hors_support_libere')
    if any(int(pred[y, x]) != m.fond or int(obs[y, x]) not in m.source.libres for y, x in erreurs):
        return refus('sol_non_etabli')
    y0, x0 = map(min, zip(*erreurs)); y1, x1 = map(max, zip(*erreurs))
    sol = np.full((y1-y0+1, x1-x0+1), -1, dtype=np.int16)
    for y, x in erreurs:
        sol[y-y0, x-x0] = obs[y, x]
    vue = copy.deepcopy(m)
    vue.statiques.append({'x': x0, 'y': y0, 'pixels': sol, 'couche': -1})
    preuve = {'x': x0, 'y': y0, 'pixels': sol.tolist(), 'origine': 'support_libere_observe'}
    vue.sols_reveles = copy.deepcopy(getattr(vue, 'sols_reveles', [])) + [preuve]
    c = Chaine(vue, copy.deepcopy(source.programme), source.grilles, source.lots, source.actions,
               coups_deja_joues=source.coups, reserve=source.limite, films=films)
    controle, etat = c.rejouer()
    if etat is None:
        return None, {**diagnostic, 'refus': 'rejeu_prefixe', 'controle': controle}
    from memoire_reparations_roles import conserver
    conserver(source,c)
    c.activer_atms()
    c.revision_locale = {'operateur': 'sol_revele', 'portee': 'cases_observees', 'generalisation': False}
    return c, {**diagnostic, 'admis': True, 'pixels_reveles': len(erreurs), 'controle': controle}
