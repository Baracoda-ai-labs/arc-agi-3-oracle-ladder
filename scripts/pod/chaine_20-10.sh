#!/usr/bin/env bash
# SUR LE POD okm0nd2f3e4jc5 (CW-268/269/270), autonome (le Mac est coupé de 9 h 30 à 10 h 30) :
#  1. attend la fin de setup_franzen.sh ; 2. dépendances du moteur dans le venv du harnais (clingo, scipy) ;
#  3. télémétrie CPU toutes les 2 min (pour D) ; 4. compaction (GPU, ABBA) ; 5. banc des niveaux frontière restants (CPU,
#     copie figée /workspace/fige). La minuterie /workspace/minuterie.sh (6 h 30) reste le seul arrêt dur.
W=/workspace; R=$W/chrysalide3; P=$W/harnais/.venv/bin/python
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
until grep -q "INSTALLATION FRANZEN OK" $W/setup.log 2>/dev/null; do
  pgrep -f setup_franzen.sh >/dev/null || { j "setup_franzen.sh fini SANS succès : chaîne arrêtée"; exit 1; }
  sleep 30
done
j "installation OK"
export PATH="$HOME/.local/bin:$PATH"
uv pip install -q --python $P "clingo==5.8.*" scipy >> $W/runs/deps.log 2>&1 && j "dépendances du moteur OK" || j "dépendances : ÉCHEC"
( while [ ! -f $W/bancs/compaction.FINI ]; do
    echo "{\"t\": $(date +%s), \"cpu_stat\": \"$(tr '\n' ' ' < /sys/fs/cgroup/cpu.stat 2>/dev/null)\", \"charge\": \"$(cut -d' ' -f1-3 /proc/loadavg)\", \"gpu\": \"$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)\"}" >> $W/runs/telemetrie_cpu.jsonl
    sleep 120
  done ) &
( cd $R && SANS_ARRET=1 bash scripts/pod/compaction.sh > $W/runs/compaction.log 2>&1 ) &
mkdir -p $W/runs/rates
cd $W/fige && for g in re86 sc25 sk48 sp80 su15 tr87; do
  ( CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_BUT_SUPPOSE=1 CHRYS_MOTEUR_BUDGET_S=2 PYTHONPATH=$W/fige nice -n 10 timeout 3600 \
    $P experiments/instrument/banc_rates.py $g $W/runs/rates/$g.json 10 200000 300 > $W/runs/rates/$g.log 2>&1 ) &
done
wait; j "chaîne 20/10 finie"
