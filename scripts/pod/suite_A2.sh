#!/usr/bin/env bash
# SUR LE POD A : arrêt APRÈS (1) la fin du lot e4_n1_publics et de g50t à 16 Go, (2) le rapatriement par A (fichier
# /workspace/RAPATRIE), ou au plus tard 45 min après la fin des lots (jamais à vide ; les fichiers restent sur le volume).
W=/workspace
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
until [ -f $W/bancs/e4_n1_publics.FINI ] && [ -f $W/bancs/g50t_16go.FINI ] && [ -f $W/bancs/plafonds_P0.FINI ]; do sleep 60; done
j "lots CPU finis ; attente du rapatriement (45 min au plus)"
for _ in $(seq 1 45); do [ -f $W/RAPATRIE ] && break; sleep 60; done
j "arrêt du pod A (CW-177.2)"
touch $W/AUTORISE_ARRET; . $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID"
