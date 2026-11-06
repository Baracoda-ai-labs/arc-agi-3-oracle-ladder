#!/usr/bin/env bash
# SUR LE POD (CW-299, option (c) a) : bruit de Franzen pur à la durée de soumission. R0e puis R0f, 48 min par jeu, 20 jeux non
# témoins, 10 flux ; référence pour tous les essais (pod et Kaggle). Ensuite le GPU est à H (QLoRA). Pas d'arrêt du pod ici.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
for n in R0e R0f; do
  j "r0r0 : début $n (48 min) anon $(awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat) Go"
  cd $R && bash scripts/pod/bloc.sh $n ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "r0r0 : fin $n (code $?)"
done
touch $W/bancs/r0r0.FINI; j "r0r0 fini : GPU libre pour H"
