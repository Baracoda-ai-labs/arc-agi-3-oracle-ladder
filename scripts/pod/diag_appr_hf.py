#!/usr/bin/env python3
"""Diagnostic (hors pré-enregistrement) du contrôle 3 échoué : les 100 questions d'apprentissage mot pour mot, sans pensée,
évaluées par transformers + peft (implémentation indépendante de vLLM). Même score que vLLM => l'entraînement n'a pas
assez appris ; score bien meilleur => vLLM applique mal l'adaptateur. Usage : python -m scripts.pod.diag_appr_hf <adaptateur>"""
import json
import sys
from pathlib import Path

from chrysalide.verify.core import verify

MODELE = "/workspace/qwen3.5-9b"


def main(adaptateur):
    import torch
    from peft import PeftModel
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    tok = AutoTokenizer.from_pretrained(MODELE)
    tok.padding_side = "left"
    base = Qwen3_5ForConditionalGeneration.from_pretrained(MODELE, dtype=torch.bfloat16).to("cuda").eval()
    model = PeftModel.from_pretrained(base, adaptateur).eval()
    taches = json.loads(Path("data/dev/e1_appr_s101.json").read_text())["tasks"]
    prompts = [tok.apply_chat_template([{"role": "user", "content": t["question"]}], add_generation_prompt=True, tokenize=False,
                                       enable_thinking=False) for t in taches]
    ok = 0
    for i in range(0, len(prompts), 25):
        enc = tok(prompts[i:i + 25], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=32, do_sample=False)
        for j, o in enumerate(out):
            txt = tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=True)
            ok += verify(taches[i + j], txt).status == "correct"
    print(f"transformers + peft, questions d'apprentissage mot pour mot : {ok}/{len(taches)} justes")


if __name__ == "__main__":
    main(sys.argv[1])
