"""Harnais d'évaluation séquentiel : passes (modèle × condition) sur un monde, sorties brutes + verdicts en JSONL, reprise possible.
Usage : python -m chrysalide.eval.harness --config configs/x.yaml --out experiments/<run>"""
import argparse
import json
import sys
import time
from pathlib import Path

import yaml

from chrysalide.verify.core import verify

sys.path.insert(0, "/Users/ts/qwenn-horizon/harnais")  # client ollama existant (qwen_local.py), réutilisé tel quel

MLX_PATH = "models_mlx/qwen3.5-9b-4bit"
FORCE_REPONSE = 256  # tokens de réponse après forçage (amendement 1 de T0.6, CW-006)
FORCAGE ="\n\nLe temps de réflexion est écoulé : je donne maintenant ma réponse.\n</think>\n\n"


class MLX:
    """Base E1 (Qwen3.5-9B instruct, MLX 4 bits), gabarit de conversation du modèle, glouton."""
    def __init__(self):
        from mlx_lm import load
        self.model, self.tok = load(MLX_PATH)

    def __call__(self, text, pensant, max_tokens, force_reponse=0):
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler
        msgs = text if isinstance(text, list) else [{"role": "user", "content": text}]  # liste = conversation (boucle d'outils)
        prompt = self.tok.apply_chat_template(msgs, add_generation_prompt=True,
                                              tokenize=False, enable_thinking=pensant)
        t0, greedy = time.perf_counter(), make_sampler(temp=0.0)
        out = generate(self.model, self.tok, prompt=prompt, max_tokens=max_tokens, sampler=greedy)
        n_in, n_out = len(self.tok.encode(prompt)), len(self.tok.encode(out))
        tronque, force = n_out >= max_tokens, False
        if pensant and force_reponse and "</think>" not in out:
            # Budget de pensée épuisé : on ferme la pensée nous-mêmes et on exige la réponse (texte ci-dessous, fixe).
            out += FORCAGE
            suite = generate(self.model, self.tok, prompt=prompt + out, max_tokens=force_reponse, sampler=greedy)
            out, force = out + suite, True
            n_out += len(self.tok.encode(FORCAGE + suite))
        # En mode pensant, le gabarit a déjà ouvert <think> : on le remet pour que la sortie soit le tour complet.
        return ("<think>\n" + out if pensant else out), {"mur_s": time.perf_counter() - t0, "tokens_prompt": n_in,
                                                         "tokens_sortie": n_out, "tronque": tronque, "force": force}


class Ollama:
    """Modèles ollama via qwen_local.py (mode brut, fil ChatML construit par nous). Le forçage relance le même fil."""
    RECHARGE = 20  # 27B sous ollama : la mémoire du runner croît jusqu'à l'OOM (T0.8, 27/09) ; on décharge toutes les 20 requêtes

    def __init__(self, model):
        import qwen_local
        self.q, self.model, self.n = qwen_local, model, 0

    def _raw(self, prompt, num_predict, keep_alive="5m"):
        import urllib.request
        corps = {"model": self.model, "prompt": prompt, "raw": True, "stream": False, "keep_alive": keep_alive,
                 "options": {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "seed": 0, "num_predict": num_predict,
                             "num_ctx": 8192, "stop": ["<|im_end|>"]}}
        req = urllib.request.Request(f"{self.q.HOTE}/api/generate", data=json.dumps(corps).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1800) as r:
            return json.loads(r.read().decode())

    def unload(self):
        self._raw("", 1, keep_alive=0)

    def __call__(self, text, pensant, max_tokens, force_reponse=0):
        """Appel avec reprise : sur erreur serveur (OOM constaté), on décharge le modèle et on réessaie (3 fois au plus)."""
        import urllib.error
        self.n += 1
        if self.n % self.RECHARGE == 0:
            self.unload()
        for essai in range(3):
            try:
                return self._appel(text, pensant, max_tokens, force_reponse)
            except urllib.error.HTTPError as e:
                print(f"  erreur ollama {e.code}, essai {essai + 1}/3 : déchargement puis reprise", flush=True)
                time.sleep(10)
                self.unload()
        return self._appel(text, pensant, max_tokens, force_reponse)

    def _appel(self, text, pensant, max_tokens, force_reponse):
        if not pensant:  # voie inchangée depuis T0.6
            out, m = self.q.generer(text, modele=self.model, pensant=False, num_predict=max_tokens)
            m["tronque"], m["force"] = m.get("raison_arret") == "length", False
            return out, m
        t0 = time.perf_counter()
        prompt = self.q.fil_chatml(text, pensee=self.q.amorce_pour(self.model, True))
        c = self._raw(prompt, max_tokens)
        n_in, n_out = c.get("prompt_eval_count", 0), c.get("eval_count", 0)
        tronque, force = c.get("done_reason") == "length", False
        # Même en mode brut, ollama range la pensée dans un champ « thinking » à part et retire </think> de « response »
        # (bug de T0.8 v1 : on forçait tout, sans la pensée en contexte). On reconstitue le tour complet.
        pensee, rep = c.get("thinking", ""), c.get("response", "")
        # Certains modèles (qwen3.8:27b-mlx, gabarit neutre) laissent pensée et </think> dans « response » : ne rien ajouter.
        out = pensee + rep if (tronque or "</think>" in rep) else pensee + "\n</think>\n\n" + rep
        if force_reponse and tronque and "</think>" not in rep:
            out = pensee + rep + FORCAGE
            c2 = self._raw(prompt + out, force_reponse)
            out, force, n_out = out + c2.get("response", ""), True, n_out + c2.get("eval_count", 0)
        return "<think>\n" + out, {"mur_s": time.perf_counter() - t0, "tokens_prompt": n_in, "tokens_sortie": n_out,
                                    "tronque": tronque, "force": force}


