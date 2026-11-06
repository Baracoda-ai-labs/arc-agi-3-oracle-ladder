#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD : attend que SGLang réponde sur 127.0.0.1:8011, puis lance la chaîne complète ; abandonne si le serveur meurt.
# Usage : setsid nohup bash scripts/pod/attendre_serveur.sh > /workspace/runs/attente.log 2>&1 < /dev/null &
cd "$(dirname "$0")/../.."
until curl -sf -m 5 http://127.0.0.1:8011/health >/dev/null; do
  ps -eo args | grep -q "[s]glang serve" || { echo "$(date '+%H:%M') serveur mort avant d'être prêt"; tail -20 /workspace/runs/serve.log; exit 1; }
  sleep 15
done
echo "$(date '+%H:%M') serveur prêt, lancement de la chaîne"
rm -f /workspace/KEEPALIVE
setsid nohup bash scripts/pod/chaine_nuit.sh >> /workspace/runs/chaine.log 2>&1 < /dev/null &
