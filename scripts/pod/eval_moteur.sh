#!/usr/bin/env bash
# SUR LE POD A (CW-227, nuit du 18 au 19/10), après le débit et compile_gpt : évaluation du moteur, meilleure variante de D
# (CHRYS_AMODAL=1 CHRYS_JAUGE_COURTE=1 CHRYS_TUILES=1 CHRYS_BUT_SUPPOSE=1, CCM-013-D), en parallèle :
#  (3) moteur seul, 20 jeux publics non témoins, 48 min, mêmes plafonds que CCM-192-A ;
#  (4) T4 complet (banc_export.py de D, 397 niveaux, 60 s, 20 processus).
# Le contrôle D et les configurations B/C du diagnostic tournent au Mac (CCM-197-A).
W=/workspace; R=$W/chrysalide3; O=$R/experiments/moteur_seul/raw_pod; P=$W/harnais/.venv/bin/python
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
export CHRYS_AMODAL=1 CHRYS_JAUGE_COURTE=1 CHRYS_TUILES=1 CHRYS_BUT_SUPPOSE=1
JEUX=$(ls $R/experiments/arc3/environment_files | grep -v -E '^(vc33|tu93|wa30|s5i5|cn04)$')
cd $R; j "éval moteur : début (meilleure variante de D)"
for g in $JEUX; do
  ( ulimit -v 16000000; CHRYS_MOTEUR_BUDGET_S=2 PYTHONPATH=$R:$W/pylib nice -n 10 timeout $(( 63 * 60 )) \
    $P experiments/moteur_seul/banc.py $g meilleure $O/meilleure_$g.json 48 0 > $O/meilleure_$g.log 2>&1 ) &
  # + prise de main courte de C (CHRYS_GARDE=3, CCM-090-C ; branche.py joue garde_n coups puis redemande)
  ( ulimit -v 16000000; CHRYS_GARDE=3 CHRYS_MOTEUR_BUDGET_S=2 PYTHONPATH=$R:$W/pylib nice -n 10 timeout $(( 63 * 60 )) \
    $P experiments/moteur_seul/banc.py $g garde3 $O/garde3_$g.json 48 0 > $O/garde3_$g.log 2>&1 ) &
done
( ulimit -v 16000000; PYTHONPATH=$R:$R/experiments/T4:$W/pylib OMP_NUM_THREADS=1 nice -n 10 \
  $P experiments/T4/banc_export.py $W/t4/environment_files $R/experiments/T4/resultats/combi_meilleure_pod.json 60 20 \
  > $W/runs/t4_meilleure.log 2>&1; j "éval moteur : fin T4 (code $?)" ) &
wait; j "éval moteur : fin ($(ls $O/meilleure_*.json 2>/dev/null | wc -l) json meilleure, $(ls $O/garde3_*.json 2>/dev/null | wc -l) json garde3)"
