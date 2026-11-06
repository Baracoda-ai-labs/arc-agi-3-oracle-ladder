#!/usr/bin/env bash
# SUR LE POD (CW-408) : arrêt du pod à 18:00 UTC (20 h Paris) le jour même ; le 30/10 au soir, c'est le dernier (pas de reprise
# ensuite : le réveil du Mac s'arrête après le 30). Arrêt dur, à l'heure, quel que soit le passage en cours (coût d'abord).
FIN=$(date -u -d "$(date -u +%F) 18:00" +%s); S=$(( FIN - $(date -u +%s) )); [ $S -lt 60 ] && S=60
echo "$(date '+%d/%m %H:%M') arrêt du soir : dans $S s" >> /workspace/runs/chaine_etapes.txt
sleep $S
echo "$(date '+%d/%m %H:%M') arrêt du soir : runpodctl stop pod" >> /workspace/runs/chaine_etapes.txt
touch /workspace/AUTORISE_ARRET; runpodctl stop pod okm0nd2f3e4jc5
