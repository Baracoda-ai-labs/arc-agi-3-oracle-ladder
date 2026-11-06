#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# Prépare le jeu de données Kaggle « chrysalide-arc3 » (CW-024 d) : nos fichiers (double licence) et les licences, même arborescence que le dépôt
# (patcher_franzen.py retrouve chrysalide/arc3/ à partir de son propre chemin). Sortie : experiments/arc3/kaggle_paquet/
set -euo pipefail
cd "$(dirname "$0")/../.."
P=experiments/arc3/kaggle_paquet
mkdir -p "$P/chrysalide/arc3" "$P/scripts/arc3"
cp chrysalide/arc3/{archi,branche,graphe,duck}.py "$P/chrysalide/arc3/"
cp scripts/arc3/patcher_franzen.py "$P/scripts/arc3/"
cp chrysalide/arc3/LICENSE-MIT-0 chrysalide/arc3/LICENSE-APACHE-2.0 chrysalide/arc3/LICENCE.md chrysalide/arc3/NOTICE.md "$P/"
git rev-parse --short HEAD > "$P/COMMIT"
( cd "$P" && find . -type f | sort | xargs shasum -a 256 ) > "$P.sha256"
echo "paquet prêt : $P (commit $(cat "$P/COMMIT"))"
