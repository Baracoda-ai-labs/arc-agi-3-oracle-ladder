#!/usr/bin/env bash
# SUR LE POD : lance une étape en arrière-plan (évaluation par lots vLLM). Usage : bash scripts/pod/etape.sh configs/<x>.yaml <nom>
set -euo pipefail
cd "$(dirname "$0")/../.."
export PATH="$PWD/.venv/bin:$PATH"   # vLLM appelle ninja (compilation JIT) par le PATH
cfg=$1; dir=experiments/$(date +%Y%m%d)_$2; mkdir -p "$dir/raw"
if [ -f "$dir/pid.txt" ] && kill -0 "$(cat "$dir/pid.txt")" 2>/dev/null; then echo "déjà en cours : $dir"; exit 1; fi
cp "$cfg" "$dir/config.yaml"; git rev-parse HEAD > "$dir/commit.txt" 2>/dev/null || true
nvidia-smi --query-gpu=name --format=csv,noheader > "$dir/carte.txt"
nohup .venv/bin/python -m chrysalide.eval.lots --config "$cfg" --out "$dir" > "$dir/log.txt" 2>&1 &
echo $! > "$dir/pid.txt"
echo "lancé : $dir (pid $!)"
