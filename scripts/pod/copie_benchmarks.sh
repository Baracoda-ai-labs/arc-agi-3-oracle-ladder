#!/usr/bin/env bash
# SUR LE POD (CCM-035-F) : copie le benchmark.json de chaque passage fini dans /workspace/benchmarks/<passage>.json (quelques Mo),
# pour que F le relise même après le retrait du passage. Toutes les 5 min, jusqu'au 30/10 22:00 UTC.
W=/workspace; mkdir -p $W/benchmarks
while [ "$(date -u +%s)" -lt "$(date -u -d '2026-10-30 22:00' +%s)" ]; do
  for d in $W/runs/*/FINI; do
    p=$(basename $(dirname $d)); [ -f $W/benchmarks/$p.json ] && continue
    f=$(ls $W/runs/$p/*/benchmark.json* 2>/dev/null | head -1); [ -n "$f" ] || continue
    case $f in *.gz) zcat $f > $W/benchmarks/$p.json;; *) cp $f $W/benchmarks/$p.json;; esac
  done
  sleep 300
done
