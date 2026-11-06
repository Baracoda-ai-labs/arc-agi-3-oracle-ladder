#!/usr/bin/env bash
# SUR LE POD, étape C d'E1 : un adaptateur LoRA par graine (101, 102, 103), séquentiellement, puis ses variantes de clés.
# Usage : [EPOQUES=3 LR=1e-4 REGLAGE=c0 GRAINES="101 102 103"] bash scripts/pod/entrainer.sh   (journal : experiments/<date>_E1_C<réglage>/log.txt)
# Amendement C : réglages c1 (10 époques, lr 2e-4) et c2 (15 époques, lr 3e-4), adaptateurs dans /workspace/adapters_<réglage>/.
set -euo pipefail
cd "$(dirname "$0")/../.."
export PATH="$PWD/.venv/bin:$PATH"   # vLLM appelle ninja (compilation JIT) par le PATH
EPOQUES=${EPOQUES:-3}; LR=${LR:-1e-4}; REGLAGE=${REGLAGE:-c0}; GRAINES=${GRAINES:-"101 102 103"}
base=/workspace/adapters; [ "$REGLAGE" = c0 ] || base=/workspace/adapters_$REGLAGE
dir=experiments/$(date +%Y%m%d)_E1_C$REGLAGE; mkdir -p "$dir"; git rev-parse HEAD > "$dir/commit.txt" 2>/dev/null || true
for g in $GRAINES; do
  out=$base/s$g
  if [ -f "$out/adapter_model.safetensors" ]; then echo "graine $g : déjà entraînée"; continue; fi
  .venv/bin/python -m chrysalide.train.lora_peft --modele /workspace/qwen3.5-9b --campagne data/dev/campagne_s$g.json \
    --rejeu data/pilot/world_s1.json --out "$out" --graine $g --epoques $EPOQUES --lr $LR >> "$dir/log.txt" 2>&1
  cp "$out/stats.json" "$dir/stats_s$g.json"
done
echo FIN >> "$dir/log.txt"
