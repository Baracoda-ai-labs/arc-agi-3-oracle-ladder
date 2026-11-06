#!/usr/bin/env bash
# SUR LE POD A (CW-214/215) : banc « moteur seul » sur les 20 jeux publics NON témoins, sans Franzen ni LLM.
# 1) contrôle « moteur muet » (10 min, 30 000 coups au plus par jeu) ; 2) moteur (CHRYS_AMODAL=1, CHRYS_BUT_SUPPOSE=1,
# budget 2 s par appel comme S1), 48 min par jeu (plafond S1). 20 jeux en parallèle, nice, 16 Go par processus.
W=/workspace; R=$W/chrysalide3; O=$R/experiments/moteur_seul/raw_pod
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
JEUX=$(ls $R/experiments/arc3/environment_files | grep -v -E '^(vc33|tu93|wa30|s5i5|cn04)$')
mkdir -p $O; cd $R
for c in muet moteur; do
  m=48; [ $c = muet ] && m=10
  j "moteur seul : début $c ($(echo $JEUX | wc -w) jeux, $m min)"
  for g in $JEUX; do
    ( ulimit -v 16000000; CHRYS_AMODAL=1 CHRYS_BUT_SUPPOSE=1 CHRYS_MOTEUR_BUDGET_S=2 PYTHONPATH=$R:$W/pylib \
      nice -n 10 timeout $(( (m + 15) * 60 )) $W/harnais/.venv/bin/python experiments/moteur_seul/banc.py $g $c $O/${c}_$g.json $m 0 \
      > $O/${c}_$g.log 2>&1 ) &
  done
  wait; j "moteur seul : fin $c ($(ls $O/${c}_*.json 2>/dev/null | wc -l) json)"
done
touch $W/bancs/moteur_seul.FINI
