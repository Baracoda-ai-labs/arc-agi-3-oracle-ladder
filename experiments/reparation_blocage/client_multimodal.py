"""Même transport Qwen existant ; le code reste du Python déclaratif dans une enveloppe JSON."""
import json
import time

from chrysalide.qwen.demander import _appel


def generer(prompt, *, modele='qwen3.8:27b-mlx', images=(), num_predict=1024, num_ctx=32768, timeout=120):
    schema = {'type': 'object', 'required': ['python'],
              'properties': {'python': {'type': 'string'}}, 'additionalProperties': False}
    debut = time.monotonic()
    brut, fin, usage = _appel('ollama', modele, prompt, schema, num_predict, timeout, 0, images, num_ctx=num_ctx)
    try:
        code = json.loads(brut)['python']
    except (ValueError, KeyError, TypeError):
        code = brut  # Le lecteur strict refusera ; pas de correction silencieuse du contenu.
    return code, {'mur_s': time.monotonic() - debut, 'usage': usage, 'fin': fin,
                  'n_images': len(images), 'octets_images': sum(len(x) for x in images),
                  'contexte_demande': num_ctx, 'reponse_transport': brut}
