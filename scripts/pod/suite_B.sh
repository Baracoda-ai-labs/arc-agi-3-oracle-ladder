#!/usr/bin/env bash
# SUR LE POD B (CW-177.2) : après E2E4 ls20 g1, arrêt du pod (arrêt, pas suppression), faute d'autre file.
W=/workspace
until grep -q "fin E2E4 ls20 g1" $W/bancs/nord_etapes.txt 2>/dev/null; do sleep 30; done
echo "$(date '+%d/%m %H:%M') arrêt du pod B (CW-177.2)" >> $W/bancs/nord_etapes.txt
. $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID"
