#!/usr/bin/env bash
# SUR LE POD A (CW-228.3 a) : instrument de chaque soir, sur le HEAD synchronisé. En parallèle :
#  diagnostic 4 configurations (6 niveaux figés, un processus par jeu) ; moteur seul 20 jeux publics non témoins, pour chaque
#  variante de VARIANTES (nom=drapeaux séparés par des virgules) ; T4 (banc_export.py) pour chaque variante. Puis tableau unique.
# Usage : VARIANTES="ref=CHRYS_AMODAL=1,CHRYS_BUT_SUPPOSE=1 garde3=CHRYS_AMODAL=1,CHRYS_BUT_SUPPOSE=1,CHRYS_GARDE=3" bash scripts/pod/banc_nuit.sh
W=/workspace; R=$W/chrysalide3; P=$W/harnais/.venv/bin/python
N=$R/experiments/instrument/nuits/$(date +%Y%m%d_%H%M); mkdir -p $N/moteur_seul
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
VARIANTES=${VARIANTES:-"meilleure=CHRYS_AMODAL=1,CHRYS_JAUGE_COURTE=1,CHRYS_TUILES=1,CHRYS_BUT_SUPPOSE=1"}
JEUX=$(ls $R/experiments/arc3/environment_files | grep -v -E '^(vc33|tu93|wa30|s5i5|cn04)$')
cd $R; j "banc de nuit : début ($N ; variantes : $VARIANTES)"
( rm -f $R/experiments/instrument/raw/diag4_k40_g0_*.json
  for g in ft09 tn36 re86 sp80 ls20 tr87; do
    ( ulimit -v 16000000; DIAG_SUFFIXE=_$g PYTHONPATH=$R:$W/pylib CHRYS_AMODAL=1 nice -n 10 timeout 7200 \
      $P experiments/instrument/diag4.py 40 0 $g > $N/diag4_$g.log 2>&1 ) &
  done; wait
  $P -c "import json,glob; r={}; [r.update(json.load(open(f))) for f in glob.glob('$R/experiments/instrument/raw/diag4_k40_g0_*.json')]; json.dump(r, open('$N/diag4.json','w'), indent=1, default=str)"
  j "banc de nuit : diagnostic fini" ) &
for v in $VARIANTES; do
  nom=${v%%=*}; dr=${v#*=}; envs=$(echo $dr | tr ',' ' ')
  for g in $JEUX; do
    ( ulimit -v 16000000; env $envs CHRYS_MOTEUR_BUDGET_S=2 PYTHONPATH=$R:$W/pylib nice -n 10 timeout $(( 63 * 60 )) \
      $P experiments/moteur_seul/banc.py $g $nom $N/moteur_seul/${nom}_$g.json 48 0 > $N/moteur_seul/${nom}_$g.log 2>&1 ) &
  done
  ( ulimit -v 16000000; env $envs PYTHONPATH=$R:$R/experiments/T4:$W/pylib OMP_NUM_THREADS=1 nice -n 10 \
    $P experiments/T4/banc_export.py $W/t4/environment_files $N/t4_$nom.json 60 20 > $N/t4_$nom.log 2>&1 ) &
done
wait
$P experiments/instrument/tableau.py $N "pod A" > $N/tableau.log 2>&1
j "banc de nuit : fin ($N)"; touch $W/bancs/banc_nuit.FINI
