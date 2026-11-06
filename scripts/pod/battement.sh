#!/usr/bin/env bash
# SUR LE POD : alerte « calcul long arrêté » (demande de Thomas). Usage : nohup bash scripts/pod/battement.sh <pid> <nom> &
# Écrit l'heure dans /workspace/battement chaque minute tant que <pid> vit ; à l'arrêt, écrit /workspace/ARRET (nom, heure,
# fin du journal). Pas de service externe (CW-035) : la session Claude Code qui suit le run relève /workspace/ARRET et notifie Thomas.
set -uo pipefail
pid=$1; nom=$2; W=/workspace
while kill -0 "$pid" 2>/dev/null; do date +%s > "$W/battement"; sleep 60; done
{ echo "$nom arrêté à $(date '+%d/%m %H:%M')"; tail -5 "$W/$nom.log" 2>/dev/null; } > "$W/ARRET"
exit 0
