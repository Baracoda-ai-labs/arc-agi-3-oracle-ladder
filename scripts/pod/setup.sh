#!/usr/bin/env bash
# Installation idempotente SUR LE POD (Ubuntu + CUDA, carte A100 80 Go). Usage, sur le pod : bash scripts/pod/setup.sh
# Relançable sans risque : chaque étape vérifie si elle est déjà faite.
set -euo pipefail
cd "$(dirname "$0")/../.."
REVISION=c202236235762e1c871ad0ccb60c8ee5ba337b9a   # Qwen/Qwen3.5-9B, révision des poids de la base E1 du Mac
MODELE=${MODELE:-/workspace/qwen3.5-9b}
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
[ -d .venv ] || uv venv --python 3.12
# vLLM d'abord (il fixe sa version de torch), puis le reste ; noyaux rapides pour les couches gated delta de Qwen3.5.
uv pip install "vllm>=0.19" peft pyyaml sqlmodel scipy statsmodels pytest flash-linear-attention ninja
# causal-conv1d se compile ; échec possible si CUDA du pod != CUDA de torch (constaté : 12.8 contre 13.0) -> repli PyTorch, correct mais plus lent
uv pip install --no-build-isolation causal-conv1d || echo "causal-conv1d non installé : repli PyTorch"
if [ ! -f "$MODELE/config.json" ]; then
  .venv/bin/hf download Qwen/Qwen3.5-9B --revision "$REVISION" --local-dir "$MODELE"
fi
# Mêmes poids que sur le Mac, octet pour octet (sinon on ne compare pas la même base) :
(cd "$MODELE" && sha256sum -c "$OLDPWD/configs/poids_qwen35_9b.sha256")
nvidia-smi --query-gpu=name,memory.total --format=csv
.venv/bin/python -c "import vllm, torch, peft; print('vllm', vllm.__version__, 'torch', torch.__version__, 'peft', peft.__version__)"
.venv/bin/python -m pytest -q tests/test_lots.py tests/test_boucle.py tests/test_verify.py
echo "INSTALLATION OK"
