#!/usr/bin/env bash
# Depuis le Mac : copie le dépôt sur le pod (experiments/ exclu : --delete y effacerait les résultats du pod) (sans .venv, sans modèles MLX, sans le jeu final). Usage : scripts/pod/envoyer.sh <hôte ssh> [port]
set -euo pipefail
cd "$(dirname "$0")/../.."
hote=$1; port=${2:-22}
rsync -az --delete -e "ssh -p $port" --exclude .venv --exclude /experiments --exclude models_mlx --exclude "data/final" --exclude '__pycache__' \
  ./ "$hote:/workspace/chrysalide3/"
echo "envoyé vers $hote:/workspace/chrysalide3"
