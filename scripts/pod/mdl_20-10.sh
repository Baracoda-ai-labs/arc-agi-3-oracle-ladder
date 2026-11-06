#!/usr/bin/env bash
# SUR LE POD (CW-271) : porte partielle par seuil (0,5) contre porte par compression (CHRYS_MDL=1), appariée, copie figée
# /workspace/fige_mdl. (1) moteur seul, 20 jeux publics non témoins, 10 min ; (2) banc PuzzleScript, 177 jeux, 30 s.
# Les deux conditions ont CHRYS_PARTIEL=2 AMODAL BUT_SUPPOSE POURSUITE_UTILE (+ défauts du HEAD) ; seule MDL diffère.
W=/workspace; F=$W/fige_mdl; P=$W/harnais/.venv/bin/python; O=$W/runs/mdl; mkdir -p $O
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
JEUX=$(ls $F/experiments/arc3/environment_files | grep -v -E '^(vc33|tu93|wa30|s5i5|cn04)$')
cd $F; j "MDL : début (HEAD $(cat $F/HEAD.txt))"
for c in seuil mdl; do
  M=0; [ $c = mdl ] && M=1
  for g in $JEUX; do
    ( CHRYS_MDL=$M CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_BUT_SUPPOSE=1 CHRYS_POURSUITE_UTILE=1 CHRYS_MOTEUR_BUDGET_S=2 \
      PYTHONPATH=$F nice -n 10 timeout 1800 $P experiments/moteur_seul/banc.py $g $c $O/${c}_$g.json 10 0 > $O/${c}_$g.log 2>&1 ) &
  done
  ( CHRYS_MDL=$M CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_BUT_SUPPOSE=1 CHRYS_POURSUITE_UTILE=1 PYTHONPATH=$F OMP_NUM_THREADS=1 nice -n 10 \
    $P experiments/instrument/ps_banc.py experiments/banc_ps/environment_files $O/ps_$c.json 30 40 1800 > $O/ps_$c.log 2>&1 ) &
done
wait; j "MDL : fin"; touch $W/bancs/mdl.FINI
