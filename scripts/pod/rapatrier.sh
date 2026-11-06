#!/usr/bin/env bash
# Depuis le Mac : rapatrie les runs du pod dans experiments/. Usage : scripts/pod/rapatrier.sh <hôte ssh> [port]
set -euo pipefail
cd "$(dirname "$0")/../.."
hote=$1; port=${2:-22}
rsync -az -e "ssh -p $port" "$hote:/workspace/chrysalide3/experiments/" experiments/
echo "rapatrié depuis $hote"
