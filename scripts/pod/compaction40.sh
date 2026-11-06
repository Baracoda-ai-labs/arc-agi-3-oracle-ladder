#!/usr/bin/env bash
# SUR LE POD (CW-292) : compaction refaite sur le POD SEUL (la 1re était polluée par la charge, CCM-267-A). Attend que la
# charge retombe (< 10 sur 1 min, au plus 40 min d'attente), puis C0c C1c C1d C0c' (ABBA) à 40 min par jeu, fin avant 15:00 UTC.
# Trace la charge chaque minute (runs/charge40.txt) pour le contrôle de validité. Pas d'arrêt du pod ici (minuterie à part).
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
( while [ ! -f $W/bancs/compaction40.FINI ]; do echo "$(date -u +%H:%M) hote=$(cut -d' ' -f1 /proc/loadavg) nous=$(ps -eo pcpu,args --no-headers | grep -v -e sglang -e sgl-intel | awk '{s+=$1} END {print int(s)}')% bb=$(pgrep -fc '[b]anc_buts') p0=$(pgrep -fc '[p]lafonds.py')" >> $W/runs/charge40.txt; sleep 60; done ) &
# /proc/loadavg est celui de l'HÔTE (voisins compris : ≈ 95 avec notre conteneur vide) ; on attend donc que NOS processus hors
# serveur sglang prennent moins de 2 cœurs (somme des %CPU).
for i in $(seq 40); do
  c=$(ps -eo pcpu,args --no-headers | grep -v -e sglang -e sgl-intel | awk '{s+=$1} END {print int(s)}'); [ "$c" -lt 200 ] && break; sleep 60
done
j "compaction40 : CPU de nos processus hors serveur au départ = $c %"
j "compaction40 : charge au départ $(cut -d' ' -f1-3 /proc/loadavg)"
for b in C0c:0 C1c:29696 C1d:29696 C0d:0; do
  n=${b%%:*}; m=${b##*:}
  h=$(date -u +%H%M); [ "$h" -gt 1408 ] && { j "compaction40 : $n non lancé (trop tard pour finir avant 15:00 UTC)"; break; }
  j "compaction40 : début $n (ARC3_SUMMARY_INTERVAL_TOKENS=$m, 40 min) charge $(cut -d' ' -f1 /proc/loadavg)"
  cd $R && bash scripts/pod/bloc.sh $n ARC3_SUMMARY_INTERVAL_TOKENS=$m MAX_RUNTIME_MINUTES=40 > $W/runs/$n.log 2>&1 < /dev/null
  j "compaction40 : fin $n (code $?)"
done
touch $W/bancs/compaction40.FINI; j "compaction40 finie"
