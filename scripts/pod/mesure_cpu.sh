#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD (voie 2 a, CW-028/039/041) : CPU du CONTENEUR (cgroup, pas l'hôte : nproc y voit 288 cœurs) et GPU pendant un run.
# Usage : nohup bash scripts/pod/mesure_cpu.sh <pid> > cpu.tsv &   (une ligne toutes les 30 s ; cœurs_occupés = usage cgroup / durée)
set -uo pipefail
pid=$1
quota=$(cat /sys/fs/cgroup/cpu.max 2>/dev/null || echo "? ?")
echo "# cpu.max=$quota (cœurs alloués = quota/période) ram_go=$(free -g | awk '/Mem/{print $2}') os.cpu_count=$(python3 -c 'import os;print(len(os.sched_getaffinity(0)))')"
echo -e "t\tcoeurs_occupes\tgpu_pct\tvram_mo"
u0=$(awk '/usage_usec/{print $2}' /sys/fs/cgroup/cpu.stat); t0=$(date +%s)
while kill -0 "$pid" 2>/dev/null; do
  sleep 30
  u1=$(awk '/usage_usec/{print $2}' /sys/fs/cgroup/cpu.stat); t1=$(date +%s)
  g=$(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
  awk -v du=$((u1 - u0)) -v dt=$((t1 - t0)) -v t=$t1 -v g="$g" 'BEGIN{split(g,a,","); printf "%d\t%.2f\t%s\t%s\n", t, du/1e6/dt, a[1], a[2]}'
  u0=$u1; t0=$t1
done
