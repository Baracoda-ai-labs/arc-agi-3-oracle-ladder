#!/usr/bin/env bash
# SUR LE POD (CW-327, Thomas 23 h 38) : suite des paires ABBA P/H1 après h0.sh (qui s'arrête à 04:50 UTC), tant que D n'a pas
# livré l'hybride corrigé : on s'arrête si /workspace/bancs/STOP_H existe, ou à 24/10 04:50 UTC (arrêt du pod à 06:00).
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
anon() { awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat; }
while [ ! -f $W/bancs/h0.FINI ]; do sleep 60; done
S2="CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_TUTO=0 CHRYS_MOTEUR_BUDGET_S=2 CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60
 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 CHRYS_MOTEUR_PROCESSUS=1 CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_FORMES=1
 CHRYS_COMPORTEMENT=1 CHRYS_BUT_SUPPOSE=1"
i=6
while :; do
  for n in P$i H1s${i}a H1s${i}b P$((i+1)); do
    [ -f $W/bancs/STOP_H ] && { j "h0_suite : STOP_H posé, arrêt avant $n"; break 2; }
    [ "$(date -u +%s)" -ge "$(date -u -d '2026-10-24 04:50' +%s)" ] && { j "h0_suite : 24/10 04:50 UTC, arrêt avant $n"; break 2; }
    [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "h0_suite : moins de 4 Go libres, arrêt avant $n"; break 2; }
    [ "$(anon)" -gt 150 ] && { j "h0_suite : mémoire $(anon) Go > 150 avant $n : arrêt des bras but/sous_buts du ×100"; for p in $(pgrep -f 'budget100.py .* (but|sous_buts) '); do kill "$p"; done; sleep 30; }
    # variante de l'hybride lue à neuf à chaque passage (CCM-303-A) : /workspace/bancs/VARIANTE_H = « H0 » (prise de main après
    # 200 coups de stagnation) ; absent = H1. Le nom du passage la porte (H1s… ou H0s…).
    v=$(cat $W/bancs/VARIANTE_H 2>/dev/null || echo H1); [ "$v" = H0 ] && n=${n/H1s/H0s}
    a=(); case $n in H1*) a=($S2);; H0*) a=($S2 CHRYS_STAGNATION_COUPS=200);; P*) a=($S2 CHRYS_STAGNATION_COUPS=100000000);; esac
    j "h0_suite : début $n anon $(anon) Go"
    cd $R && bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
    j "h0_suite : fin $n (code $?)"
    find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k -print0 | xargs -0 -r gzip -6
  done
  i=$((i+2))
done
touch $W/bancs/h0_suite.FINI; j "h0_suite fini"
