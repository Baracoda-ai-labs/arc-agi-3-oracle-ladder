"""Attestation bornée du candidat, distincte du hash agent_p1 de référence.

Inventaire explicite et comparaison avec les empreintes déclarées par la session.
Ne prétend pas capturer les modules dynamiques chargés après cette déclaration,
ni les bibliothèques système transitives d'une extension native.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

DISTRIBUTIONS=('numpy','arc-agi','arcengine','cloudpickle','clingo')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventaire(root):
    root=Path(root)
    paths=set(root.glob('*.py')) | set(root.glob('*.json'))
    for relatif in ('paquet/chrysalide','paquet/livraison_p1/code','paquet/livraison_explo/code',
                    'paquet/references/astra4/livraison_astra4/ajouts/boucle_v4'):
        dossier=root/relatif
        for ext in ('*.py','*.json','*.so','*.dylib'):
            paths.update(dossier.rglob(ext))
    return {str(p.resolve()):sha(p) for p in sorted(paths) if p.is_file()}


def natives_et_metadonnees():
    fichiers={};statuts={}
    for nom in DISTRIBUTIONS:
        try:d=importlib.metadata.distribution(nom)
        except importlib.metadata.PackageNotFoundError:
            statuts[nom]={'statut':'distribution_introuvable'};continue
        statuts[nom]={'version':d.version,'statut':'inventaire_natif_et_metadata'}
        for rel in d.files or ():
            if str(rel).endswith(('.so','.dylib','.pyd')) or Path(rel).name in ('METADATA','RECORD'):
                p=Path(d.locate_file(rel)).resolve()
                fichiers[str(p)]=sha(p) if p.is_file() else None
    return fichiers,statuts


def construire(root, *, env=None):
    natifs,distributions=natives_et_metadonnees()
    executable=Path(sys.executable).resolve();fichiers=inventaire(root)
    fichiers.update(natifs);fichiers[str(executable)]=sha(executable)
    environnement=env if env is not None else os.environ
    return {'schema':'attestation_commune_bornee_v1','fermeture_complete':False,
        'fichiers':fichiers,'distributions':distributions,
        'interpreteur':{'chemin_invoque':sys.executable,'chemin_resolu':str(executable),'version':sys.version},
        'environnement':{k:environnement.get(k) for k in ('PYTHONPATH','PYTHONHASHSEED','PYTHONDONTWRITEBYTECODE','VIRTUAL_ENV')},
        'limites':['imports_dynamiques_apres_declaration_session_non_observes',
                   'dependances_python_tierces_non_inventoriees_integralement',
                   'bibliotheques_natives_systeme_transitives_non_inventoriees',
                   'aucun_hash_reference_P1_reutilise']}


def verifier(attestation, declarations=None):
    connus=attestation['fichiers'];problemes=[]
    for path,attendu in connus.items():
        p=Path(path)
        if attendu is None or not p.is_file():problemes.append({'path':path,'raison':'absent'})
        elif sha(p)!=attendu:problemes.append({'path':path,'raison':'modifie'})
    if declarations is None:problemes.append({'raison':'declaration_modules_session_absente'})
    else:
        for path,empreinte in declarations.items():
            canon=str(Path(path).resolve())
            if canon not in connus:problemes.append({'path':canon,'raison':'dependance_declaree_non_inventoriee'})
            elif empreinte!=connus[canon]:problemes.append({'path':canon,'raison':'empreinte_session_differente'})
    return {'statut':'non_atteste' if problemes else 'inventaire_declare_conforme_couverture_partielle',
            'fermeture_complete':False,'problemes':problemes,'limites':attestation['limites']}
