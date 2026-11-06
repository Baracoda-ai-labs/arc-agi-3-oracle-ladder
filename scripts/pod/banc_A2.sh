#!/usr/bin/env bash
# SUR LE POD A : reprise du banc P0 après les MemoryError (6 Go) et le module manquant (18/10, 19 h 56).
# compile → paliers → mixte → iw1, 4 processus × 16 Go ; puis file ouverte /workspace/bancs/file_banc ; vide 30 min → arrêt.
W=/workspace; R=$W/chrysalide3; F=$W/bancs/file_banc
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
lot() {
  mv $R/experiments/T3.0/raw/plafond_P0_$2.json $R/experiments/T3.0/raw/plafond_P0_$2_echec_memoire.json 2>/dev/null
  cd $R && LOT_VMEM_KO=16000000 bash scripts/pod/lancer_lot.sh "$1" env PYTHONPATH=$R:$R/experiments/T3.0:$W/pylib python experiments/T3.0/plafonds.py tous 1,2,3 1000000 600 4 "$2"
  until [ -f $W/bancs/$1.FINI ]; do sleep 60; done; j "banc : fin $1 ($(cat $W/bancs/$1.FINI))"
}
for v in compile paliers mixte iw1; do lot banc_${v}_v2 $v; done
inactif=0
while [ $inactif -lt 30 ]; do
  c=$(ls $F/*.cmd 2>/dev/null | head -1)
  if [ -n "$c" ]; then n=$(basename "$c" .cmd); mv "$c" "$c.lance"; j "banc : début $n"
    cd $R && LOT_VMEM_KO=16000000 bash scripts/pod/lancer_lot.sh "$n" bash "$c.lance"; until [ -f $W/bancs/$n.FINI ]; do sleep 60; done
    j "banc : fin $n"; inactif=0
  else sleep 60; inactif=$((inactif+1)); fi
done
until [ -f $W/bancs/e4_n1_publics.FINI ] && { [ ! -f $W/bancs/e4_sansulimit.sh ] || [ -f $W/bancs/e4_sansulimit.FINI ]; }; do sleep 60; done
j "banc vide depuis 30 min : arrêt du pod A (CW-186)"; touch $W/AUTORISE_ARRET; . $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID"
