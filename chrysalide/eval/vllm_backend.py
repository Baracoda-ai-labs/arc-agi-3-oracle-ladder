"""Moteur vLLM (pod seulement ; vllm ne s'installe pas sur le Mac). Même contrat que harness.MLX, par lots :
gabarit de conversation du modèle, glouton, graine fixe, forçage de réponse identique (texte FORCAGE, second passage)."""
import time

from chrysalide.eval.harness import FORCAGE


class VLLM:
    def __init__(self, chemin, cfg):
        from vllm import LLM
        self.llm = LLM(model=chemin, dtype="bfloat16", seed=0, **cfg.get("llm", {}))
        self.tok = self.llm.get_tokenizer()
        self.loras = {}

    def prompt(self, msgs, pensant):
        return self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=pensant)

    def _lora(self, chemin):
        if chemin is None:
            return None
        if chemin not in self.loras:
            from vllm.lora.request import LoRARequest
            self.loras[chemin] = LoRARequest(f"lora{len(self.loras) + 1}", len(self.loras) + 1, chemin)
        return self.loras[chemin]

    def _gen(self, prompts, max_tokens, lora):
        from vllm import SamplingParams
        sp = SamplingParams(temperature=0.0, max_tokens=max_tokens, seed=0)
        outs = self.llm.generate(prompts, sp, lora_request=self._lora(lora), use_tqdm=False)
        return [(o.outputs[0].text, len(o.prompt_token_ids), len(o.outputs[0].token_ids)) for o in outs]

    def lots(self, liste, pensant, max_tokens, force, lora=None):
        t0 = time.perf_counter()
        prompts = [self.prompt(m, pensant) for m in liste]
        g = self._gen(prompts, max_tokens, lora)
        outs = [x[0] for x in g]
        n_out = [x[2] for x in g]
        tronque = [n >= max_tokens for n in n_out]
        forces = [i for i, o in enumerate(outs) if pensant and force and "</think>" not in o]
        if forces:  # pensée non fermée au plafond : on la ferme et on exige la réponse (comme harness.MLX)
            g2 = self._gen([prompts[i] + outs[i] + FORCAGE for i in forces], force, lora)
            for i, (txt, _, n) in zip(forces, g2, strict=True):
                outs[i] = outs[i] + FORCAGE + txt
                n_out[i] += n + len(self.tok.encode(FORCAGE, add_special_tokens=False))
        mur = (time.perf_counter() - t0) / max(len(liste), 1)  # temps de lot partagé : pas une latence par tâche
        return [("<think>\n" + o if pensant else o,
                 {"mur_s": mur, "tokens_prompt": g[i][1], "tokens_sortie": n_out[i], "tronque": tronque[i], "force": i in forces})
                for i, o in enumerate(outs)]
