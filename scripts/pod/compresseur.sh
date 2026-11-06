#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD, à côté de la chaîne : compresse les journaux de requêtes des blocs FINIS (chaque ligne recopie tout le contexte :
# ≈ 3-5 Go par bloc, le volume n'a que ≈ 24 Go libres) ; prévient si le disque descend sous 5 Go.
# Usage : setsid nohup bash scripts/pod/compresseur.sh > /workspace/runs/compresseur.log 2>&1 < /dev/null &
W=/workspace
while ps -eo args | grep -q "[c]haine_nuit.sh"; do
  for d in "$W"/runs/*/; do
    { [ -f "$d/FINI" ] || [ -f "$d/ARRET" ]; } || continue
    find "$d" -name '*_requests.jsonl' -exec gzip -1 {} + 2>/dev/null
  done
  libre=$(df --output=avail -BG "$W" | tail -1 | tr -dc 0-9)
  [ "$libre" -lt 5 ] && echo "$(date '+%H:%M') DISQUE BAS : ${libre} Go libres" | tee "$W/runs/DISQUE_BAS"
  sleep 300
done
