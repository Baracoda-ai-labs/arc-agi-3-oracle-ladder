#!/usr/bin/env bash
# SUR LE POD (CW-301) : R0g puis R0h après R0f, SUR LE MÊME SERVEUR (pas de relance) : bruit de Franzen pur à 48 min ET
# dégradation éventuelle du cache avec l'âge du serveur (série R0e → R0h). Pas d'arrêt du pod ici.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
while [ ! -f $W/bancs/r0r0.FINI ]; do sleep 60; done
for n in R0g R0h; do
  curl -sf http://127.0.0.1:8011/health >/dev/null || { j "r0gh : serveur absent avant $n, série arrêtée (pas de relance : la série mesure l'âge du serveur)"; break; }
  j "r0gh : début $n (48 min, même serveur) anon $(awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat) Go"
  cd $R && bash scripts/pod/bloc.sh $n ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "r0gh : fin $n (code $?)"
done
touch $W/bancs/r0gh.FINI; j "r0gh fini"
