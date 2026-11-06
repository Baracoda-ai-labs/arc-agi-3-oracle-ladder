#!/usr/bin/env bash
# w_abba2 (CW-345) : reprise au bloc 2 après la fenêtre de la sonde Qwen.
# SUR LE POD (CW-335, décision de Thomas 7 h 55) : notes de travail de Franzen conservées d'un niveau à l'autre.
# R = Franzen tel quel (harnais patché, tous CHRYS_* éteints = cellule inerte, contrôle HC = 26,98) ;
# W = R + ARC3_WM_WIPE_ON_LEVEL=0 (un seul réglage ; effacement à la mort inchangé). ABBA × 2 : R1 W1 W2 R2 | R3 W3 W4 R4,
# puis d'autres blocs tant qu'il reste du temps (arrêt sur bancs/STOP_W ou 24/10 04:50 UTC). 20 jeux non témoins, 48 min.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
anon() { awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat; }
rm -f $W/bancs/STOP_W; until [ "$(date -u +%H%M)" -ge 1115 ]; do sleep 30; done  # CW-345 : reprise après la sonde Qwen de H
b=3
while :; do
  for n in R$b W$b W$((b+1)) R$((b+1)); do
    [ -f $W/bancs/STOP_W ] && { j "w_abba : STOP_W, arrêt avant $n"; break 2; }
    [ "$(date -u +%s)" -ge "$(date -u -d '2026-10-24 04:50' +%s)" ] && { j "w_abba : 24/10 04:50 UTC, arrêt avant $n"; break 2; }
    [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "w_abba : moins de 4 Go libres, arrêt avant $n"; break 2; }
    a=(); case $n in W*) a=(ARC3_WM_WIPE_ON_LEVEL=0);; esac
    j "w_abba : début $n anon $(anon) Go"
    cd $R && bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
    j "w_abba : fin $n (code $?)"
    find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
  done
  b=$((b+2))
done
touch $W/bancs/w_abba2.FINI; j "w_abba2 fini"
