"""Paramètres sémantiques d'export persistés avec la perception du modèle."""
import os
from contextlib import contextmanager
from chrysalide.arc3.logique.export_langage import exporter


@contextmanager
def appliquer_contexte_export(perception):
    contexte = dict(getattr(perception, 'contexte_export', {}))
    if any(not isinstance(k, str) or not k.startswith('CHRYS_') or
           not isinstance(v, str) for k, v in contexte.items()):
        raise ValueError('Contexte export attendu : variables CHRYS_ et valeurs texte')
    avant = {k: os.environ.get(k) for k in contexte}
    try:
        os.environ.update(contexte)
        yield
    finally:
        for k, v in avant.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def exporter_contextuel(perception, theorie, taille):
    # Aucune variable d'environnement ne reste imposée au retour, notamment
    # lorsque l'appelant est un générateur suspendu entre deux candidats.
    with appliquer_contexte_export(perception):
        return exporter(theorie, taille)
