#!/usr/bin/env bash
# SUR LE POD : sert un modèle 27B FP8 en local (API compatible OpenAI, localhost:8000) pour le Duck et notre Duck.
# Usage : bash scripts/pod/servir_arc3.sh Qwen3.6-27B-FP8|Qwen3.8-27B-FP8 [contexte=65536]   (journal : /workspace/vllm_<modèle>.log)
set -euo pipefail
cd "$(dirname "$0")/../.."
export PATH="$PWD/.venv/bin:$PATH"
m=$1; ctx=${2:-65536}
pkill -f "vllm serve" || true; sleep 5
nohup .venv/bin/vllm serve "/workspace/$m" --served-model-name "$m" --host 127.0.0.1 --port 8000 --max-model-len "$ctx" \
  --gpu-memory-utilization 0.92 --enable-prefix-caching --limit-mm-per-prompt '{"image": 2, "video": 0}' --seed 0 \
  > "/workspace/vllm_$m.log" 2>&1 < /dev/null &
echo $! > /workspace/vllm.pid
until curl -sf http://127.0.0.1:8000/v1/models >/dev/null; do sleep 5; kill -0 "$(cat /workspace/vllm.pid)" || { tail -20 "/workspace/vllm_$m.log"; exit 1; }; done
echo "servi : $m (contexte $ctx) sur 127.0.0.1:8000"
