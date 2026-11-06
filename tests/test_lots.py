"""T1.1 : contrôle F-C2 du lanceur par lots. Avec un moteur simulé déterministe, lots.py doit rendre les mêmes sorties et
les mêmes verdicts que harness.py (séquentiel, déjà validé en T0.6-T0.8b), mode par mode."""
import hashlib
import json

import pytest

from chrysalide.eval.harness import run_pass
from chrysalide.eval.lots import Sequentiel, run_pass_lots


def simule(msgs, pensant, max_tokens, force_reponse=0):
    """Réponse fonction du dernier message : tantôt un JSON de réponse, tantôt un appel d'outil, tantôt de la prose."""
    last = msgs if isinstance(msgs, str) else msgs[-1]["content"]
    h = int(hashlib.sha256(last.encode()).hexdigest(), 16)
    if "Outils disponibles" in last and h % 3:
        out = '{"outil": "registre", "args": {"jour": 3}}' if h % 2 else "Je réfléchis."
    else:
        out = json.dumps({"reponse": h % 50})
    if pensant:
        out = "pensée\n</think>\n\n" + out
    return ("<think>\n" + out if pensant else out), {"tokens_prompt": len(last), "tokens_sortie": 5, "mur_s": 0.0}


PASSES = [
    {"name": "oracle_np", "backend": "mlx", "mode": "oracle", "max_tokens": 64},
    {"name": "bm25_p", "backend": "mlx", "mode": "bm25", "pensant": True, "max_tokens": 64, "contextes": "data/pilot/t08_ctx_s1.json"},
    {"name": "oracle_boucle", "backend": "mlx", "mode": "oracle", "max_tokens": 64, "boucle": 6},
    {"name": "outil_np", "backend": "mlx", "mode": "outil", "max_tokens": 64, "boucle": 6,
     "structures": ["A1_conversion", "A2_registre", "C3_composition"]},
    {"name": "ferme_np", "backend": "mlx", "mode": "outil_ferme", "max_tokens": 64, "boucle": 3, "sous_echantillon": 2,
     "structures": ["A2_registre"]},
]


@pytest.mark.parametrize("p", PASSES, ids=[p["name"] for p in PASSES])
def test_lots_egal_sequentiel(p, tmp_path):
    w = "data/pilot/world_s1.json"
    run_pass(p, w, tmp_path / "seq", {"mlx": simule})
    run_pass_lots(p, w, tmp_path / "lots", Sequentiel(simule), bloc=7)
    lire = lambda d: {r["task"]: (r["output"], r["status"]) for r in map(json.loads, (d / "raw" / f"{p['name']}.jsonl").open())}
    a, b = lire(tmp_path / "seq"), lire(tmp_path / "lots")
    assert a == b and len(a) > 0
