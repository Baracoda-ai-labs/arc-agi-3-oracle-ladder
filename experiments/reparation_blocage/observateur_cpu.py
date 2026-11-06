"""Une tâche sans attente ni droit d'action, au-dessus du processus moteur existant."""
import copy
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor


def cle_instantane(historique, contexte):
    contenu = json.dumps([contexte, historique], sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(contenu.encode()).hexdigest()


class Observateur:
    """Un seul appelant propriétaire ; l'ouvrier ne reçoit que des données copiées."""
    def __init__(self, distant):
        self.distant = distant
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='observateur_cpu')
        self.future = None
        self.ferme = False

    def soumettre(self, historique, contexte):
        if self.ferme:
            return {'statut': 'ferme'}
        if self.future is not None:
            return {'statut': 'occupe_sans_file'}
        debut = time.monotonic()
        hist, ctx = copy.deepcopy(historique), copy.deepcopy(contexte)
        self.cle = cle_instantane(hist, ctx)
        self.contexte = ctx
        self.debut = debut
        self.future = self.pool.submit(self.distant.proposer, hist, coup=ctx.get("coup", len(hist.get("lots", []))))
        return {'statut': 'soumis', 'cle': self.cle, 'mur_soumission_s': time.monotonic() - debut}

    def lire(self, cle_courante):
        if self.future is None:
            return {'statut': 'absent'}
        if not self.future.done():
            return {'statut': 'en_cours'}
        future, self.future = self.future, None
        rapport = {'cle': self.cle, 'contexte': copy.deepcopy(self.contexte),
                   'perime': cle_courante != self.cle, 'droit_action': False,
                   'mur_depuis_soumission_s': time.monotonic() - self.debut}
        try:
            rapport.update(statut='termine', proposition=future.result())
        except Exception as e:  # noqa: BLE001 — une erreur d'observation ne doit pas arrêter l'agent
            rapport.update(statut='erreur', erreur=repr(e))
        return rapport

    def fermer(self):
        self.ferme = True
        self.distant.fermer()
        self.pool.shutdown(wait=True, cancel_futures=True)
