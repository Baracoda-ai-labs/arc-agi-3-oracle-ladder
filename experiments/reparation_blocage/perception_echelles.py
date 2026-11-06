"""Échelles héritées alternatives après réfutation de la projection automatique."""
import time
from chrysalide.arc3.logique.faits import echelle_candidats
from representation_legacy_sans_but import construire


def proposer(historique, secondes=2):
    debut = time.process_time()
    rapport = {'candidats': [], 'budget_cpu': secondes}
    admis = []
    def essayer(echelle, nom):
        restant = secondes - (time.process_time() - debut)
        if restant <= 0:
            return None
        t = time.process_time()
        c, diagnostic = construire(historique, limite_s=restant, echelle=echelle)
        tr = c.perception.tr
        ech = (tr.s, tr.ox, tr.oy)
        rapport['candidats'].append({'nom': nom, 'echelle': ech,
            'cpu': time.process_time() - t, **diagnostic})
        if diagnostic['admis']:
            admis.append((nom, c))
        return ech
    initiale = essayer(None, 'legacy')
    if not admis and initiale is not None and time.process_time() - debut < secondes:
        vues = {initiale}
        for ech in echelle_candidats(historique['grilles']):
            ech = tuple(ech)
            if ech in vues:
                continue
            vues.add(ech)
            if time.process_time() - debut >= secondes:
                break
            essayer(ech, 'legacy_echelle_' + '_'.join(map(str, ech)))
    rapport['cpu'] = time.process_time() - debut
    rapport['budget_epuise'] = rapport['cpu'] >= secondes
    rapport['admis'] = len(admis)
    return admis, rapport
