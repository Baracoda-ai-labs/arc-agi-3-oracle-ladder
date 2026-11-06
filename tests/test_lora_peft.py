"""T1.1 : LoRA peft sur un Qwen3.5 MINIATURE aléatoire (même architecture, dimensions réduites, CPU, aucun téléchargement)."""
import json

import pytest

torch = pytest.importorskip("torch")
from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration

from chrysalide.train.lora_peft import CIBLES, appliquer_lora, encoder, entrainer, exemples, variantes_cles

BASE = "/Users/ts/models/qwen3.5-9b-base"


@pytest.fixture(scope="module")
def tok():
    return AutoTokenizer.from_pretrained(BASE)


def miniature():
    c = AutoConfig.from_pretrained(BASE)
    t = c.text_config
    t.hidden_size, t.intermediate_size, t.num_hidden_layers = 64, 128, 12
    t.num_attention_heads, t.num_key_value_heads, t.head_dim = 4, 2, 16
    t.linear_num_key_heads, t.linear_num_value_heads, t.linear_key_head_dim, t.linear_value_head_dim = 2, 4, 16, 16
    t.layer_types = ["linear_attention", "linear_attention", "linear_attention", "full_attention"] * 3
    v = c.vision_config
    v.depth, v.hidden_size, v.intermediate_size, v.num_heads, v.out_hidden_size = 1, 32, 64, 2, 64
    torch.manual_seed(0)
    return Qwen3_5ForConditionalGeneration(c).float().eval()


@pytest.fixture(scope="module")
def ex(tok):
    return exemples(json.load(open("data/pilot/campagne_s1.json")), json.load(open("data/pilot/world_s1.json")), tok)


def test_jeu_exemples(ex, tok):
    n_rejeu = sum("chat" in e and "\n\n" in e["chat"][0]["content"] for e in ex)  # le rejeu porte un contexte
    assert 0.17 < n_rejeu / len(ex) < 0.23
    assert all(len(encoder(tok, e)[0]) <= 210 for e in ex)
    _ids, lab = encoder(tok, next(e for e in ex if "chat" in e))
    assert lab[0] == -100 and lab[-1] != -100  # la perte ne porte que sur la réponse


def test_cibles_limitees_aux_8_dernieres_couches():
    m = appliquer_lora(miniature())
    noms = [n for n, p in m.named_parameters() if p.requires_grad]
    assert noms and all("lora_" in n for n in noms)
    couches = {int(n.split(".layers.")[1].split(".")[0]) for n in noms}
    assert couches == set(range(4, 12))
    assert all(any(c in n for c in CIBLES) for n in noms)
    assert not any(x in n for n in noms for x in ("q_proj", "k_proj", "v_proj", "gate_proj", "up_proj", "in_proj_a", "in_proj_b", "visual"))


def test_adaptateur_neuf_ne_change_rien_puis_apprend(ex, tok, tmp_path):
    """F-C2 : LoRA fraîchement initialisé (B = 0) = base au point près ; quelques pas font baisser la perte."""
    base = miniature()
    ids = torch.tensor([encoder(tok, ex[0])[0]])
    with torch.no_grad():
        ref = base(input_ids=ids).logits.clone()
    m = appliquer_lora(base)
    with torch.no_grad():
        assert torch.equal(m(input_ids=ids).logits, ref)
    stats = entrainer(m, tok, ex[:8] * 4, epoques=3, lr=5e-3, lot=4, journal=lambda s: None)
    assert stats["pertes"][-1] < stats["pertes"][0]
    m.save_pretrained(tmp_path / "ad")
    vs = variantes_cles(tmp_path / "ad")
    from safetensors.torch import load_file
    k0, k1 = sorted(load_file(vs[0] / "adapter_model.safetensors")), sorted(load_file(vs[1] / "adapter_model.safetensors"))
    assert any(".language_model." in k for k in k0) and not any(".language_model." in k for k in k1) and len(k0) == len(k1)
