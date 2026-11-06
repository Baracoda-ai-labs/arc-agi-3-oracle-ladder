#!/usr/bin/env bash
# CW-411 (Thomas, 22/10 18 h 22) : pod en continu jusqu'au VENDREDI 30/10 à 23 h (Paris, heure d'hiver depuis le 25/10 = UTC+1)
# = 22:00 UTC ; arrêt unique, pas d'arrêt la nuit ni samedi. Remplace minuterie4.sh (arrêt du 24/10 8 h, désarmée).
FIN=$(date -u -d "2026-10-30 22:00" +%s); S=$(( FIN - $(date -u +%s) )); [ $S -lt 60 ] && S=60
echo "$(date '+%d/%m %H:%M') minuterie5 armée : arrêt le 30/10 à 22:00 UTC (23 h Paris), dans $S s (CW-411)" >> /workspace/runs/chaine_etapes.txt
sleep $S; echo "$(date) minuterie5 : arrêt du pod (30/10 23 h Paris)" >> /workspace/runs/chaine_etapes.txt; touch /workspace/AUTORISE_ARRET; runpodctl stop pod okm0nd2f3e4jc5
