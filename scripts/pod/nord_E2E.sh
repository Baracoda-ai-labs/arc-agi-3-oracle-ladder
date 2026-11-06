#!/usr/bin/env bash
# SUR LE POD B (CW-167) : coupe le lot 3 « ancien » à 10 h 34 (3 600 s) ; puis, après E2E1 (V0), E2E2 = V0 + films,
# puis E2E3 = V1 (boucle à étages) + films ; mêmes 5 jeux, 60 min par jeu, 1 passe. Harnais repatché (copie du code) avant.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/bancs/nord_etapes.txt; }
JEUX='["ls20","sk48","sp80","ft09","tr87"]'
( until [ "$(date -u +%H%M)" -ge 0834 ]; do sleep 30; done
  for p in $(pgrep -f "creneau_llm.sh|llm_langage.py"); do kill "$p" 2>/dev/null; done; j "lot 3 ancien coupé (CW-167, 3 600 s)" ) &
until [ -f $W/runs/E2E1/FINI ] || [ -f $W/runs/E2E1/ARRET ]; do sleep 30; done
j "fin E2E1 (V0)"
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && j "harnais repatché (films)"
cd $R && bash scripts/pod/bloc.sh E2E2 CHRYS_MOTEUR=1 CHRYS_TUTO=1 CHRYS_MOTEUR_CLE=1 MAX_RUNTIME_MINUTES=60 -- "$JEUX"
j "fin E2E2 (V0 + films)"
j "E2E3 déplacé sur le pod A (CW-170)"
