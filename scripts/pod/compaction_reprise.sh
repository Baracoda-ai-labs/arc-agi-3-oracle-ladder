#!/usr/bin/env bash
# SUR LE POD (CW-263) : reprise de la compaction après la chute du serveur (≈ 9 h 15, pendant la copie du volume par la
# migration) : C0a est complet ; on refait C1a (C1a_r), puis C1b, puis C0b. Pas d'arrêt du pod ici (minuterie à part).
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
for b in C1a_r:29696 C1b:29696 C0b:0; do
  n=${b%%:*}; m=${b##*:}
  [ -d $W/runs/$n ] && mv $W/runs/$n $W/runs/${n}_echec_serveur_$(date +%H%M)
  j "compaction (reprise) : début $n (ARC3_SUMMARY_INTERVAL_TOKENS=$m)"
  cd $R && bash scripts/pod/bloc.sh $n ARC3_SUMMARY_INTERVAL_TOKENS=$m MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "compaction (reprise) : fin $n (code $?)"
done
touch $W/bancs/compaction_reprise.FINI
