#!/usr/bin/env bash
# SUR LE POD A (CW-217) : banc moteur seul, variante « tout éteint » (CHRYS_AMODAL=0, CHRYS_BUT_SUPPOSE=0), mêmes plafonds
# que moteur_seul.sh (48 min, 30 000 coups, 2 s par appel), en parallèle de la variante allumée.
W=/workspace; R=$W/chrysalide3; O=$R/experiments/moteur_seul/raw_pod
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
JEUX=$(ls $R/experiments/arc3/environment_files | grep -v -E '^(vc33|tu93|wa30|s5i5|cn04)$')
cd $R; j "moteur seul : début eteint"
for g in $JEUX; do
  ( ulimit -v 16000000; CHRYS_AMODAL=0 CHRYS_BUT_SUPPOSE=0 CHRYS_MOTEUR_BUDGET_S=2 PYTHONPATH=$R:$W/pylib \
    nice -n 10 timeout $(( 63 * 60 )) $W/harnais/.venv/bin/python experiments/moteur_seul/banc.py $g eteint $O/eteint_$g.json 48 0 \
    > $O/eteint_$g.log 2>&1 ) &
done
wait; j "moteur seul : fin eteint ($(ls $O/eteint_*.json 2>/dev/null | wc -l) json)"; touch $W/bancs/moteur_seul_eteint.FINI
