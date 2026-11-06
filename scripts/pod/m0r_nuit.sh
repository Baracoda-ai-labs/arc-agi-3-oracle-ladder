#!/usr/bin/env bash
# SUR LE POD (CW-356/357, Thomas 21/10) : nuit = M0 (S2 + CHRYS_HISTORIQUE_FIDELE, « référence de la fusion ») contre R (Franzen
# seul), ABBA par blocs (R M M R | M R R M …) jusqu'à bancs/STOP_M, disque < 4 Go ou 24/10 04:50 UTC. Après la fin du tirage 2
# ft09/re86 (suite_21-10 arrêtée par STOP_S avant ses bras M0/M1/V/P, retirés). 20 jeux non témoins, 48 min, même serveur.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
anon() { awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat; }
while [ ! -f $W/bancs/suite_21-10.FINI ]; do sleep 30; done
S2="CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_TUTO=0 CHRYS_MOTEUR_BUDGET_S=2 CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60
 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 CHRYS_MOTEUR_PROCESSUS=1 CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_FORMES=1
 CHRYS_COMPORTEMENT=1 CHRYS_BUT_SUPPOSE=1"
grep -rq CHRYS_HISTORIQUE_FIDELE $R/chrysalide/arc3/ || { j "m0r : HISTORIQUE_FIDELE absent du code : ARRÊT"; exit 1; }
b=1
while :; do
  for n in NR$b NM$b NM$((b+1)) NR$((b+1)) NM$((b+2)) NR$((b+2)) NR$((b+3)) NM$((b+3)); do
    [ -f $W/bancs/STOP_M ] && { j "m0r : STOP_M avant $n"; break 2; }
    [ "$(date -u +%s)" -ge "$(date -u -d '2026-10-24 04:50' +%s)" ] && { j "m0r : 24/10 04:50 UTC"; break 2; }
    [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "m0r : moins de 4 Go libres avant $n"; break 2; }
    a=(); case $n in NM*) a=($S2 CHRYS_HISTORIQUE_FIDELE=1);; esac
    j "m0r : début $n anon $(anon) Go"
    cd $R && bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
    j "m0r : fin $n (code $?)"
    find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
  done
  b=$((b+4))
done
touch $W/bancs/m0r_nuit.FINI; j "m0r fini"
