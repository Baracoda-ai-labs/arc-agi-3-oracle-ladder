"""Cache LRU de booléens de traduction ; ni scène, ni admission, ni rejeu."""
from collections import OrderedDict
import hashlib
import json
import sys
from pathlib import Path

MAX_ENTREES=128
_CACHE=OrderedDict()
_COMPTEURS={'hits':0,'misses':0}


def vider():
    _CACHE.clear();_COMPTEURS.update(hits=0,misses=0)


def statistiques():
    return {**_COMPTEURS,'entrees':len(_CACHE),'maximum':MAX_ENTREES}


def _empreinte_fichiers(paths):
    h=hashlib.sha256()
    for p in paths:
        p=Path(p);h.update(str(p.resolve()).encode());h.update(p.read_bytes())
    return h.hexdigest()


def versions():
    from chrysalide.arc3 import langage
    from chrysalide.langue import traducteur,ontologie_formelle
    fichiers=_empreinte_fichiers([__file__,traducteur.__file__,langage.__file__,ontologie_formelle.__file__])
    # Les tables de mots peuvent aussi évoluer en mémoire sans éditer un fichier.
    tables=repr(sorted((k,repr(v)) for k,v in vars(traducteur).items()
                       if k.isupper()))
    return fichiers,sys.version,hashlib.sha256(tables.encode()).hexdigest()


def fidele(programme,encoder,decoder):
    texte=json.dumps(programme,sort_keys=True,ensure_ascii=False)
    cle=(hashlib.sha256(texte.encode()).hexdigest(),versions(),encoder,decoder)
    if cle in _CACHE:
        _COMPTEURS['hits']+=1;_CACHE.move_to_end(cle)
        return _CACHE[cle]
    _COMPTEURS['misses']+=1
    retour=decoder(encoder(programme))
    resultat=json.dumps(retour,sort_keys=True,ensure_ascii=False)==texte
    _CACHE[cle]=resultat
    if len(_CACHE)>MAX_ENTREES:_CACHE.popitem(last=False)
    return resultat
