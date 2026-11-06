#!/usr/bin/env bash
# SUR LE POD A (CCM-180-A) : essai apparié S1 moteur allumé EN PROCESSUS SÉPARÉ (CHRYS_MOTEUR_PROCESSUS=1) contre S1 éteint,
# 20 jeux non témoins (défaut de bloc.sh), 48 min, même serveur, en même temps. Mesure : tours/h et niveaux.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais > /dev/null
j "début S1proc (moteur en processus séparé) et S1off2"
cd $R && setsid nohup bash scripts/pod/bloc.sh S1proc CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_MOTEUR_PROCESSUS=1 CHRYS_TUTO=0 \
  CHRYS_MOTEUR_BUDGET_S=2 CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 \
  MAX_RUNTIME_MINUTES=48 > $W/runs/S1proc.log 2>&1 < /dev/null &
sleep 20
cd $R && setsid nohup bash scripts/pod/bloc.sh S1off2 MAX_RUNTIME_MINUTES=48 > $W/runs/S1off2.log 2>&1 < /dev/null &
