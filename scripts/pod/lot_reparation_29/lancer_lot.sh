#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD (Codex 29/10, « réparation de predire », lot 1 ≤ 4 h installation comprise, plafond global 100 €).
# Usage, depuis le dépôt chrysalide3 cloné sur le pod :  bash scripts/pod/lot_reparation_29/lancer_lot.sh > /workspace/lot.log 2>&1
# Enchaîne : installation Franzen existante → harnais aligné sur la cellule RO → serveur SGLang → commande EXACTE de Codex
# (20 requêtes au plus, un appel à la fois, 1 h d'exécution au plus, aucun retry) → manifeste. N'arrête PAS le pod :
# l'extinction reste à Cowork/Claude (console), dès que /workspace/LOT_FINI existe.
set -euo pipefail
cd "$(dirname "$0")/../../.."
D=$PWD; W=/workspace; L=$D/scripts/pod/lot_reparation_29; SORTIE=$W/runs/reparation_predire_29_1
[ -e "$SORTIE" ] && { echo "ARRÊT : $SORTIE existe déjà (sortie neuve exigée)"; exit 1; }
date -u +%FT%TZ > $W/lot_debut.txt
bash scripts/pod/setup_franzen.sh > $W/setup.log 2>&1
python3 scripts/arc3/patcher_garde.py $W/harnais          # cellule RO : franzen + garde + outils (setup pose aussi perception, éteint)
python3 scripts/arc3/patcher_outils.py $W/harnais
mkdir -p $W/codex && tar -xzf $L/verificateur_strict_29_be8496f6.tar.gz -C $W/codex
V=$W/codex/experiments/reparation_blocage/verificateur_strict_29
mkdir -p $W/runs
setsid nohup python3 scripts/pod/franzen_lanceur.py > $W/runs/lanceur.log 2>&1 < /dev/null &
until curl -sf -m 5 http://127.0.0.1:8011/health >/dev/null; do
  ps -eo args | grep -q "[s]glang serve" || { echo "serveur mort avant d'être prêt"; tail -20 $W/runs/serve.log; exit 1; }
  sleep 15
done
date -u +%FT%TZ > $W/serveur_pret.txt
{ echo "harnais_sha256 $(cd $W/harnais && find . -path ./.venv -prune -o -type f -name '*.py' -print | sort | xargs sha256sum | sha256sum | cut -c1-64)"
  echo "franzen_commit $(cat $W/franzen.commit)"; echo "modele $(ls $W/modele | head -20 | tr '\n' ' ')"
  echo "modele_config_sha256 $(sha256sum $W/modele/config.json | cut -c1-64)"; nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
  echo "codex_ref be8496f68093e8822072f9c3357bf6800735242f"; } > $W/manifeste_lot.txt
(cd $V && timeout 3600 $W/harnais/.venv/bin/python essai_reparation.py run --cases cas_sk48.json --output $SORTIE \
   --harnais $W/harnais --base-url http://127.0.0.1:8011/v1 --model flashnext) > $W/runs/essai.log 2>&1 || echo "essai : code $?" >> $W/runs/essai.log
date -u +%FT%TZ > $W/lot_fin.txt; touch $W/LOT_FINI
echo "LOT FINI : sortie $SORTIE ; manifeste $W/manifeste_lot.txt ; arrêter le pod maintenant"
