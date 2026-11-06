#!/usr/bin/env bash
# SUR LE POD (S1 ARC-AGI-3, CW-021/022) : installation idempotente. Usage, sur le pod : bash scripts/pod/setup_arc3.sh
#   - environnement Chrysalide (.venv) : vLLM récent (service local compatible OpenAI), arc-agi (jeux hors ligne), nos outils ;
#   - modèles (téléchargement autorisé sur le pod seulement) : Qwen/Qwen3.6-27B-FP8 et Qwen/Qwen3.8-27B-FP8 (Apache 2.0) ;
#   - Duck (référence isolée, option a) : /workspace/duck-harness avec SON environnement ; jamais dans notre dépôt ni nos dépendances.
set -euo pipefail
cd "$(dirname "$0")/../.."
export PATH="$HOME/.local/bin:$PWD/.venv/bin:$PATH"
W=/workspace
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
[ -d .venv ] || uv venv --python 3.12
uv pip install "vllm>=0.30" arc-agi pyyaml sqlmodel scipy pytest ninja
for m in Qwen3.6-27B-FP8 Qwen3.8-27B-FP8; do
  [ -f "$W/$m/config.json" ] || .venv/bin/hf download "Qwen/$m" --local-dir "$W/$m"
done
# Jeux publics : clé anonyme, sans compte (constaté le 30/09), puis hors ligne.
mkdir -p experiments/arc3 && (cd experiments/arc3 && ../../.venv/bin/python -c "
from arc_agi import Arcade, OperationMode
arc = Arcade(operation_mode=OperationMode.NORMAL, environments_dir='environment_files')
ids = [l.strip() for l in open('jeux_publics.txt') if l.strip()]
assert all(arc.make(g) is not None for g in ids), 'jeu manquant'
print(len(ids), 'jeux publics prêts')")
# Duck : environnement séparé (son propre uv / pyproject). Code lu par la machine, pas par nous (salle blanche, option b).
if [ ! -d "$W/duck-harness" ]; then git clone --depth 1 https://github.com/Tufalabs/duck-harness "$W/duck-harness"; fi
(cd "$W/duck-harness" && git rev-parse HEAD > "$W/duck-harness.commit" && (cd ARC3-Inference && make install) ) \
  || echo "ATTENTION : installation du Duck échouée, voir ci-dessus (référence a non disponible)"
nvidia-smi --query-gpu=name,memory.total --format=csv
.venv/bin/python -c "import vllm, arc_agi; print('vllm', vllm.__version__)"
df -h "$W" | tail -1
echo "INSTALLATION ARC3 OK"
