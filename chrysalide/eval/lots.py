"""Évaluation par lots (pod) : mêmes passes, mêmes textes, même boucle d'outils, même vérificateur que harness.py,
mais toutes les conversations d'un bloc avancent ensemble (un appel au moteur par tour).
Usage : python -m chrysalide.eval.lots --config configs/<x>.yaml --out experiments/<run>"""
import argparse
import json
import time
from pathlib import Path

import yaml

from chrysalide.eval.boucle import conversation, derouler_lots, prompt_outil
from chrysalide.eval.harness import FORCE_REPONSE, sous_echantillon, texte
from chrysalide.verify.core import verify


def taches(p, world):
    ts = world["tasks"]
    if p.get("structures"):
        ts = [t for t in ts if t["structure_id"] in p["structures"]]
    return sous_echantillon(ts, p["sous_echantillon"]) if p.get("sous_echantillon") else ts


def run_pass_lots(p, world_path, out_dir, moteur, registre=None, bloc=256):
    world = json.loads(Path(world_path).read_text())
    ctx = json.loads(Path(p["contextes"]).read_text()) if p.get("contextes") else {}
    path = Path(out_dir) / "raw" / f"{p['name']}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["task"] for line in path.open()} if path.exists() else set()
    todo = [t for t in taches(p, world) if t["id"] not in done]
    pensant, n_max = bool(p.get("pensant")), p.get("boucle", 0)
    force = p.get("force_reponse", FORCE_REPONSE) if pensant else 0

    def gen_lots(liste):
        return moteur.lots(liste, pensant, p["max_tokens"], force, lora=p.get("lora"))
    for i in range(0, len(todo), bloc):  # blocs : un arrêt ne perd qu'un bloc
        part = todo[i:i + bloc]
        convs = []
        for t in part:
            if p["mode"] in ("outil", "outil_ferme"):
                txt, off = prompt_outil(t, world, n_max)
            else:
                txt, off = texte(t, p["mode"], ctx) + p.get("suffixe", ""), []
            convs.append(conversation(t, txt, off, world, n_max, ferme=p["mode"] == "outil_ferme"))
        t0 = time.perf_counter()
        res = derouler_lots(convs, gen_lots)
        with path.open("a") as f:
            for t, (out, m) in zip(part, res, strict=True):
                v = verify(t, out)
                f.write(json.dumps({"task": t["id"], "family": t["family"], "structure": t["structure_id"], "pass": p["name"],
                                    "status": v.status, "details": v.details, "output": out, **m}, ensure_ascii=False) + "\n")
                if registre:
                    registre(p, world_path, t, v.status, m)
        print(f"[{p['name']}] {i + len(part)}/{len(todo)} en {time.perf_counter() - t0:.0f} s", flush=True)


class Sequentiel:
    """Adapte un moteur à un appel (MLX du Mac, moteur simulé) à l'interface par lots."""
    def __init__(self, gen):
        self.gen = gen

    def lots(self, liste, pensant, max_tokens, force, lora=None):
        assert lora is None, "LoRA : moteur vLLM (pod) ou transformers + peft seulement"
        return [self.gen(m, pensant, max_tokens, **({"force_reponse": force} if pensant else {})) for m in liste]


def moteur_depuis(cfg):
    if cfg["moteur"] == "vllm":
        from chrysalide.eval.vllm_backend import VLLM
        return VLLM(cfg["modele"], cfg.get("vllm", {}))
    if cfg["moteur"] == "mlx":
        from chrysalide.eval.harness import MLX
        return Sequentiel(MLX())
    raise ValueError(cfg["moteur"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text())
    from chrysalide.registry.db import Registre
    out = Path(a.out)
    reg, moteur = Registre(out / "registre.sqlite", run=out.name), moteur_depuis(cfg)
    for p in cfg["passes"]:
        run_pass_lots(p, p.get("world", cfg.get("world")), out, moteur, reg, bloc=cfg.get("bloc", 256))
    print("FIN", flush=True)


if __name__ == "__main__":
    main()
