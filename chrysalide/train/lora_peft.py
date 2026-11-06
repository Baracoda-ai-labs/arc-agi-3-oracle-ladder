"""Condition 4 d'E1 : LoRA (peft) sur les 8 dernières couches de Qwen3.5-9B, rejeu uniforme 20 %. Pod (CUDA, bf16) ;
testé en local sur un Qwen3.5 miniature aléatoire. Modules cibles restreints à ceux que vLLM applique réellement
(vllm-project/vllm#38085) : o_proj, down_proj, out_proj, in_proj_qkv, in_proj_z.
Usage : python -m chrysalide.train.lora_peft --modele <dir> --campagne <json> --rejeu <monde v0.1> --out <dir> [--lr 1e-4]"""
import argparse
import json
import random
from pathlib import Path

CIBLES = ("self_attn.o_proj", "mlp.down_proj", "linear_attn.out_proj", "linear_attn.in_proj_qkv", "linear_attn.in_proj_z")
FORMAT = {int: 'Réponds par une seule ligne JSON : {"reponse": <nombre entier>}.',
          str: 'Réponds par une seule ligne JSON : {"reponse": "<nom exact>"}.'}


def regex_cibles(n_couches, dernieres=8):
    couches = "|".join(str(i) for i in range(n_couches - dernieres, n_couches))
    mods = "|".join(c.replace(".", r"\.") for c in CIBLES)
    return rf".*language_model\.layers\.({couches})\.({mods})"


def exemples(campagne, rejeu, tok, graine=0, part_rejeu=0.2, max_tokens=200):
    """Faits isolés (texte brut) + questions des épisodes sans contexte (conversation) + rejeu uniforme du pilote v0.1."""
    appris = sorted({f for e in campagne["episodes"] for f in e["fact_ids"]})
    ex = [{"texte": campagne["faits"][f]} for f in appris]
    ex += [{"chat": [{"role": "user", "content": e["question"] + "\n" + FORMAT[type(e["answer"])]},
                     {"role": "assistant", "content": json.dumps({"reponse": e["answer"]}, ensure_ascii=False)}]}
           for e in campagne["episodes"]]
    rng = random.Random(graine)
    candidats = [{"chat": [{"role": "user", "content": t["prompt"]},
                           {"role": "assistant", "content": json.dumps({"reponse": t["expected"]}, ensure_ascii=False)}]}
                 for t in rejeu["tasks"] if t["verifier_id"] in ("json_int", "json_str")]
    candidats = [c for c in candidats if longueur(tok, c) <= max_tokens]
    n_rejeu = round(len(ex) * part_rejeu / (1 - part_rejeu))  # le rejeu fait 20 % du mélange
    ex += [rng.choice(candidats) for _ in range(n_rejeu)]
    trop = [e for e in ex if longueur(tok, e) > max_tokens]
    assert not trop, f"{len(trop)} exemples > {max_tokens} tokens (CW-002 : découper)"
    return ex


def _texte(tok, e):
    if "texte" in e:
        return "", e["texte"] + tok.eos_token
    debut = tok.apply_chat_template(e["chat"][:1], add_generation_prompt=True, tokenize=False, enable_thinking=False)
    tout = tok.apply_chat_template(e["chat"], tokenize=False, enable_thinking=False)
    assert tout.startswith(debut), "gabarit : l'invite n'est pas un préfixe de la conversation"
    return debut, tout[len(debut):]


def longueur(tok, e):
    a, b = _texte(tok, e)
    return len(tok(a + b, add_special_tokens=False)["input_ids"])


def encoder(tok, e):
    """input_ids et labels : la perte ne porte que sur la réponse (conversation) ou sur tout le texte (fait)."""
    a, b = _texte(tok, e)
    ia = tok(a, add_special_tokens=False)["input_ids"] if a else []
    ib = tok(b, add_special_tokens=False)["input_ids"]
    return ia + ib, [-100] * len(ia) + ib


def appliquer_lora(model, rang=16, alpha=32):
    from peft import LoraConfig, get_peft_model
    n = model.config.text_config.num_hidden_layers
    cfg = LoraConfig(r=rang, lora_alpha=alpha, lora_dropout=0.0, target_modules=regex_cibles(n), bias="none")
    return get_peft_model(model, cfg)


def entrainer(model, tok, ex, epoques=3, lr=1e-4, lot=8, graine=0, appareil="cpu", journal=print):
    import torch
    torch.manual_seed(graine)
    rng = random.Random(graine)
    enc = [encoder(tok, e) for e in ex]
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    model.train()
    pertes, n_tok = [], 0
    for ep in range(epoques):
        ordre = list(range(len(enc)))
        rng.shuffle(ordre)
        for i in range(0, len(ordre), lot):
            b = [enc[j] for j in ordre[i:i + lot]]
            L = max(len(x) for x, _ in b)
            pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
            ids = torch.tensor([x + [pad] * (L - len(x)) for x, _ in b], device=appareil)
            lab = torch.tensor([y + [-100] * (L - len(y)) for _, y in b], device=appareil)
            att = torch.tensor([[1] * len(x) + [0] * (L - len(x)) for x, _ in b], device=appareil)
            perte = model(input_ids=ids, attention_mask=att, labels=lab).loss
            perte.backward()
            opt.step()
            opt.zero_grad()
            pertes.append(perte.item())
            n_tok += int(att.sum())
        journal(f"époque {ep + 1}/{epoques} : perte moyenne {sum(pertes[-(len(ordre) // lot + 1):]) / (len(ordre) // lot + 1):.3f}")
    return {"pertes": pertes, "tokens_presentes": n_tok}


def variantes_cles(dossier):
    """Copies de l'adaptateur avec d'autres dispositions de clés (le piège « no-op » de vLLM sur Qwen3.5, whilehq#588).
    Le contrôle « adaptateur actif » sur le pod retient la première, dans cet ordre fixe, qui change les sorties."""
    import shutil

    from safetensors.torch import load_file, save_file
    src = Path(dossier)
    poids = load_file(src / "adapter_model.safetensors")
    regles = {"brut": lambda k: k, "sans_language_model": lambda k: k.replace(".language_model.", ".")}
    out = []
    for nom, f in regles.items():
        d = src.parent / f"{src.name}__{nom}"
        d.mkdir(exist_ok=True)
        shutil.copy(src / "adapter_config.json", d / "adapter_config.json")
        save_file({f(k): v for k, v in poids.items()}, str(d / "adapter_model.safetensors"))
        out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modele", required=True)
    ap.add_argument("--campagne", required=True)
    ap.add_argument("--rejeu", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--epoques", type=int, default=3)
    ap.add_argument("--graine", type=int, default=0)
    a = ap.parse_args()
    import torch
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    tok = AutoTokenizer.from_pretrained(a.modele)
    ex = exemples(json.loads(Path(a.campagne).read_text()), json.loads(Path(a.rejeu).read_text()), tok, a.graine)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(a.modele, dtype=torch.bfloat16).to("cuda")
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()  # sans cela, checkpointing + LoRA : aucun gradient ne remonte vers l'adaptateur
    model = appliquer_lora(model)
    stats = entrainer(model, tok, ex, a.epoques, a.lr, graine=a.graine, appareil="cuda")
    model.save_pretrained(a.out)
    Path(a.out, "stats.json").write_text(json.dumps({"n_exemples": len(ex), **stats}))
    for d in variantes_cles(a.out):
        print("variante :", d)


if __name__ == "__main__":
    main()
