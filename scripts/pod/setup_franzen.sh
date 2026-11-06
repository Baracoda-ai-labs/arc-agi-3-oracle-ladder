#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD (T2.4, CW-038/041) : installation idempotente de la base Franzen + notre patch, tout sous /workspace.
#   bash scripts/pod/setup_franzen.sh        (journal conseillé : > /workspace/setup.log 2>&1)
# Pod réel : image RunPod PyTorch 2.8 / CUDA 12.8 / Ubuntu 24.04, RTX PRO 6000 (SM120), 90 Go RAM, 16 vCPU, volume 150 Go.
# Modèle : albucino W4A16-FP8PLE (129 Go, brouillon MTP inclus) — l'Intel BF16-PLE (181 Go) ne tient ni sur le volume ni en RAM.
set -euo pipefail
[ -f /workspace/pod_env.sh ] && . /workspace/pod_env.sh   # RUNPOD_POD_ID, absent des sessions distantes
cd "$(dirname "$0")/../.."
D=$PWD; W=/workspace
pgrep -f veille_inactivite.sh >/dev/null || nohup "$W/veille_inactivite.sh" >/dev/null 2>&1 &   # garde-fou de Cowork (CW-041)
nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader | tee "$W/gpu.txt"
grep -q "12.0" "$W/gpu.txt" || { echo "ARRÊT : carte non SM120"; exit 1; }
pilote=$(cut -d, -f4 "$W/gpu.txt" | tr -d ' ' | cut -d. -f1)
[ "$pilote" -ge 580 ] || { echo "ARRÊT : pilote $pilote < 580, CUDA 13 (bundle Pennyroyal) impossible"; exit 1; }
command -v pkg-config >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  pkg-config build-essential >/dev/null; }   # prérequis du constructeur Pennyroyal, absents de l'image PyTorch (17/10)
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
# caches et chantier sur le disque du conteneur (60 Go) : le volume (150 Go) est occupé à 86 % par le modèle
export PATH="$HOME/.local/bin:$PATH" UV_CACHE_DIR=/root/.cache/uv HF_HOME=$W/.cache/hf PIP_CACHE_DIR=/root/.cache/pip
# 1. Franzen au commit lu (Apache-2.0)
[ -d "$W/franzen" ] || git clone -q https://github.com/da-fr/arc-agi-3-solution "$W/franzen"
(cd "$W/franzen" && git checkout -q 10882e33 && git rev-parse HEAD > "$W/franzen.commit")
# 2. poids d'abord (le plus long ; en parallèle du bundle)
( [ -f "$W/modele/config.json" ] || uvx --from huggingface_hub hf download albucino/Qwen3.8-Flash-Next-W4A16-FP8PLE \
    --local-dir "$W/modele" ) > "$W/poids.log" 2>&1 &
POIDS=$!
# 3. bundle SGLang Pennyroyal (CUDA 13 en roues, vérifié hors ligne par le constructeur)
# reprise d'une étape interrompue (roues SGLang déjà construites) : le constructeur ne refait que la validation hors ligne
etape=$(ls -d "$W"/out-penny/.penny-bundle.* 2>/dev/null | tail -1 || true)
if [ -n "$etape" ] && [ -d "$etape/wheels" ]; then export RESUME_STAGE="$etape"; rm -rf /root/build-penny/resolve.* /root/build-penny/offline-check.* /root/.cache/uv /root/.cache/pip; fi
[ -d "$W/out-penny/bundle-pennyroyal" ] || OUT="$W/out-penny" WORK=/root/build-penny PYTHON=python3 BUILD_JOBS=${BUILD_JOBS:-32} \
  bash "$W/franzen/serving/build_bundle_pennyroyal.sh" > "$W/bundle.log" 2>&1
rm -rf /root/build-penny "$W/build-penny"   # chantier de compilation : plusieurs Go inutiles ensuite
# 4. harnais : copie de travail patchée (CHRYS_* éteints par défaut = Franzen inchangé)
[ -d "$W/harnais" ] || cp -R "$W/franzen/ARC3-Inference" "$W/harnais"
[ -d "$W/tufa-arc-agi-framework" ] || cp -R "$W/franzen/tufa-arc-agi-framework" "$W/tufa-arc-agi-framework"
python3 "$D/scripts/arc3/patcher_franzen.py" "$W/harnais"
if [ "${RO_EXACT:-0}" = "1" ]; then   # 29/10 : harnais = cellule 12 des carnets RO/ROF, mêmes patchs dans le même ordre
  for p in patcher_garde.py patcher_outils.py patcher_faits.py; do python3 "$D/scripts/arc3/$p" "$W/harnais"; done
else
python3 "$D/scripts/arc3/patcher_perception.py" "$W/harnais"   # bloc P (B), éteint par défaut
python3 "$D/scripts/arc3/patcher_outils.py" "$W/harnais"       # V2' (A), éteint par défaut
fi
# le harnais exige Python ==3.12.12 (uv la télécharge)
(cd "$W/harnais" && { .venv/bin/python -V 2>/dev/null | grep -q "3.12.12" || uv venv -q --clear --python 3.12.12 .venv; } \
   && env -u VIRTUAL_ENV uv sync -q --locked --extra dev --python .venv/bin/python && uv pip install -q --python .venv/bin/python --no-deps -e "$W/tufa-arc-agi-framework")
# 5. jeux publics hors ligne (clé anonyme, comme T2.0)
mkdir -p "$W/environment_files" && (cd "$W" && "$W/harnais/.venv/bin/python" -c "
from arc_agi import Arcade, OperationMode
arc = Arcade(operation_mode=OperationMode.NORMAL, environments_dir='environment_files')
ids = sorted(e.game_id for e in arc.get_environments()); [arc.make(g) for g in ids]; print(len(ids), 'jeux')")
wait $POIDS || { tail -5 "$W/poids.log"; exit 1; }
du -sh "$W/modele" "$W/out-penny" "$W/harnais/.venv"; df -h "$W" | tail -1
echo "INSTALLATION FRANZEN OK"
