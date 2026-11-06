#!/usr/bin/env bash
# SUR LE POD A (CW-224.2, criblage des flux) : Franzen v3 pur, 20 jeux non témoins, 48 min, seul sur la carte (la file CPU
# compile_gpt / eval_moteur tourne à côté, sans GPU). F6, F8, puis F10c (référence, même nuit). Retient l'arrêt du pod.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
echo "until [ -f $W/bancs/flux.FINI ]; do sleep 60; done" > $W/bancs/file_banc/zz_attendre_flux.cmd
for b in F6:6 F8:8 F10c:10; do
  n=${b%%:*}; m=${b##*:}
  j "flux : début $n (ARC3_MAX_ACTIVE_STREAMS=$m)"
  cd $R && bash scripts/pod/bloc.sh $n ARC3_MAX_ACTIVE_STREAMS=$m MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "flux : fin $n (code $?)"
done
touch $W/bancs/flux.FINI
