#!/usr/bin/env bash
# SUR LE POD A (CW-198 (3)) : S1 sur les 25 jeux, moteur ALLUMÉ (réglages du notebook S1) contre ÉTEINT (Franzen pur,
# garde posé mais inactif), EN PARALLÈLE sur le même serveur (comparaison appariée : même charge), 48 min par jeu
# (= essai du notebook : 532 min × 10 flux / 110 jeux). Puis la voie B de B (CCM-128-B) sur le même serveur.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais
j "début S1on (moteur allumé) — le serveur se lève"
cd $R && setsid nohup bash scripts/pod/bloc.sh S1on CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_TUTO=0 CHRYS_MOTEUR_BUDGET_S=2 \
  CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 MAX_RUNTIME_MINUTES=48 \
  > $W/runs/S1on.log 2>&1 < /dev/null &
until curl -sf http://127.0.0.1:8011/health > /dev/null; do sleep 15; done
sleep 30
j "début S1off (moteur éteint), en parallèle"
cd $R && setsid nohup bash scripts/pod/bloc.sh S1off MAX_RUNTIME_MINUTES=48 > $W/runs/S1off.log 2>&1 < /dev/null &
j "début voie B (B, creneau_voieB.sh) sur le même serveur"
cd $R && PYTHONPATH=$R:$W/pylib PY=$W/harnais/.venv/bin/python bash experiments/T3.6/creneau_voieB.sh > $W/bancs/voieB.log 2>&1
j "fin voie B (code $?)"
