#!/usr/bin/env bash
# SUR LE POD (CW-294.6, CW-315) : mesure quotidienne des 13 niveaux frontière avec les réglages du jour (copie figée de HEAD,
# G allumé par défaut, COPIE allumé), entonnoir du moteur ; départ à 03:00 UTC (fin des bras ×100), fin ≈ 03:40 UTC.
W=/workspace; F=$W/fige_matin; P=$W/harnais/.venv/bin/python; O=$W/runs/frontieres_matin; mkdir -p $O $F
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
tar xzf $W/fige_matin.tgz -C $F
until [ "$(date -u +%H%M)" -ge 0300 ] && [ "$(date -u +%H%M)" -lt 1200 ]; do sleep 60; done
j "frontières du matin : départ ($(cat $W/fige_matin.txt)), anon $(awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat) Go"
cd $F && for g in bp35 dc22 g50t ka59 lf52 ls20 m0r0 re86 sc25 sk48 sp80 su15 tr87; do
  ( CHRYS_SOUSBUTS=1 CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_BUT_SUPPOSE=1 CHRYS_MOTEUR_BUDGET_S=2 PYTHONPATH=$F \
    CHRYSALIDE_DONNEES=$W/chrysalide3 nice -n 10 timeout 3600 \
    $P experiments/instrument/banc_rates.py $g $O/$g.json 10 200000 300 > $O/$g.log 2>&1 ) &
done
wait; gzip -6 $O/*.log $O/traces/*.jsonl 2>/dev/null; touch $W/bancs/frontieres_matin.FINI; j "frontières du matin finies"
