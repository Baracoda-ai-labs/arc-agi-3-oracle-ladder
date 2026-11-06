#!/usr/bin/env bash
# SUR LE POD B : lot 3 de P1-b (CW-155/156, CCM-099-B : surprise dans l'ontologie, choix fermé ; sauvetage + lecteur tolérant),
# APRÈS la fin du lot 2 (CW-154 : ne pas l'interrompre). Le code du lot 3 est déposé à part (bancs/T3.3_lot3, chrysalide_lot3)
# et recopié seulement quand le lot 2 est fini, pour ne pas changer le code sous un lot en cours.
W=/workspace; R=$W/chrysalide3; T=$R/experiments/T3.3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/bancs/nord_etapes.txt; }
until grep -q "fin P1-b lot 2" $W/bancs/nord_etapes.txt 2>/dev/null; do sleep 30; done
mkdir -p $T/lot2_pod && cp -r $T/resultats_pod.json $T/raw_pod $T/lot2_pod/ 2>/dev/null; cp $W/bancs/creneau_llm2.log $T/lot2_pod/ 2>/dev/null
cp -r $R/experiments/entrainement $T/lot2_pod/entrainement 2>/dev/null
cp -r $W/bancs/T3.3_lot3/. $T/ && cp -r $W/bancs/chrysalide_lot3/. $R/chrysalide/
curl -sf http://127.0.0.1:8011/health >/dev/null || { j "serveur absent : lot 3 sauté"; exit 1; }
j "début P1-b lot 3 (surprise dans l'ontologie, choix fermé)"
cd $R && timeout 7500 env PYTHONPATH=$R PY=$W/harnais/.venv/bin/python PLAFOND=7200 bash experiments/T3.3/creneau_llm.sh > $W/bancs/creneau_llm3.log 2>&1
j "fin P1-b lot 3 (code $?)"
