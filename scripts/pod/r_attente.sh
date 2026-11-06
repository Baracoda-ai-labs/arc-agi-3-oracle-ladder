#!/usr/bin/env bash
# SUR LE POD (22/10 soir) : en attendant le correctif de D (jalon 1, ip.sh), le GPU fait des passages R (Franzen seul, 48 min)
# plutôt que rien : ils élargissent la référence de bruit. Arrêt par bancs/STOP_R (entre deux passages), moins de 4 Go, ou 30/10 21:00 UTC.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') r_attente : $*" | tee -a $W/runs/chaine_etapes.txt; }
r=${R_DEBUT:?R_DEBUT}
while :; do
  n=R$r
  [ -f $W/bancs/STOP_R ] && { j "STOP_R avant $n"; break; }
  [ "$(date -u +%s)" -ge "$(date -u -d '2026-10-30 21:00' +%s)" ] && break
  [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "moins de 4 Go libres avant $n"; break; }
  j "début $n"
  cd $R && bash scripts/pod/bloc.sh $n ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "fin $n (code $?)"
  find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
  r=$((r+1))
done
touch $W/bancs/r_attente.FINI; j "fini"
