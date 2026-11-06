#!/usr/bin/env bash
# SUR LE POD A (CW-177.2) : après E2E4, lot CPU de B (taux de base d'E4 au niveau 1, 20 jeux publics, ≤ 6 processus),
# puis ARRÊT du pod (arrêt, pas suppression ; AUTORISE_ARRET pour la cale), faute d'autre file.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
until [ -f $W/runs/E2E4_A/FINI ] || [ -f $W/runs/E2E4_A/ARRET ]; do sleep 30; done
j "fin E2E4 (pod A) ; arrêt du serveur, lot CPU de B"
for p in $(pgrep -f "sglang serve"); do kill "$p"; done
cd $R && bash scripts/pod/lancer_lot.sh e4_n1_publics python experiments/T2.9/e4_n1_lot.py 6
until [ -f $W/bancs/e4_n1_publics.FINI ]; do sleep 60; done
j "fin du lot e4_n1_publics ($(cat $W/bancs/e4_n1_publics.FINI)) ; arrêt du pod A (CW-177.2)"
touch $W/AUTORISE_ARRET; . $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID"
