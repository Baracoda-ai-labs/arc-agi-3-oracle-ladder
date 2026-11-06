#!/usr/bin/env bash
# SUR LE POD (CW-345) : fenêtre GPU de 45 min pour la sonde Qwen de H. STOP_W posé pendant R2 (à 09:00 UTC) -> w_abba s'arrête
# après R2 ; serveur laissé seul ; w_abba2 reprend au bloc 2 (R3 W3 W4 R4) à 11:15 UTC.
W=/workspace
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
until [ "$(date -u +%H%M)" -ge 0900 ]; do sleep 30; done
touch $W/bancs/STOP_W; j "pause_sonde : STOP_W posé (arrêt de w_abba après R2, CW-345)"
while [ ! -f $W/bancs/w_abba.FINI ]; do sleep 30; done
j "pause_sonde : GPU libre pour la sonde Qwen de H jusqu'à 11:15 UTC (serveur flashnext, 127.0.0.1:8011)"
setsid nohup bash $W/w_abba2_run.sh > $W/runs/w_abba2.log 2>&1 < /dev/null &
