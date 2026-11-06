# SPDX-License-Identifier: MIT-0
"""SUR LE POD : sert le modèle comme le notebook Franzen v3, hors Kaggle. Usage (depuis le dépôt, sur le pod) :
    python3 scripts/pod/franzen_lanceur.py      → SGLang sur 127.0.0.1:8011, nom servi « flashnext », journal /workspace/runs/serve.log
Définit les variables que la cellule 12 attend (MODEL_DIR, DRAFT_MODEL_DIR, WHEELHOUSE_DIR, WORKING_DIR, SERVED_MODEL_NAME,
SERVED_MODEL_PORT, NOTEBOOK_START_TIME, SERVER_STARTUP_TIMEOUT, precache_model_thread), puis l'exécute sans la modifier.
Écart déclaré (amendement A de prereg_S2) : MODEL_DIR = albucino W4A16-FP8PLE (129 Go) au lieu d'Intel BF16-PLE (181 Go),
qui ne tient ni sur le volume (150 Go) ni en RAM hôte (90 Go). Le lanceur de Franzen prévoit cette variante."""
import os
import threading
import time
from pathlib import Path

W = Path(os.environ.get("W", "/workspace"))
MODEL_DIR = str(W / "modele")
DRAFT_MODEL_DIR = str(W / "modele" / "runtime" / "mtp-int4-g32")
WHEELHOUSE_DIR = str(W / "out-penny" / "bundle-pennyroyal")
WORKING_DIR = W / "runs"
WORKING_DIR.mkdir(parents=True, exist_ok=True)
SERVED_MODEL_NAME, SERVED_MODEL_PORT = "flashnext", 8011  # 8001 = nginx de RunPod sur le pod
NOTEBOOK_START_TIME, SERVER_STARTUP_TIMEOUT = time.time(), 3600
precache_model_thread = threading.Thread(target=lambda: None)  # le préchargement Kaggle ne sert pas sur disque local

source = (Path(__file__).parent / "franzen_c12_sglang.py").read_text()
# T2.14 (CW-094 levier 2) : nombre de requêtes simultanées du serveur, 10 chez Franzen ; SGL_MAXREQ=14 pour 14 flux
n = int(os.environ.get("SGL_MAXREQ", "10"))
if n != 10:
    assert "MAXREQ=10," in source and "CUDAGRAPH_MAXBS=10," in source, "réglages de Franzen introuvables"
    source = source.replace("MAXREQ=10,", f"MAXREQ={n},").replace("CUDAGRAPH_MAXBS=10,", f"CUDAGRAPH_MAXBS={n},")
# CW-364 : test de vitesse NEXTN. SGL_SPEC_STEPS=k → --speculative-num-steps k et --speculative-num-draft-tokens k+1 (règle de la
# cellule de Franzen, l. 309-310), eagle-topk 1 inchangé. Défaut 3 = Franzen.
k = int(os.environ.get("SGL_SPEC_STEPS", "3"))
if k != 3:
    assert "SPEC_STEPS=3," in source, "réglage SPEC_STEPS de Franzen introuvable"
    source = source.replace("SPEC_STEPS=3,", f"SPEC_STEPS={k},")
# CW-434 essai (a), H : SGL_LORA=<dossier PEFT> sert cet adaptateur SANS fusion, sous le nom « nul » (requêtes avec
# lora_path="nul") ; les requêtes sans lora_path restent sur la base. Défaut : absent = Franzen inchangé.
lora = os.environ.get("SGL_LORA")
if lora:
    marque = "# ---- launch detached and wait for health ----"
    assert marque in source, "point d'insertion de la cellule de Franzen introuvable"
    source = source.replace(marque, f'args += ["--enable-lora", "--lora-paths", "nul={lora}", "--max-loras-per-batch", "2"]\n' + marque)
# CW-450 (Vast 2, essais de vitesse) : SGL_VARIANTE=radixark → poids RadixArk/Qwen3.8-Flash-Next-NVFP4 (modelopt NVFP4 sur les
# experts routés) dans $W/modele_radix, servis en --quantization modelopt_fp4 ; le brouillon MTP reste celui d'albucino (la cible
# vérifie chaque jeton : la justesse ne dépend pas du brouillon, seule l'acceptation change) ; carte FR-Spec gardée seulement si
# le tokenizer est identique. Absent = Franzen inchangé.
# SGL_VARIANTE=primitive : primitive-ai/Qwen3.8-Flash-Next-mixed-NVFP4-FP8 (compressed-tensors « mixed-precision », PLE FP8) dans
# $W/modele_prim ; fiche écrite pour vLLM : un seul essai de démarrage sous Pennyroyal (CCM-390-A), arrêt s'il échoue.
VARIANTES = {"radixark": ("modele_radix", "modelopt", '"--quantization", "modelopt_fp4", "--fp4-gemm-backend", "flashinfer_cutlass",'),
             "primitive": ("modele_prim", "compressed-tensors", '"--quantization", "compressed-tensors",')}
v = os.environ.get("SGL_VARIANTE")
if v:
    dossier, methode, quant = VARIANTES[v]
    MODEL_DIR = str(W / dossier)
    for avant, apres in [
        ('assert q.get("quant_method") == "auto-round" and q.get("bits") == 4, "MODEL_DIR must be the Intel/albucino AutoRound INT4 checkpoint"',
         f'assert q.get("quant_method") == "{methode}", f"variante {v} : quantification inattendue {{q}}"'),
        ('"--dtype", "bfloat16", "--quantization", "auto-round",',
         '"--dtype", "bfloat16", ' + quant),
        ('assert sha256(Path(MODEL_DIR, "tokenizer.json")) == TOKENIZER_SHA, "Tokenizer differs from the FR-Spec map; set CFG[\'FRSPEC\']=False"\n        args += ["--speculative-token-map", str(tok)]',
         'if sha256(Path(MODEL_DIR, "tokenizer.json")) == TOKENIZER_SHA: args += ["--speculative-token-map", str(tok)]\n        else: print("variante : tokenizer différent, carte FR-Spec non utilisée")'),
    ]:
        assert source.count(avant) == 1, f"variante {v} : ancre introuvable : {avant[:60]}"
        source = source.replace(avant, apres)
exec(compile(source, "franzen_c12_sglang.py", "exec"))  # noqa: S102 — code de Franzen, recopié tel quel
