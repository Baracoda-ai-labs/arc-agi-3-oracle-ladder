#!/usr/bin/env bash
# SUR LE POD : (re)lance la recherche des traces de tous les niveaux (CW-098.4), détachée, priorité basse.
# Passer par ce fichier évite qu'un pgrep/pkill distant se reconnaisse lui-même. Usage : bash scripts/pod/lancer_traces.sh [plafond_s] [memoire_Go]
# Leçon FC2 (17/10) : la recherche a saturé la mémoire du conteneur et tué SGLang. D'où : 6 processus au plus, 4 Go de mémoire
# virtuelle par processus (ulimit -v), budget total passé au script, et un GARDIEN qui tue la recherche si la mémoire du
# conteneur dépasse 150 Go (le serveur passe avant).
cd "$(dirname "$0")/../.."
for p in $(pgrep -f "scripts/pod/traces_tous.py"); do kill "$p" 2>/dev/null; done
for p in $(pgrep -f "gardien_traces"); do kill "$p" 2>/dev/null; done
sleep 2
[ -d /workspace/bancs/traces ] && mv /workspace/bancs/traces "/workspace/bancs/traces_ancien_$(date +%H%M)"
mkdir -p /workspace/bancs/traces
( ulimit -v 6000000; TRACES_PROC=6 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 setsid nohup nice -n 19 \
  /workspace/harnais/.venv/bin/python scripts/pod/traces_tous.py /workspace/environment_files \
  /workspace/bancs/traces "${1:-900}" "${2:-24}" > /workspace/bancs/traces.log 2>&1 < /dev/null & )
setsid nohup bash -c 'exec -a gardien_traces bash -c "while pgrep -f scripts/pod/traces_tous.py >/dev/null; do
  m=\$(cat /sys/fs/cgroup/memory.current); a=\$(grep -E \"^anon \" /sys/fs/cgroup/memory.stat | cut -d\" \" -f2)
  if [ \"\$a\" -gt 150000000000 ]; then pkill -f scripts/pod/traces_tous.py; echo \"\$(date) tué : anon=\$a\" >> /workspace/bancs/traces_gardien.log; fi
  sleep 10; done"' > /dev/null 2>&1 < /dev/null &
sleep 3
pgrep -fc "scripts/pod/traces_tous.py"
