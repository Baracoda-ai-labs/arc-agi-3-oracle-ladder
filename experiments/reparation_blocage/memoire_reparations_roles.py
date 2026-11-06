"""Provenance conservée lors des réparations d'un modèle de rôles."""
import copy

CHAMPS=('but_inconnu','preuve_revision_but','intervalles_contexte',
        'preuve_classe_glissable','preuve_but_elargi','but_hypothese_non_confirmee',
        'preuve_transfert_roles','modele_source_transfert')

def conserver(source,candidat):
    for nom in CHAMPS:
        if hasattr(source,nom):setattr(candidat,nom,copy.deepcopy(getattr(source,nom)))