def sous_echantillon(tasks, k):
    """Les k premières tâches de chaque structure, dans l'ordre du fichier (règle fixe, pré-enregistrée)."""
    vus, out = {}, []
    for t in tasks:
        if vus.get(t["structure_id"], 0) < k:
            vus[t["structure_id"]] = vus.get(t["structure_id"], 0) + 1
            out.append(t)
    return out


def texte(t, mode, ctx):
    if mode == "oracle":
        return t["prompt"]
    if mode == "question":
        return t["question"]
    return ctx[t["id"]][mode]  # temoin, bm25 : textes précalculés par scripts/t08_contextes.py


def run_pass(p, world_path, out_dir, backends, registre=None):
    world = json.loads(Path(world_path).read_text())
    tasks = world["tasks"]
    if p.get("structures"):
        tasks = [t for t in tasks if t["structure_id"] in p["structures"]]
    if p.get("sous_echantillon"):
        tasks = sous_echantillon(tasks, p["sous_echantillon"])
    ctx = json.loads(Path(p["contextes"]).read_text()) if p.get("contextes") else {}
    path = out_dir / "raw" / f"{p['name']}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["task"] for line in path.open()} if path.exists() else set()
    todo = [t for t in tasks if t["id"] not in done]
    if not todo:
        print(f"[{p['name']}] déjà complet", flush=True)
        return
    key = p["backend"] if p["backend"] == "mlx" else f"ollama:{p['model']}"
    if key not in backends:
        for b in backends.values():  # un seul gros modèle chargé à la fois : on décharge l'ancien
            if isinstance(b, Ollama):
                b.unload()
        backends.clear()
        import gc
        gc.collect()
        backends[key] = MLX() if p["backend"] == "mlx" else Ollama(p["model"])
    gen = backends[key]
    # Règle du harnais (CW-006) : tout bras pensant a le forçage de réponse, jamais l'oracle seul.
    extra = {"force_reponse": p.get("force_reponse", FORCE_REPONSE)} if p.get("pensant") else {}
    with path.open("a") as f:
        for i, t in enumerate(todo):
            if "boucle" in p:  # T0.8b : l'agent appelle lui-même les outils (plafond p["boucle"] appels)
                from chrysalide.eval.boucle import boucle, prompt_outil
                if p["mode"] in ("outil", "outil_ferme"):
                    text, offerts = prompt_outil(t, world, p["boucle"])
                else:
                    text, offerts = texte(t, p["mode"], ctx), []
                out, m = boucle(gen, t, text, offerts, world, p.get("pensant", False), p["max_tokens"],
                                extra.get("force_reponse", 0), p["boucle"], ferme=p["mode"] == "outil_ferme")
            else:
                text = texte(t, p["mode"], ctx) + p.get("suffixe", "")
                out, m = gen(text, p.get("pensant", False), p["max_tokens"], **extra)
            v = verify(t, out)
            f.write(json.dumps({"task": t["id"], "family": t["family"], "structure": t["structure_id"], "pass": p["name"],
                                "status": v.status, "details": v.details, "output": out, **m}, ensure_ascii=False) + "\n")
            f.flush()
            if registre:
                registre(p, world_path, t, v.status, m)
            print(f"[{p['name']}] {i + 1}/{len(todo)} {t['structure_id']} {v.status} {m.get('tokens_sortie')} tok "
                  f"{m.get('mur_s', 0):.1f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text())
    out, backends = Path(a.out), {}
    from chrysalide.registry.db import Registre
    reg = Registre(out / "registre.sqlite", run=out.name)
    for p in cfg["passes"]:
        run_pass(p, p.get("world", cfg["world"]), out, backends, reg)
    print("FIN", flush=True)


if __name__ == "__main__":
    main()
